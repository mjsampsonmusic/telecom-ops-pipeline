# Telecom Service Operations BI Pipeline

An end-to-end ETL and reporting pipeline for a (synthetic) regional telecom provider.
It pulls data from three source systems, cleans and conforms it into a SQL data
warehouse, validates it with automated data quality checks, and publishes a KPI
dashboard. Pure Python standard library plus SQLite, so it runs anywhere with Python 3.10+.


## What it does

| Stage | Detail |
|---|---|
| **Extract** | Billing and network usage CSV exports; support tickets from a paginated, token-authenticated REST API (`pipeline/mock_api.py` stands in for a SaaS ticketing platform). The API client retries 5xx and network errors with exponential backoff. |
| **Transform** | Deduplicates re-exported rows, normalizes mixed date formats and inconsistent casing, maps unknown plans, computes resolution hours and SLA compliance, and quarantines tickets that reference unknown customers. Every cleanup action is logged. |
| **Load** | Idempotent upserts into a star schema (`dim_customer`, `dim_date`, `fact_invoice`, `fact_ticket`, `fact_usage`). Re-running never duplicates rows. |
| **Validate** | Seven post-load checks: row count reconciliation, orphan keys, invalid amounts, impossible timestamps, duplicate IDs, billing after disconnect. Results are written to `etl_run_log`. |
| **Report** | SQL KPI views (revenue, ARPU, ticket volume, MTTR, SLA %, usage by plan, region health) rendered to a self-contained HTML dashboard. |
| **Automate** | GitHub Actions runs the tests and the pipeline on every push and nightly, and publishes the dashboard as a build artifact. |

## Run it

```bash
python -m pipeline.run                    # generates sample data on first run
python -m pipeline.run --fail-rate 0.15   # inject API outages to exercise retries
python -m unittest discover -s tests -v
open reports/dashboard.html
```

Query the warehouse directly:

```bash
sqlite3 data/warehouse.db "SELECT * FROM v_ticket_kpis;"
```

## Layout

```
pipeline/   generate.py  mock_api.py  extract.py  transform.py  load.py  quality.py  report.py  run.py
sql/        schema.sql (star schema)   kpi_views.sql (reporting views)
tests/      unit tests for transforms, integration tests for the API client and full run
docs/       data_flow.md (sources, mappings, lineage)   runbook.md (operations and troubleshooting)
```

All customer, billing, and ticket data is randomly generated. No real company data is used.
