"""Load step: idempotent upserts into the SQLite star schema."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((SQL_DIR / "schema.sql").read_text())
    return conn


def date_key(iso: str) -> int:
    return int(iso[:10].replace("-", ""))


def load_dim_date(conn, start: date, end: date) -> None:
    rows, d = [], start
    while d <= end:
        rows.append((date_key(d.isoformat()), d.isoformat(), d.year, d.month,
                     d.strftime("%Y-%m"), d.isoweekday()))
        d += timedelta(days=1)
    conn.executemany("INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?,?,?)", rows)


def load_customers(conn, customers: list[dict]) -> dict:
    conn.executemany("""
        INSERT INTO dim_customer (customer_id, region, plan_name, monthly_rate,
                                  start_date, end_date, is_active)
        VALUES (:customer_id, :region, :plan_name, :monthly_rate, :start_date, :end_date, :is_active)
        ON CONFLICT(customer_id) DO UPDATE SET
            region=excluded.region, plan_name=excluded.plan_name,
            monthly_rate=excluded.monthly_rate, end_date=excluded.end_date,
            is_active=excluded.is_active
    """, customers)
    return dict(conn.execute("SELECT customer_id, customer_key FROM dim_customer"))


def load_facts(conn, keys: dict, invoices, usage, tickets) -> int:
    conn.executemany("INSERT OR REPLACE INTO fact_invoice VALUES (?,?,?,?,?)", [
        (i["invoice_id"], keys[i["customer_id"]], date_key(i["invoice_date"]), i["amount"], i["paid"])
        for i in invoices])
    conn.executemany("INSERT OR REPLACE INTO fact_usage VALUES (?,?,?,?)", [
        (keys[u["customer_id"]], date_key(u["usage_date"]), u["gb_down"], u["gb_up"])
        for u in usage])
    conn.executemany("INSERT OR REPLACE INTO fact_ticket VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (t["ticket_id"], keys[t["customer_id"]], date_key(t["opened_at"]), t["category"],
         t["priority"], t["opened_at"], t["closed_at"], t["resolution_hours"],
         t["sla_hours"], t["sla_met"])
        for t in tickets])
    return len(invoices) + len(usage) + len(tickets)


def create_views(conn) -> None:
    conn.executescript((SQL_DIR / "kpi_views.sql").read_text())
