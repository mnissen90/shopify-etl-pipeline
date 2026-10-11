"""Load: SQL Server I/O for the pipeline.

All statements are parameterized. The incremental strategy is
delete-and-reload over an overlap window: each run deletes the last
N days for the client and reloads them, so reruns and backfills are
idempotent.
"""

from __future__ import annotations

import datetime as dt
import logging

import pyodbc

from ..config import DbConfig
from .transform import COLUMNS, to_insert_tuples

logger = logging.getLogger(__name__)

TABLE = "ShopifyOrders"
BATCH_SIZE = 1000

INSERT_SQL = (
    f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in COLUMNS)})"
)

# Derived metric kept in sync after every load.
UPDATE_DERIVED_SQL = f"""
UPDATE {TABLE}
SET [line_items_price] =
      ISNULL([gross_sales], 0)
    - ISNULL([total_discount], 0)
    + ISNULL([returns], 0)
    + ISNULL([shipping], 0)
    + ISNULL([tax], 0)
"""

DEDUPE_SQL_PATH = "sql/dedupe.sql"


def get_connection(db: DbConfig) -> pyodbc.Connection:
    return pyodbc.connect(db.odbc_string, autocommit=False)


def get_last_loaded_date(
    conn: pyodbc.Connection, client_name: str
) -> dt.date | None:
    """Latest loaded date for a client (NULL when the client is new)."""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT CAST(MAX([date]) AS datetime) FROM {TABLE} "
        "WHERE ClientName = ? AND gross_sales > 0",
        client_name,
    )
    row = cursor.fetchone()
    value = row[0] if row else None
    return value.date() if value else None


def delete_since(
    conn: pyodbc.Connection, client_name: str, since: dt.date
) -> int:
    """Delete a client's rows on/after `since`. Returns rows deleted."""
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM {TABLE} WHERE [date] >= ? AND ClientName = ?",
        str(since),
        client_name,
    )
    deleted = cursor.rowcount
    conn.commit()
    logger.info(
        "Deleted %d rows for %s since %s", deleted, client_name, since
    )
    return deleted


def insert_rows(conn: pyodbc.Connection, rows: list[dict]) -> int:
    """Bulk-insert flattened rows in batches. Returns rows inserted."""
    if not rows:
        return 0
    cursor = conn.cursor()
    total = 0
    batch = to_insert_tuples(rows)
    for i in range(0, len(batch), BATCH_SIZE):
        cursor.executemany(INSERT_SQL, batch[i : i + BATCH_SIZE])
        total += len(batch[i : i + BATCH_SIZE])
    conn.commit()
    logger.info("Inserted %d rows into %s", total, TABLE)
    return total


def refresh_derived_metrics(conn: pyodbc.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(UPDATE_DERIVED_SQL)
    conn.commit()
    logger.info("Refreshed derived metrics")


def run_dedupe(conn: pyodbc.Connection) -> None:
    """Apply the idempotent ROW_NUMBER() dedupe from sql/dedupe.sql."""
    from pathlib import Path

    sql = Path(DEDUPE_SQL_PATH).read_text()
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    logger.info("Dedupe complete")
