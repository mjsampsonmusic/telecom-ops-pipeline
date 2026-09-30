-- Star schema for the operations data warehouse (SQLite)
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key   INTEGER PRIMARY KEY,
    customer_id    TEXT UNIQUE NOT NULL,
    region         TEXT NOT NULL,
    plan_name      TEXT NOT NULL,
    monthly_rate   REAL NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    is_active      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INTEGER PRIMARY KEY,      -- YYYYMMDD
    full_date    TEXT UNIQUE NOT NULL,
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    year_month   TEXT NOT NULL,
    day_of_week  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_invoice (
    invoice_id     TEXT PRIMARY KEY,
    customer_key   INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    amount         REAL NOT NULL,
    paid           INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_ticket (
    ticket_id        TEXT PRIMARY KEY,
    customer_key     INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    opened_date_key  INTEGER NOT NULL REFERENCES dim_date(date_key),
    category         TEXT NOT NULL,
    priority         TEXT NOT NULL,
    opened_at        TEXT NOT NULL,
    closed_at        TEXT,
    resolution_hours REAL,
    sla_hours        REAL NOT NULL,
    sla_met          INTEGER
);

CREATE TABLE IF NOT EXISTS fact_usage (
    customer_key  INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    gb_down       REAL NOT NULL,
    gb_up         REAL NOT NULL,
    PRIMARY KEY (customer_key, date_key)
);

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL,
    rows_loaded   INTEGER,
    checks_failed INTEGER,
    notes         TEXT
);
