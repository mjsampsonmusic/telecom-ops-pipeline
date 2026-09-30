-- KPI views consumed by the dashboard and ad hoc SQL reporting
DROP VIEW IF EXISTS v_monthly_revenue;
CREATE VIEW v_monthly_revenue AS
SELECT d.year_month,
       ROUND(SUM(f.amount), 2)                                      AS billed,
       ROUND(SUM(CASE WHEN f.paid = 1 THEN f.amount ELSE 0 END), 2) AS collected,
       COUNT(DISTINCT f.customer_key)                               AS billed_customers,
       ROUND(SUM(f.amount) / COUNT(DISTINCT f.customer_key), 2)     AS arpu
FROM fact_invoice f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.year_month;

DROP VIEW IF EXISTS v_ticket_kpis;
CREATE VIEW v_ticket_kpis AS
SELECT d.year_month,
       COUNT(*)                                            AS tickets_opened,
       ROUND(AVG(t.resolution_hours), 1)                   AS mttr_hours,
       ROUND(100.0 * SUM(t.sla_met) / COUNT(t.sla_met), 1) AS sla_pct
FROM fact_ticket t
JOIN dim_date d ON d.date_key = t.opened_date_key
GROUP BY d.year_month;

DROP VIEW IF EXISTS v_tickets_by_category;
CREATE VIEW v_tickets_by_category AS
SELECT category,
       COUNT(*)                                        AS tickets,
       ROUND(AVG(resolution_hours), 1)                 AS mttr_hours,
       ROUND(100.0 * SUM(sla_met) / COUNT(sla_met), 1) AS sla_pct
FROM fact_ticket
GROUP BY category
ORDER BY tickets DESC;

DROP VIEW IF EXISTS v_usage_by_plan;
CREATE VIEW v_usage_by_plan AS
SELECT c.plan_name,
       COUNT(DISTINCT c.customer_key) AS customers,
       ROUND(SUM(u.gb_down) / COUNT(*), 1) AS avg_gb_down_per_month
FROM fact_usage u
JOIN dim_customer c ON c.customer_key = u.customer_key
GROUP BY c.plan_name
ORDER BY avg_gb_down_per_month DESC;

DROP VIEW IF EXISTS v_region_health;
CREATE VIEW v_region_health AS
SELECT c.region,
       COUNT(DISTINCT CASE WHEN c.is_active = 1 THEN c.customer_key END) AS active_customers,
       COUNT(t.ticket_id)                                                AS tickets,
       ROUND(1.0 * COUNT(t.ticket_id) /
             MAX(COUNT(DISTINCT CASE WHEN c.is_active = 1 THEN c.customer_key END), 1), 2)
                                                                         AS tickets_per_active_customer
FROM dim_customer c
LEFT JOIN fact_ticket t ON t.customer_key = c.customer_key
GROUP BY c.region
ORDER BY tickets_per_active_customer DESC;
