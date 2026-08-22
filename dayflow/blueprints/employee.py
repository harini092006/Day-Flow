import os
from datetime import date, datetime, timedelta
from calendar import monthrange

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, current_app, send_file, abort
)
from werkzeug.utils import secure_filename

from database import get_db
from utils.auth_helper import role_required, is_valid_email
from utils.report_helper import generate_salary_slip_pdf, MONTH_NAMES

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


def _allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


def _current_employee(db):
    return db.execute("SELECT * FROM employees WHERE id=?", (session["user_id"],)).fetchone()


def _leave_summary(db, emp):
    """Annual Leave Allowed − Approved Leave Taken, counting actual calendar days per request."""
    approved = db.execute(
        "SELECT start_date, end_date FROM leave_requests WHERE employee_id=? AND status='Approved'",
        (emp["id"],),
    ).fetchall()
    taken = 0
    for r in approved:
        start = date.fromisoformat(r["start_date"])
        end = date.fromisoformat(r["end_date"])
        taken += (end - start).days + 1

    pending_days = 0
    pending_rows = db.execute(
        "SELECT start_date, end_date FROM leave_requests WHERE employee_id=? AND status='Pending'",
        (emp["id"],),
    ).fetchall()
    for r in pending_rows:
        start = date.fromisoformat(r["start_date"])
        end = date.fromisoformat(r["end_date"])
        pending_days += (end - start).days + 1

    allowance = emp["annual_leave_allowance"] if emp["annual_leave_allowance"] is not None else 24
    balance = max(allowance - taken, 0)
    return {
        "allowance": allowance,
        "taken": taken,
        "balance": balance,
        "pending_days": pending_days,
    }


# ---------------------------------------------------------------- Dashboard
@employee_bp.route("/dashboard")
@role_required("employee")
def dashboard():
    db = get_db()
    emp = _current_employee(db)
    today = date.today().isoformat()

    today_att = db.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND att_date=?", (emp["id"], today)
    ).fetchone()

    month_start = date.today().replace(day=1).isoformat()
    total_days = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE employee_id=? AND att_date >= ? AND att_date <= ?",
        (emp["id"], month_start, today),
    ).fetchone()["c"]
    present_days = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE employee_id=? AND att_date >= ? AND att_date <= ? AND status IN ('Present','Half-Day')",
        (emp["id"], month_start, today),
    ).fetchone()["c"]
    attendance_pct = round((present_days / total_days) * 100, 1) if total_days else 0

    leave_info = _leave_summary(db, emp)
    leave_balance = leave_info["balance"]

    pending_leaves = db.execute(
        "SELECT COUNT(*) c FROM leave_requests WHERE employee_id=? AND status='Pending'", (emp["id"],)
    ).fetchone()["c"]

    net_salary = emp["basic_salary"] + emp["allowance"] - emp["deduction"]

    notifications = db.execute(
        "SELECT * FROM notifications WHERE employee_id=? ORDER BY created_at DESC LIMIT 6", (emp["id"],)
    ).fetchall()

    recent_attendance = db.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND att_date <= ? ORDER BY att_date DESC LIMIT 5",
        (emp["id"], today),
    ).fetchall()
    recent_leaves = db.execute(
        "SELECT * FROM leave_requests WHERE employee_id=? ORDER BY created_at DESC LIMIT 5", (emp["id"],)
    ).fetchall()

    return render_template(
        "employee/dashboard.html", employee=emp, today_att=today_att,
        attendance_pct=attendance_pct, leave_balance=leave_balance, pending_leaves=pending_leaves,
        net_salary=net_salary, notifications=notifications,
        recent_attendance=recent_attendance, recent_leaves=recent_leaves
    )


@employee_bp.route("/notifications/mark-read", methods=["POST"])
@role_required("employee")
def mark_notifications_read():
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE employee_id=?", (session["user_id"],))
    db.commit()
    return redirect(request.referrer or url_for("employee.dashboard"))


# ---------------------------------------------------------------- Profile
@employee_bp.route("/profile", methods=["GET", "POST"])
@role_required("employee")
def profile():
    db = get_db()
    emp = _current_employee(db)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        dob = request.form.get("dob") or None
        emergency_contact_name = request.form.get("emergency_contact_name", "").strip()
        emergency_contact_phone = request.form.get("emergency_contact_phone", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if email and not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        if email:
            dup = db.execute("SELECT id FROM employees WHERE email=? AND id != ?", (email, emp["id"])).fetchone()
            if dup:
                errors.append("Another account already uses this email.")

        if errors:
            for e in errors:
                flash(e, "danger")
            documents = db.execute(
                "SELECT * FROM documents WHERE employee_id=? ORDER BY uploaded_at DESC", (emp["id"],)
            ).fetchall()
            return render_template("employee/profile.html", employee=emp, documents=documents)

        photo_filename = emp["profile_photo"]
        photo = request.files.get("profile_photo")
        if photo and photo.filename:
            if _allowed_file(photo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
                photo_filename = f"{emp['employee_code']}_{secure_filename(photo.filename)}"
                photo.save(os.path.join(current_app.config["UPLOAD_FOLDER_PROFILE"], photo_filename))
            else:
                flash("Profile photo must be a PNG/JPG/JPEG/GIF file.", "warning")

        db.execute(
            """UPDATE employees SET full_name=?, email=?, phone=?, address=?, dob=?,
               emergency_contact_name=?, emergency_contact_phone=?, profile_photo=? WHERE id=?""",
            (full_name, email or emp["email"], phone, address, dob,
             emergency_contact_name, emergency_contact_phone, photo_filename, emp["id"]),
        )
        db.commit()
        session["full_name"] = full_name
        flash("Profile updated successfully.", "success")
        return redirect(url_for("employee.profile"))

    documents = db.execute(
        "SELECT * FROM documents WHERE employee_id=? ORDER BY uploaded_at DESC", (emp["id"],)
    ).fetchall()
    recognitions = db.execute(
        "SELECT * FROM recognitions WHERE employee_id=? ORDER BY created_at DESC", (emp["id"],)
    ).fetchall()
    return render_template("employee/profile.html", employee=emp, documents=documents, recognitions=recognitions)


@employee_bp.route("/documents/upload", methods=["POST"])
@role_required("employee")
def upload_document():
    db = get_db()
    emp = _current_employee(db)
    doc_type = request.form.get("doc_type", "Other")
    doc_file = request.files.get("document")

    if not doc_file or not doc_file.filename:
        flash("Please choose a file to upload.", "danger")
        return redirect(url_for("employee.profile"))

    if not _allowed_file(doc_file.filename, current_app.config["ALLOWED_DOCUMENT_EXTENSIONS"]):
        flash("Only PDF, PNG, JPG or JPEG files are allowed.", "danger")
        return redirect(url_for("employee.profile"))

    safe_name = secure_filename(doc_file.filename)
    stored_name = f"{emp['employee_code']}_{doc_type}_{int(datetime.now().timestamp())}_{safe_name}"
    doc_file.save(os.path.join(current_app.config["UPLOAD_FOLDER_DOCUMENTS"], stored_name))

    db.execute(
        "INSERT INTO documents (employee_id, doc_type, filename, original_name) VALUES (?,?,?,?)",
        (emp["id"], doc_type, stored_name, safe_name),
    )
    db.commit()
    flash(f"{doc_type} uploaded successfully.", "success")
    return redirect(url_for("employee.profile"))


# ---------------------------------------------------------------- Attendance
@employee_bp.route("/attendance", methods=["GET", "POST"])
@role_required("employee")
def attendance():
    db = get_db()
    emp = _current_employee(db)
    today = date.today().isoformat()

    if request.method == "POST":
        action = request.form.get("action")
        now_time = datetime.now().strftime("%H:%M:%S")
        existing = db.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND att_date=?", (emp["id"], today)
        ).fetchone()

        if action == "check_in":
            if existing and existing["check_in"]:
                flash("You have already checked in today.", "warning")
            else:
                if existing:
                    db.execute("UPDATE attendance SET check_in=?, status='Present' WHERE id=?", (now_time, existing["id"]))
                else:
                    db.execute(
                        "INSERT INTO attendance (employee_id, att_date, check_in, status) VALUES (?,?,?,?)",
                        (emp["id"], today, now_time, "Present"),
                    )
                db.commit()
                flash(f"Checked in at {now_time}.", "success")

        elif action == "check_out":
            if not existing or not existing["check_in"]:
                flash("You need to check in before checking out.", "danger")
            elif existing["check_out"]:
                flash("You have already checked out today.", "warning")
            else:
                check_in_dt = datetime.strptime(existing["check_in"], "%H:%M:%S")
                check_out_dt = datetime.strptime(now_time, "%H:%M:%S")
                hours_worked = (check_out_dt - check_in_dt).total_seconds() / 3600
                status = "Half-Day" if hours_worked < 4 else "Present"
                db.execute(
                    "UPDATE attendance SET check_out=?, status=? WHERE id=?",
                    (now_time, status, existing["id"]),
                )
                db.commit()
                flash(f"Checked out at {now_time}.", "success")

        return redirect(url_for("employee.attendance"))

    view = request.args.get("view", "monthly")
    if view == "daily":
        start = today
    elif view == "weekly":
        start = (date.today() - timedelta(days=7)).isoformat()
    else:
        start = date.today().replace(day=1).isoformat()

    records = db.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND att_date >= ? AND att_date <= ? ORDER BY att_date DESC",
        (emp["id"], start, today),
    ).fetchall()

    today_att = db.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND att_date=?", (emp["id"], today)
    ).fetchone()

    return render_template("employee/attendance.html", records=records, view=view, today_att=today_att)


# ---------------------------------------------------------------- Leave
@employee_bp.route("/leave", methods=["GET", "POST"])
@role_required("employee")
def leave():
    db = get_db()
    emp = _current_employee(db)

    if request.method == "POST":
        leave_type = request.form.get("leave_type")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        reason = request.form.get("reason", "").strip()
        remarks = request.form.get("remarks", "").strip()

        errors = []
        if not leave_type:
            errors.append("Please select a leave type.")
        if not start_date or not end_date:
            errors.append("Start and end dates are required.")
        elif start_date > end_date:
            errors.append("End date cannot be before start date.")
        if not reason:
            errors.append("Please provide a reason for your leave.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            db.execute(
                """INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, reason, remarks)
                   VALUES (?,?,?,?,?,?)""",
                (emp["id"], leave_type, start_date, end_date, reason, remarks),
            )
            db.commit()
            flash("Leave request submitted successfully.", "success")
        return redirect(url_for("employee.leave"))

    history = db.execute(
        "SELECT * FROM leave_requests WHERE employee_id=? ORDER BY created_at DESC", (emp["id"],)
    ).fetchall()
    leave_info = _leave_summary(db, emp)
    return render_template("employee/leave.html", history=history, leave_info=leave_info)


# ---------------------------------------------------------------- Payroll
@employee_bp.route("/payroll")
@role_required("employee")
def payroll():
    db = get_db()
    emp = _current_employee(db)
    net_salary = emp["basic_salary"] + emp["allowance"] - emp["deduction"]
    slips = db.execute(
        "SELECT * FROM payroll WHERE employee_id=? ORDER BY year DESC, month DESC", (emp["id"],)
    ).fetchall()
    return render_template(
        "employee/payroll.html", employee=emp, net_salary=net_salary,
        slips=slips, month_names=MONTH_NAMES
    )


@employee_bp.route("/payroll/slip/<int:year>/<int:month>")
@role_required("employee")
def download_slip(year, month):
    db = get_db()
    emp = _current_employee(db)
    slip = db.execute(
        "SELECT * FROM payroll WHERE employee_id=? AND year=? AND month=?", (emp["id"], year, month)
    ).fetchone()
    if not slip:
        flash("No salary slip found for that month yet.", "warning")
        return redirect(url_for("employee.payroll"))

    buf = generate_salary_slip_pdf(emp, month, year, current_app.config["COMPANY_NAME"])
    filename = f"SalarySlip_{emp['employee_code']}_{MONTH_NAMES[month]}{year}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


# ---------------------------------------------------------------- Documents
@employee_bp.route("/documents")
@role_required("employee")
def documents():
    db = get_db()
    emp = _current_employee(db)
    docs = db.execute(
        "SELECT * FROM documents WHERE employee_id=? ORDER BY uploaded_at DESC", (emp["id"],)
    ).fetchall()
    return render_template("employee/documents.html", documents=docs)


# ---------------------------------------------------------------- Ask HR
@employee_bp.route("/queries")
@role_required("employee")
def queries():
    db = get_db()
    emp = _current_employee(db)
    rows = db.execute(
        "SELECT * FROM hr_queries WHERE employee_id=? ORDER BY updated_at DESC", (emp["id"],)
    ).fetchall()
    return render_template("employee/queries.html", queries=rows)


@employee_bp.route("/queries/new", methods=["POST"])
@role_required("employee")
def new_query():
    db = get_db()
    emp = _current_employee(db)
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    if not subject or not message:
        flash("Please enter both a subject and your question.", "danger")
        return redirect(url_for("employee.queries"))

    cur = db.execute(
        "INSERT INTO hr_queries (employee_id, subject, status) VALUES (?,?, 'Pending')",
        (emp["id"], subject),
    )
    query_id = cur.lastrowid
    db.execute(
        "INSERT INTO hr_query_messages (query_id, sender_role, sender_name, message) VALUES (?,?,?,?)",
        (query_id, "employee", emp["full_name"], message),
    )
    db.commit()
    flash("Your query was sent to HR.", "success")
    return redirect(url_for("employee.query_detail", query_id=query_id))


@employee_bp.route("/queries/<int:query_id>", methods=["GET", "POST"])
@role_required("employee")
def query_detail(query_id):
    db = get_db()
    emp = _current_employee(db)
    q = db.execute(
        "SELECT * FROM hr_queries WHERE id=? AND employee_id=?", (query_id, emp["id"])
    ).fetchone()
    if not q:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action", "reply")
        if action == "resolve":
            db.execute("UPDATE hr_queries SET status='Resolved', updated_at=datetime('now') WHERE id=?", (query_id,))
            db.commit()
            flash("Query marked as resolved. Thanks for confirming!", "success")
        else:
            message = request.form.get("message", "").strip()
            if message:
                db.execute(
                    "INSERT INTO hr_query_messages (query_id, sender_role, sender_name, message) VALUES (?,?,?,?)",
                    (query_id, "employee", emp["full_name"], message),
                )
                new_status = "Pending" if q["status"] != "Resolved" else "Pending"
                db.execute(
                    "UPDATE hr_queries SET status=?, updated_at=datetime('now') WHERE id=?",
                    (new_status, query_id),
                )
                db.commit()
                flash("Message sent to HR.", "success")
        return redirect(url_for("employee.query_detail", query_id=query_id))

    q = db.execute("SELECT * FROM hr_queries WHERE id=?", (query_id,)).fetchone()
    messages = db.execute(
        "SELECT * FROM hr_query_messages WHERE query_id=? ORDER BY created_at ASC", (query_id,)
    ).fetchall()
    return render_template("employee/query_detail.html", q=q, messages=messages)
