"""Generate synthetic source-system exports for a regional telecom provider.

Three "source systems" are simulated, each with its own quirks so the
pipeline has real cleanup work to do:
  * billing  -> customers.csv, invoices.csv (CSV export, mixed casing, dupes)
  * network  -> usage.csv (monthly GB per customer)
  * ticketing -> tickets.json (served by mock_api.py as a paginated REST API)
All data is fake. Seeded so every run is reproducible.
"""
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

REGIONS = ["Ellettsville", "Spencer", "Bloomington", "Bedford", "Gosport", "Stinesville"]
PLANS = {  # plan -> (monthly rate, avg monthly GB down)
    "Fiber 1 Gig": (89.99, 620),
    "Fiber 500": (69.99, 410),
    "Fiber 100": (49.99, 240),
    "DSL 25": (39.99, 110),
    "Voice Only": (24.99, 0),
}
CATEGORIES = {  # category -> (weight, SLA hours, mean resolution hours)
    "Outage": (18, 4, 3.2),
    "Repair": (30, 24, 19.0),
    "Install": (20, 72, 55.0),
    "Billing": (22, 48, 20.0),
    "Equipment": (10, 48, 30.0),
}
PRIORITY = {"Outage": "P1", "Repair": "P2", "Install": "P3", "Billing": "P3", "Equipment": "P2"}


def month_starts(start: date, months: int):
    y, m = start.year, start.month
    for _ in range(months):
        yield date(y, m, 1)
        m += 1
        if m == 13:
            y, m = y + 1, 1


def generate(out_dir: Path, n_customers: int = 600, months: int = 12, seed: int = 42) -> dict:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    first_month = date(2025, 10, 1)
    last_day = date(2026, 9, 30)

    customers = []
    for i in range(1, n_customers + 1):
        plan = rng.choices(list(PLANS), weights=[18, 30, 25, 17, 10])[0]
        start = first_month - timedelta(days=rng.randint(0, 900))
        end = None
        if rng.random() < 0.12:  # churned during the window
            end = first_month + timedelta(days=rng.randint(30, 330))
        region = rng.choice(REGIONS)
        # source quirks: inconsistent casing / whitespace in the billing export
        if rng.random() < 0.08:
            region = f"  {region.upper()} "
        customers.append({
            "customer_id": f"C{i:05d}",
            "region": region,
            "plan": plan if rng.random() > 0.01 else "",
            "start_date": start.isoformat(),
            "end_date": end.isoformat() if end else "",
        })

    with open(out_dir / "customers.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(customers[0]))
        w.writeheader()
        w.writerows(customers)
        w.writerows(rng.sample(customers, 9))  # duplicate rows from a re-export

    invoices, usage = [], []
    inv_seq = 0
    for c in customers:
        plan = c["plan"] or "Fiber 100"
        rate, gb = PLANS[plan]
        end = date.fromisoformat(c["end_date"]) if c["end_date"] else None
        for ms in month_starts(first_month, months):
            if end and ms > end:
                break
            inv_seq += 1
            invoices.append({
                "invoice_id": f"INV{inv_seq:07d}",
                "customer_id": c["customer_id"],
                # mixed date formats from the billing system
                "invoice_date": ms.strftime("%m/%d/%Y") if inv_seq % 7 == 0 else ms.isoformat(),
                "amount": f"{rate + (rng.choice([0, 0, 0, 5.00, 12.50])):.2f}",
                "status": rng.choices(["PAID", "paid", "OPEN"], weights=[80, 12, 8])[0],
            })
            if gb:
                down = max(0.0, rng.gauss(gb, gb * 0.25))
                usage.append({
                    "customer_id": c["customer_id"],
                    "month": ms.strftime("%Y-%m"),
                    "gb_down": f"{down:.1f}",
                    "gb_up": f"{down * rng.uniform(0.08, 0.3):.1f}",
                })

    with open(out_dir / "invoices.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(invoices[0]))
        w.writeheader()
        w.writerows(invoices)
    with open(out_dir / "usage.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(usage[0]))
        w.writeheader()
        w.writerows(usage)

    tickets = []
    cat_names = list(CATEGORIES)
    weights = [CATEGORIES[c][0] for c in cat_names]
    for t in range(1, int(n_customers * 1.6) + 1):
        cat = rng.choices(cat_names, weights=weights)[0]
        _, sla, mean_hrs = CATEGORIES[cat]
        opened = datetime(2025, 10, 1) + timedelta(minutes=rng.randint(0, 364 * 24 * 60))
        hrs = rng.expovariate(1 / mean_hrs)
        closed = opened + timedelta(hours=hrs)
        still_open = closed.date() > last_day or rng.random() < 0.02
        cust = rng.choice(customers)["customer_id"] if rng.random() > 0.005 else "C99999"  # orphan
        tickets.append({
            "id": f"TKT-{t:06d}",
            "customer": cust,
            "category": cat,
            "priority": PRIORITY[cat],
            "opened": opened.isoformat(timespec="minutes"),
            "closed": None if still_open else closed.isoformat(timespec="minutes"),
        })
    with open(out_dir / "tickets.json", "w") as f:
        json.dump(tickets, f)

    return {"customers": len(customers), "invoices": len(invoices),
            "usage": len(usage), "tickets": len(tickets)}


if __name__ == "__main__":
    print(generate(Path("data/raw")))
