"""Transform step: standardize, deduplicate, and conform source rows to the warehouse model."""
from datetime import date, datetime

PLAN_RATES = {"Fiber 1 Gig": 89.99, "Fiber 500": 69.99, "Fiber 100": 49.99,
              "DSL 25": 39.99, "Voice Only": 24.99}
SLA_HOURS = {"Outage": 4, "Repair": 24, "Install": 72, "Billing": 48, "Equipment": 48}
AS_OF = date(2026, 9, 30)


def parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {value!r}")


def clean_customers(rows: list[dict]) -> tuple[list[dict], list[str]]:
    seen, out, issues = set(), [], []
    for r in rows:
        cid = r["customer_id"].strip()
        if cid in seen:
            issues.append(f"duplicate customer {cid} dropped")
            continue
        seen.add(cid)
        plan = r["plan"].strip()
        if plan not in PLAN_RATES:
            issues.append(f"customer {cid}: missing/unknown plan, set to 'Unassigned'")
            plan = "Unassigned"
        end = parse_date(r["end_date"]) if r["end_date"].strip() else None
        out.append({
            "customer_id": cid,
            "region": r["region"].strip().title(),
            "plan_name": plan,
            "monthly_rate": PLAN_RATES.get(plan, 0.0),
            "start_date": parse_date(r["start_date"]).isoformat(),
            "end_date": end.isoformat() if end else None,
            "is_active": int(end is None or end > AS_OF),
        })
    return out, issues


def clean_invoices(rows: list[dict]) -> list[dict]:
    return [{
        "invoice_id": r["invoice_id"],
        "customer_id": r["customer_id"],
        "invoice_date": parse_date(r["invoice_date"]).isoformat(),
        "amount": round(float(r["amount"]), 2),
        "paid": int(r["status"].strip().upper() == "PAID"),
    } for r in rows]


def clean_usage(rows: list[dict]) -> list[dict]:
    return [{
        "customer_id": r["customer_id"],
        "usage_date": f"{r['month']}-01",
        "gb_down": float(r["gb_down"]),
        "gb_up": float(r["gb_up"]),
    } for r in rows]


def clean_tickets(rows: list[dict], known_customers: set) -> tuple[list[dict], list[str]]:
    out, issues = [], []
    for r in rows:
        if r["customer"] not in known_customers:
            issues.append(f"ticket {r['id']}: unknown customer {r['customer']}, quarantined")
            continue
        opened = datetime.fromisoformat(r["opened"])
        closed = datetime.fromisoformat(r["closed"]) if r["closed"] else None
        hours = round((closed - opened).total_seconds() / 3600, 2) if closed else None
        sla = SLA_HOURS[r["category"]]
        out.append({
            "ticket_id": r["id"],
            "customer_id": r["customer"],
            "category": r["category"],
            "priority": r["priority"],
            "opened_at": opened.isoformat(),
            "closed_at": closed.isoformat() if closed else None,
            "resolution_hours": hours,
            "sla_hours": sla,
            "sla_met": None if hours is None else int(hours <= sla),
        })
    return out, issues
