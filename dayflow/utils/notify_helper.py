"""Shared notification helpers: manual notify() plus automatic
birthday / work-anniversary / welcome notification generation.
"""
from datetime import date


def notify(db, employee_id, message, ntype="info", title=None):
    """Insert a notification for one employee. Caller is responsible for db.commit()."""
    db.execute(
        "INSERT INTO notifications (employee_id, title, message, type) VALUES (?,?,?,?)",
        (employee_id, title, message, ntype),
    )


def notify_all_active_employees(db, message, ntype="announcement", title=None, exclude_id=None):
    rows = db.execute(
        "SELECT id FROM employees WHERE is_active=1 AND role='employee'" +
        (" AND id != ?" if exclude_id else ""),
        (exclude_id,) if exclude_id else (),
    ).fetchall()
    for r in rows:
        notify(db, r["id"], message, ntype, title)


def _already_sent(db, employee_id, event_type, event_key):
    row = db.execute(
        "SELECT id FROM auto_events WHERE employee_id=? AND event_type=? AND event_key=?",
        (employee_id, event_type, event_key),
    ).fetchone()
    return row is not None


def _mark_sent(db, employee_id, event_type, event_key):
    try:
        db.execute(
            "INSERT INTO auto_events (employee_id, event_type, event_key) VALUES (?,?,?)",
            (employee_id, event_type, event_key),
        )
    except Exception:
        pass  # unique constraint race — another request already recorded it


def check_and_send_auto_notifications(db, employee):
    """Called opportunistically (e.g. on dashboard load) for the signed-in employee.
    Sends at most one birthday and one work-anniversary notification per calendar year,
    tracked via the auto_events table so re-visiting the dashboard never duplicates them.
    """
    today = date.today()
    year_key = str(today.year)
    changed = False

    dob = employee["dob"]
    if dob:
        try:
            dob_date = date.fromisoformat(dob)
            if (dob_date.month, dob_date.day) == (today.month, today.day):
                if not _already_sent(db, employee["id"], "birthday", year_key):
                    notify(
                        db, employee["id"],
                        f"Happy Birthday, {employee['full_name']}! 🎉 Wishing you a wonderful day "
                        f"filled with happiness and success!",
                        ntype="birthday",
                        title="🎂 Happy Birthday!",
                    )
                    _mark_sent(db, employee["id"], "birthday", year_key)
                    changed = True
        except ValueError:
            pass

    joining_date = employee["joining_date"]
    if joining_date:
        try:
            join_date = date.fromisoformat(joining_date)
            years = today.year - join_date.year
            if (join_date.month, join_date.day) == (today.month, today.day) and years > 0:
                if not _already_sent(db, employee["id"], "anniversary", year_key):
                    notify(
                        db, employee["id"],
                        f"Congratulations, {employee['full_name']}, on completing {years} "
                        f"wonderful year{'s' if years != 1 else ''} with our organization! "
                        f"Wishing you continued success!",
                        ntype="anniversary",
                        title="🎉 Happy Work Anniversary!",
                    )
                    _mark_sent(db, employee["id"], "anniversary", year_key)
                    changed = True
        except ValueError:
            pass

    if changed:
        db.commit()
