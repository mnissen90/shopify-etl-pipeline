"""Validate: reconcile the warehouse against the Shopify API.

For each day in the loaded window, sum a metric (e.g. gross_sales) from the
warehouse and compare it to the same metric computed straight from the API.
Anything outside tolerance is reported as a discrepancy. This is the
"trust but verify" step that catches silent API changes, missed refunds,
and partial loads.
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import pyodbc

from .extract import ShopifyClient
from .load import TABLE
from .transform import flatten_order

logger = logging.getLogger(__name__)


def warehouse_daily_totals(
    conn: pyodbc.Connection,
    client_name: str,
    metric: str,
    start: dt.date,
    end: dt.date,
) -> pd.DataFrame:
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT CAST([date] AS date) AS day, SUM({metric}) AS warehouse_total "
        f"FROM {TABLE} "
        "WHERE ClientName = ? AND CAST([date] AS date) BETWEEN ? AND ? "
        "GROUP BY CAST([date] AS date)",
        client_name,
        str(start),
        str(end),
    )
    df = pd.DataFrame(cursor.fetchall(), columns=["day", "warehouse_total"])
    if not df.empty:
        df["day"] = pd.to_datetime(df["day"]).dt.date
        df["warehouse_total"] = df["warehouse_total"].fillna(0).astype(float)
    return df


def api_daily_totals(
    client: ShopifyClient,
    client_name: str,
    metric: str,
    start: dt.date,
    end: dt.date,
) -> pd.DataFrame:
    """Re-pull each day from the API and sum the metric from flattened rows."""
    totals: dict[dt.date, float] = {}
    day = start
    while day <= end:
        day_total = 0.0
        for order in client.fetch_orders(day):
            for row in flatten_order(order, client_name):
                day_total += float(row.get(metric) or 0)
        totals[day] = day_total
        day += dt.timedelta(days=1)
    df = pd.DataFrame(
        [{"day": d, "api_total": t} for d, t in totals.items()]
    )
    return df


def find_discrepancies(
    conn: pyodbc.Connection,
    client: ShopifyClient,
    client_name: str,
    metric: str = "gross_sales",
    start: dt.date | None = None,
    end: dt.date | None = None,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Return days where warehouse and API totals differ beyond tolerance."""
    end = end or (dt.date.today() - dt.timedelta(days=1))
    start = start or (end - dt.timedelta(days=7))

    warehouse = warehouse_daily_totals(conn, client_name, metric, start, end)
    api = api_daily_totals(client, client_name, metric, start, end)

    merged = api.merge(warehouse, on="day", how="outer").fillna(0)
    merged["diff"] = (merged["api_total"] - merged["warehouse_total"]).abs()
    discrep = merged[merged["diff"] > tolerance].copy()
    discrep["metric"] = metric
    discrep["client"] = client_name

    if not discrep.empty:
        logger.warning(
            "Found %d discrepant days for %s on %s",
            len(discrep),
            client_name,
            metric,
        )
    else:
        logger.info("No discrepancies for %s on %s", client_name, metric)
    return discrep
