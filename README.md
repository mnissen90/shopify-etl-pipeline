# Shopify ETL Pipeline

Production-style ETL pipeline that ingests Shopify order data (orders, line items,
shipping, and refunds) into SQL Server, with built-in data quality checks and
failure alerting.

This project is a cleaned-up, open-source-friendly restructure of ETL scripts I
ran in production for several years at a digital advertising agency, loading
multi-client ecommerce data on a daily schedule.

## Architecture

```
                 ┌──────────────┐
                 │ Shopify REST │
                 │     API      │
                 └──────┬───────┘
                        │  paginated pulls, retries w/ backoff
                        ▼
                 ┌──────────────┐      ┌───────────────┐
                 │   extract.py │─────▶│  transform.py │
                 └──────────────┘      └───────┬───────┘
                        flatten orders            │  dedupe, derived metrics
                        to line items             ▼
                                          ┌──────────────┐
                                          │    load.py   │
                                          └──────┬───────┘
                                                 │  incremental: delete-and-reload
                                                 │  10-day overlap window
                                                 ▼
                                          ┌──────────────┐
                                          │  SQL Server  │
                                          └──────┬───────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        ▼                        ▼                        ▼
                 ┌──────────────┐      ┌──────────────────┐      ┌───────────────┐
                 │  validate.py │      │  SQL aggregations│      │   alerts.py   │
                 └──────────────┘      └──────────────────┘      └───────────────┘
                  reconcile API vs       order-level rollups     email on client
                  warehouse totals       & dedup (sql/)          failure / anomaly
```

`pipeline.py` orchestrates the whole run: for each client it determines the
incremental window, extracts, transforms, loads, validates, and collects any
client failures into a single alert email.

## Project layout

```
shopify-etl-pipeline/
├── README.md
├── requirements.txt
├── .env.example            # copy to .env and fill in (never commit .env)
├── config.py               # typed config loaded from environment
├── src/
│   ├── extract.py          # Shopify API client: pagination, retries
│   ├── transform.py        # pure functions: flatten, dedupe (unit-tested)
│   ├── load.py             # SQL Server loading, incremental windows
│   ├── validate.py         # API-vs-warehouse reconciliation checks
│   ├── alerts.py           # email alerting
│   └── pipeline.py         # orchestrator: python -m src.pipeline
├── sql/
│   ├── schema.sql          # table DDL
│   └── dedupe.sql          # idempotent dedupe for the orders table
├── tests/
│   └── test_transform.py   # pytest suite (no database required)
└── clients/                # one .ini per Shopify store (see .env.example)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in your values
```

Create the table:

```bash
sqlcmd -S $DB_SERVER -d $DB_NAME -U $DB_USER -i sql/schema.sql
```

Add one client config per store in `clients/`, e.g. `clients/acme.ini`:

```ini
[shopify]
store_name = acme
api_key = ${SHOPIFY_API_KEY}
api_password = ${SHOPIFY_API_SECRET}
```

## Running

```bash
python -m src.pipeline
```

In production this ran daily via Windows Task Scheduler on an Azure VM. Any
scheduler works (cron, Airflow, Task Scheduler) since the pipeline is
idempotent: each run deletes and reloads a 10-day overlap window, so reruns
and backfills are safe.

## Testing

```bash
pytest
```

The transform layer is pure functions over dicts/DataFrames, so the suite runs
without a database or API credentials.

## Configuration

| Variable | Description |
|---|---|
| `DB_SERVER` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | SQL Server connection |
| `DB_DRIVER` | ODBC driver (default: `ODBC Driver 18 for SQL Server`) |
| `SHOPIFY_API_VERSION` | e.g. `2020-10` |
| `ALERT_FROM` / `ALERT_TO` / `SMTP_HOST` ... | failure alert email settings |
| `OVERLAP_DAYS` | incremental overlap window (default: 10) |
| `MAX_RETRIES` / `RETRY_BACKOFF_SECONDS` | API retry policy |

## Notes on the restructure

The original scripts were single-file, per-client jobs with hardcoded paths and
string-interpolated SQL. Restructuring them here, I:

- moved all secrets and paths into environment-based config (no hardcoded
  credentials or `C:\Users\...` paths),
- replaced `print` debugging with the `logging` module,
- parameterized every SQL statement (the originals interpolated values into
  `DELETE`/`SELECT` strings),
- extracted retry-with-backoff into a reusable decorator,
- pulled the flatten/dedupe logic into pure, unit-tested functions,
- kept the business logic faithful: same incremental strategy, same refund
  handling, same reconciliation approach.
