"""End-to-end ETL run: extract -> transform -> load -> quality checks -> dashboard.

Usage:  python -m pipeline.run [--fail-rate 0.1] [--db data/warehouse.db]
"""
import argparse
import logging
from datetime import date, datetime
from pathlib import Path

from . import extract, load, quality, report, transform
from .generate import generate
from .mock_api import TOKEN, serve_in_background

log = logging.getLogger("pipeline")


def run(raw_dir: Path, db_path: Path, report_path: Path, fail_rate: float = 0.0) -> dict:
    started = datetime.now().isoformat(timespec="seconds")
    if not (raw_dir / "customers.csv").exists():
        log.info("no source exports found, generating synthetic data: %s", generate(raw_dir))

    # Extract
    server, base_url = serve_in_background(raw_dir / "tickets.json", fail_rate=fail_rate)
    try:
        raw_tickets = extract.fetch_tickets(base_url, TOKEN)
    finally:
        server.shutdown()
    raw_customers = extract.read_csv(raw_dir / "customers.csv")
    raw_invoices = extract.read_csv(raw_dir / "invoices.csv")
    raw_usage = extract.read_csv(raw_dir / "usage.csv")

    # Transform
    customers, issues = transform.clean_customers(raw_customers)
    invoices = transform.clean_invoices(raw_invoices)
    usage = transform.clean_usage(raw_usage)
    tickets, t_issues = transform.clean_tickets(raw_tickets, {c["customer_id"] for c in customers})
    issues += t_issues
    log.info("transform: %s cleanup actions logged", len(issues))

    # Load
    conn = load.connect(db_path)
    with conn:
        load.load_dim_date(conn, date(2023, 1, 1), date(2026, 12, 31))
        keys = load.load_customers(conn, customers)
        rows = load.load_facts(conn, keys, invoices, usage, tickets)
        load.create_views(conn)

    # Validate + report
    checks = quality.run_checks(conn, {"invoices": len(invoices), "usage": len(usage)})
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        (log.info if ok else log.error)("check %-32s %s (%s)", name, "PASS" if ok else "FAIL", detail)
    report.render(conn, checks, report_path)

    with conn:
        conn.execute("INSERT INTO etl_run_log (started_at, finished_at, status, rows_loaded, checks_failed, notes)"
                     " VALUES (?,?,?,?,?,?)",
                     (started, datetime.now().isoformat(timespec="seconds"),
                      "FAILED_CHECKS" if failed else "SUCCESS", rows, len(failed), f"{len(issues)} cleanup actions"))
    conn.close()
    return {"rows_loaded": rows, "checks_failed": len(failed), "cleanup_actions": len(issues)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--db", default="data/warehouse.db")
    ap.add_argument("--report", default="reports/dashboard.html")
    ap.add_argument("--fail-rate", type=float, default=0.0, help="inject API 503s to exercise retries")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(Path(a.raw), Path(a.db), Path(a.report), a.fail_rate)
    log.info("done: %s", result)
    raise SystemExit(1 if result["checks_failed"] else 0)


if __name__ == "__main__":
    main()
