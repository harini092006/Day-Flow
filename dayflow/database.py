import sqlite3
from datetime import date
from flask import g, current_app
from werkzeug.security import generate_password_hash


def get_db():
    """Return a request-scoped SQLite connection with row access by column name."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('employee','admin')),
    gender TEXT,
    dob TEXT,
    phone TEXT,
    address TEXT,
    department TEXT,
    job_title TEXT,
    joining_date TEXT,
    employment_type TEXT DEFAULT 'Full-Time',
    profile_photo TEXT,
    basic_salary REAL DEFAULT 0,
    allowance REAL DEFAULT 0,
    deduction REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    att_date TEXT NOT NULL,
    check_in TEXT,
    check_out TEXT,
    status TEXT NOT NULL DEFAULT 'Present' CHECK(status IN ('Present','Absent','Half-Day','Leave')),
    remarks TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE(employee_id, att_date)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    remarks TEXT,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected')),
    admin_comment TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    decided_at TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payroll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    basic_salary REAL NOT NULL,
    allowance REAL NOT NULL,
    deduction REAL NOT NULL,
    net_salary REAL NOT NULL,
    generated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE(employee_id, month, year)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    doc_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT,
    uploaded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    title TEXT,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hr_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Replied','Resolved')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hr_query_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    sender_role TEXT NOT NULL CHECK(sender_role IN ('employee','hr')),
    sender_name TEXT,
    message TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (query_id) REFERENCES hr_queries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    announcement_date TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recognitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    category TEXT,
    given_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hr_communications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_type TEXT NOT NULL CHECK(recipient_type IN ('individual','all')),
    recipient_id INTEGER,
    recipient_label TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel IN ('notification','email','both')),
    notified_count INTEGER DEFAULT 0,
    emailed_count INTEGER DEFAULT 0,
    email_failed_count INTEGER DEFAULT 0,
    sent_by TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auto_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_key TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE(employee_id, event_type, event_key)
);
"""

# Columns added after the initial release. Each tuple is (table, column, ddl-fragment).
# Applied with ALTER TABLE ... ADD COLUMN, ignoring "duplicate column" errors so this
# is safe to re-run against a database that already has some/all of these columns.
MIGRATIONS = [
    ("employees", "annual_leave_allowance", "REAL DEFAULT 24"),
    ("employees", "emergency_contact_name", "TEXT"),
    ("employees", "emergency_contact_phone", "TEXT"),
    # Default to 1 (already welcomed) so this migration doesn't retroactively greet
    # employees who existed before this feature shipped. New signups explicitly set 0.
    ("employees", "welcomed", "INTEGER DEFAULT 1"),
    ("notifications", "title", "TEXT"),
]


def init_db(app):
    """Create tables (if missing) and seed a default admin account."""
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
        db.commit()

        for table, column, ddl in MIGRATIONS:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
                db.commit()
            except sqlite3.OperationalError:
                pass  # column already exists — safe to ignore

        cur = db.execute("SELECT COUNT(*) AS c FROM employees WHERE role = 'admin'")
        if cur.fetchone()["c"] == 0:
            db.execute(
                """INSERT INTO employees
                   (employee_code, full_name, email, password_hash, role, department,
                    job_title, joining_date, employment_type, basic_salary, allowance, deduction)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "ADM001",
                    "Ananya Rao",
                    "admin@dayflow.com",
                    generate_password_hash("Admin@123"),
                    "admin",
                    "Human Resources",
                    "HR Manager",
                    date.today().isoformat(),
                    "Full-Time",
                    60000,
                    10000,
                    2000,
                ),
            )
            db.commit()
        db.close()
