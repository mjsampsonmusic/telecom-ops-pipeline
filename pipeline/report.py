"""Render the KPI views into a self-contained HTML dashboard (no external deps)."""
from datetime import datetime
from html import escape
from pathlib import Path


def _bar_chart(labels, values, title, color="#2f6fb0", fmt="{:,.0f}", w=560, h=220):
    pad, top = 36, 24
    vmax = max(values) or 1
    bw = (w - 2 * pad) / len(values)
    bars = []
    for i, (lab, v) in enumerate(zip(labels, values)):
        bh = (h - top - pad) * v / vmax
        x = pad + i * bw
        y = h - pad - bh
        bars.append(f'<rect x="{x + 3:.1f}" y="{y:.1f}" width="{bw - 6:.1f}" height="{bh:.1f}" fill="{color}"/>'
                    f'<text x="{x + bw / 2:.1f}" y="{h - pad + 14}" font-size="9" text-anchor="middle">{escape(lab[-5:])}</text>'
                    f'<text x="{x + bw / 2:.1f}" y="{y - 3:.1f}" font-size="8" text-anchor="middle">{fmt.format(v)}</text>')
    return (f'<figure><figcaption>{escape(title)}</figcaption>'
            f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">{"".join(bars)}</svg></figure>')


def _table(conn, sql, title):
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    head = "".join(f"<th>{escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in cur)
    return f"<section><h2>{escape(title)}</h2><table><tr>{head}</tr>{body}</table></section>"


def render(conn, checks, out_path: Path) -> Path:
    rev = conn.execute("SELECT year_month, billed, arpu FROM v_monthly_revenue ORDER BY year_month").fetchall()
    tk = conn.execute("SELECT year_month, tickets_opened, sla_pct FROM v_ticket_kpis ORDER BY year_month").fetchall()
    churn = conn.execute("SELECT year_month, churn_pct FROM v_monthly_churn ORDER BY year_month").fetchall()
    avg_churn = round(sum(r[1] for r in churn) / len(churn), 2) if churn else 0
    latest = rev[-1]
    active = conn.execute("SELECT COUNT(*) FROM dim_customer WHERE is_active = 1").fetchone()[0]
    sla_all = conn.execute("SELECT ROUND(100.0*SUM(sla_met)/COUNT(sla_met),1) FROM fact_ticket").fetchone()[0]
    mttr = conn.execute("SELECT ROUND(AVG(resolution_hours),1) FROM fact_ticket").fetchone()[0]
    passed = sum(1 for _, ok, _ in checks if ok)

    cards = "".join(f'<div class="card"><span>{escape(k)}</span><b>{escape(v)}</b></div>' for k, v in [
        ("Active customers", f"{active:,}"),
        (f"Billed {latest[0]}", f"${latest[1]:,.0f}"),
        ("ARPU", f"${latest[2]:,.2f}"),
        ("SLA met (12 mo)", f"{sla_all}%"),
        ("Mean time to resolve", f"{mttr} h"),
        ("Avg monthly churn", f"{avg_churn}%"),
        ("Data checks", f"{passed}/{len(checks)} passed"),
    ])
    checks_html = "".join(
        f'<li class="{"ok" if ok else "bad"}">{"PASS" if ok else "FAIL"}: {escape(n)} ({escape(d)})</li>'
        for n, ok, d in checks)

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Service Operations KPI Dashboard</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:0 auto;max-width:1180px;padding:24px;color:#1d2733;background:#f6f8fa}}
 h1{{margin:0 0 4px}} .sub{{color:#5b6875;margin:0 0 20px}}
 .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
 .card{{background:#fff;border:1px solid #dde3ea;border-radius:8px;padding:12px}}
 .card span{{display:block;font-size:12px;color:#5b6875}} .card b{{font-size:22px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:16px}}
 figure,section{{background:#fff;border:1px solid #dde3ea;border-radius:8px;padding:12px;margin:0;overflow-x:auto}}
 figcaption,h2{{font-weight:600;font-size:15px;margin:0 0 8px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid #eef1f4}}
 ul{{font-size:13px}} .ok{{color:#1a7f37}} .bad{{color:#c62828}}
</style></head><body>
<h1>Service Operations KPI Dashboard</h1>
<p class="sub">Generated {datetime.now():%Y-%m-%d %H:%M} from the operations data warehouse. Synthetic data.</p>
<div class="cards">{cards}</div>
<div class="grid">
{_bar_chart([r[0] for r in rev], [r[1] for r in rev], "Monthly billed revenue ($)", fmt="{:,.0f}")}
{_bar_chart([r[0] for r in tk], [r[1] for r in tk], "Tickets opened per month", color="#d9822b")}
{_bar_chart([r[0] for r in tk], [r[2] or 0 for r in tk], "SLA compliance by month (%)", color="#1a7f37", fmt="{:.0f}")}
{_bar_chart([r[0] for r in churn], [r[1] for r in churn], "Monthly churn rate (%)", color="#8e44ad", fmt="{:.2f}")}
{_table(conn, "SELECT * FROM v_tickets_by_category", "Tickets by category")}
{_table(conn, "SELECT * FROM v_usage_by_plan", "Average monthly download by plan (GB)")}
{_table(conn, "SELECT * FROM v_region_health", "Region health")}
</div>
<section style="margin-top:16px"><h2>Data quality checks</h2><ul>{checks_html}</ul></section>
</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path
