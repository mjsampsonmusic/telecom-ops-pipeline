# Data Flow and Lineage

```
billing system  --CSV-->  customers.csv, invoices.csv  --+
network system  --CSV-->  usage.csv                    --+--> transform --> SQLite warehouse --> KPI views --> dashboard.html
ticketing SaaS  --REST--> /api/v1/tickets (paginated)  --+                       |
                                                                          quality checks --> etl_run_log
```

## Source to target mapping

| Source field | Target | Rule |
|---|---|---|
| customers.customer_id | dim_customer.customer_id | trimmed; duplicates dropped (first row wins) |
| customers.region | dim_customer.region | trimmed, title case |
| customers.plan | dim_customer.plan_name, monthly_rate | unknown or blank mapped to `Unassigned` |
| customers.end_date | dim_customer.is_active | active if blank or after the as-of date |
| invoices.invoice_date | fact_invoice.date_key | accepts `YYYY-MM-DD` and `MM/DD/YYYY` |
| invoices.status | fact_invoice.paid | `PAID` in any case = 1 |
| usage.month | fact_usage.date_key | first day of month |
| tickets.opened / closed | fact_ticket.resolution_hours | closed minus opened, null if open |
| tickets.category | fact_ticket.sla_hours, sla_met | Outage 4h, Repair 24h, Billing/Equipment 48h, Install 72h |
| tickets.customer | fact_ticket.customer_key | unknown customer: quarantined and logged |
