import os
import sqlite3
from flask import current_app, g

SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Employee','Manager','Finance','Admin')),
    department TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_no TEXT UNIQUE,
    employee_id INTEGER NOT NULL REFERENCES users(id),
    department TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    expense_date TEXT NOT NULL,
    receipt_number TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Draft','Submitted','Approved','Rejected','Paid')),
    approver_id INTEGER REFERENCES users(id),
    approval_comment TEXT,
    submitted_at TEXT,
    approved_at TEXT,
    rejected_at TEXT,
    payment_date TEXT,
    payment_reference TEXT,
    paid_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    timestamp TEXT NOT NULL,
    ip_address TEXT
);

CREATE INDEX IF NOT EXISTS idx_claims_employee ON claims(employee_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_department ON claims(department);
CREATE INDEX IF NOT EXISTS idx_claims_expense_date ON claims(expense_date);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log records are immutable');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log records are immutable');
END;
"""


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        g.db = conn
    return g.db


def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    if current_app.config.get("SEED_DATA", True):
        from seed import seed_database
        seed_database(db)
