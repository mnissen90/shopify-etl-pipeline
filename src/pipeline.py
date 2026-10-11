"""Pipeline orchestrator.

For each client config in clients/*.ini:
  1. determine the incremental window (max loaded date minus overlap),
  2. delete-and-reload that window,
  3. pull orders from the Shopify API day by day (retries with backoff),
  4. flatten, dedupe, and insert,
  5. refresh derived metrics and run the idempotent dedupe,
  6. reconcile warehouse totals against the API.

Any client that fails after all retries is collected into a single alert
email at the end of the run.

Usage:
    python -m src.pipeline
"""

from __future__ import annotations

import configparser
import datetime as dt
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Settings  # noqa: E402
from src.alerts import send_alert  # noqa: E402
from src.extract import ShopifyClient  # noqa: E402
from src.load import (  # noqa: E402
    delete_since,
    get_connection,
    get_last_loaded_date,
    insert_rows,
    refresh_derived_metrics,
    run_dedupe,
)
from src.transform import dedupe_records, flatten_order  # noqa: E402
from src.validate import find_discrepancies  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")

# First-ever load starts here when a client has no history yet.
DEFAULT_START_DATE = dt.date(2019, 1, 1)


def load_client_configs(settings: Settings) -> list[dict]:
    """Read clients/*.ini into a list of {name, store_name, api_key, api_password}."""
    clients = []
    for path in sorted(settings.pipeline.clients_dir.glob("*.ini")):
        parser = configparser.ConfigParser()
        parser.read(path)
        section = parser["shopify"]
        clients.append(
            {
                "name": path.stem,
                "store_name": os.path.expandvars(section["store_name"]),
                "api_key": os.path.expandvars(section["api_key"]),
                "api_password": os.path.expandvars(section["api_password"]),
            }
        )
    return clients


def run_client(settings: Settings, client: dict) -> None:
    name = client["name"]
    shopify = ShopifyClient(
        store_name=client["store_name"],
        api_key=client["api_key"],
        api_password=client["api_password"],
        api_version=settings.shopify.api_version,
        max_retries=settings.pipeline.max_retries,
        backoff_seconds=settings.pipeline.retry_backoff_seconds,
    )

    with get_connection(settings.db) as conn:
        last_loaded = get_last_loaded_date(conn, name)
        start = (last_loaded or DEFAULT_START_DATE) - dt.timedelta(
            days=settings.pipeline.overlap_days
        )
        end = dt.date.today() - dt.timedelta(days=1)

        delete_since(conn, name, start)

        day = start
        while day <= end:
            logger.info("Loading %s for %s", name, day)
            rows: list[dict] = []
            for order in shopify.fetch_orders(day):
                rows.extend(flatten_order(order, name))
            # refunds pass: catches late adjustments to older orders
            for order in shopify.fetch_orders(day, updated_since=True):
                rows.extend(flatten_order(order, name))
            rows = dedupe_records(rows)
            insert_rows(conn, rows)
            day += dt.timedelta(days=1)

        refresh_derived_metrics(conn)
        run_dedupe(conn)

        discrepancies = find_discrepancies(
            conn, shopify, name, metric="gross_sales", start=start, end=end
        )
        if not discrepancies.empty:
            raise RuntimeError(
                f"Discrepancies found for {name}:\n"
                + discrepancies.to_string(index=False)
            )

    logger.info("Client %s complete", name)


def main() -> int:
    settings = Settings()
    clients = load_client_configs(settings)
    if not clients:
        logger.error("No client configs found in %s", settings.pipeline.clients_dir)
        return 1

    failed: list[str] = []
    for client in clients:
        try:
            run_client(settings, client)
        except Exception as err:  # noqa: BLE001 - collect and alert, don't stop
            logger.exception("Client %s failed", client["name"])
            failed.append(f"{client['name']}: {err}")

    if failed:
        subject = "ALERT: Shopify pipeline failures"
        body = "The following clients failed:\n\n" + "\n".join(failed)
        send_alert(settings.alerts, subject, body)
        return 1

    logger.info("Pipeline complete: all %d clients loaded", len(clients))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
