import sqlite3
import tempfile
import unittest
from pathlib import Path

from pipeline import transform
from pipeline.extract import fetch_tickets
from pipeline.generate import generate
from pipeline.mock_api import TOKEN, serve_in_background
from pipeline.run import run


class TransformTests(unittest.TestCase):
    def test_parse_mixed_date_formats(self):
        self.assertEqual(transform.parse_date("03/01/2026").isoformat(), "2026-03-01")
        self.assertEqual(transform.parse_date(" 2026-03-01 ").isoformat(), "2026-03-01")

    def test_customers_deduped_and_standardized(self):
        rows = [
            {"customer_id": "C1", "region": "  SPENCER ", "plan": "Fiber 500", "start_date": "2024-01-01", "end_date": ""},
            {"customer_id": "C1", "region": "Spencer", "plan": "Fiber 500", "start_date": "2024-01-01", "end_date": ""},
            {"customer_id": "C2", "region": "Bedford", "plan": "", "start_date": "2024-01-01", "end_date": ""},
        ]
        out, issues = transform.clean_customers(rows)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["region"], "Spencer")
        self.assertEqual(out[1]["plan_name"], "Unassigned")
        self.assertEqual(len(issues), 2)

    def test_orphan_ticket_quarantined_and_sla_flag(self):
        rows = [
            {"id": "T1", "customer": "C1", "category": "Outage", "priority": "P1",
             "opened": "2026-01-01T00:00", "closed": "2026-01-01T05:00"},
            {"id": "T2", "customer": "C404", "category": "Repair", "priority": "P2",
             "opened": "2026-01-01T00:00", "closed": None},
        ]
        out, issues = transform.clean_tickets(rows, {"C1"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["sla_met"], 0)  # 5h > 4h outage SLA
        self.assertEqual(len(issues), 1)


class IntegrationTests(unittest.TestCase):
    def test_api_client_retries_through_503s(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            counts = generate(raw, n_customers=50)
            server, url = serve_in_background(raw / "tickets.json", fail_rate=0.3)
            try:
                rows = fetch_tickets(url, TOKEN, page_size=10, max_retries=8, backoff=0.01)
            finally:
                server.shutdown()
            self.assertEqual(len(rows), counts["tickets"])

    def test_churn_view_matches_disconnects(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run(tmp / "raw", tmp / "wh.db", tmp / "dash.html")
            conn = sqlite3.connect(tmp / "wh.db")
            rows = conn.execute("SELECT year_month, disconnects, churn_pct FROM v_monthly_churn").fetchall()
            self.assertEqual(len(rows), 12)
            expected = conn.execute("""SELECT COUNT(*) FROM dim_customer
                                       WHERE end_date BETWEEN '2025-10-01' AND '2026-09-30'""").fetchone()[0]
            self.assertEqual(sum(r[1] for r in rows), expected)
            self.assertTrue(all(0 <= r[2] < 100 for r in rows))

    def test_end_to_end_run_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            args = (tmp / "raw", tmp / "wh.db", tmp / "dash.html")
            first = run(*args)
            second = run(*args)  # re-running must not duplicate rows
            self.assertEqual(first["checks_failed"], 0)
            self.assertEqual(first["rows_loaded"], second["rows_loaded"])
            conn = sqlite3.connect(tmp / "wh.db")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM etl_run_log").fetchone()[0], 2)
            self.assertTrue((tmp / "dash.html").read_text().startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
