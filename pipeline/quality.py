"""Post-load data quality checks. Each returns (name, passed, detail)."""


def run_checks(conn, source_counts: dict) -> list[tuple[str, bool, str]]:
    q = lambda sql: conn.execute(sql).fetchone()[0]
    results = []

    for table, src in (("fact_invoice", "invoices"), ("fact_usage", "usage")):
        loaded = q(f"SELECT COUNT(*) FROM {table}")
        results.append((f"row count reconciles: {table}", loaded == source_counts[src],
                        f"source={source_counts[src]} loaded={loaded}"))

    orphans = q("""SELECT COUNT(*) FROM fact_ticket t
                   LEFT JOIN dim_customer c ON c.customer_key = t.customer_key
                   WHERE c.customer_key IS NULL""")
    results.append(("no orphan tickets", orphans == 0, f"{orphans} orphans"))

    bad_amounts = q("SELECT COUNT(*) FROM fact_invoice WHERE amount <= 0")
    results.append(("invoice amounts positive", bad_amounts == 0, f"{bad_amounts} bad rows"))

    bad_times = q("SELECT COUNT(*) FROM fact_ticket WHERE closed_at IS NOT NULL AND closed_at < opened_at")
    results.append(("ticket close after open", bad_times == 0, f"{bad_times} bad rows"))

    dup_cust = q("SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM dim_customer")
    results.append(("customer ids unique", dup_cust == 0, f"{dup_cust} duplicates"))

    billed_after_churn = q("""SELECT COUNT(*) FROM fact_invoice f
                              JOIN dim_customer c ON c.customer_key = f.customer_key
                              JOIN dim_date d ON d.date_key = f.date_key
                              WHERE c.end_date IS NOT NULL AND d.full_date > c.end_date""")
    results.append(("no billing after disconnect", billed_after_churn == 0,
                    f"{billed_after_churn} invoices"))
    return results
