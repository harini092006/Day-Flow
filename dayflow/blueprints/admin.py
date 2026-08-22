import os
from datetime import date, datetime, timedelta
from calendar import monthrange

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, current_app, send_file, abort
)
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from database import get_db
from utils.auth_helper import role_required, is_valid_email, is_valid_password
from utils.email_helper import (
    send_leave_approved_email, send_leave_rejected_email, send_payroll_generated_email,
    send_hr_communication_email,
)
from utils.report_helper import generate_salary_slip_pdf, generate_report_pdf, generate_report_excel, MONTH_NAMES
from utils.notify_helper import notify as _notify_full, notify_all_active_employees

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _notify(db, employee_id, message, ntype="info", title=None):
    _notify_full(db, employee_id, message, ntype, title)


def _allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


# ---------------------------------------------------------------- Dashboard
@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    db = get_db()
    today = date.today().isoformat()

    total_employees = db.execute(
        "SELECT COUNT(*) c FROM employees WHERE role='employee' AND is_active=1"
    ).fetchone()["c"]

    present_today = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE att_date=? AND status='Present'", (today,)
    ).fetchone()["c"]

    half_day_today = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE att_date=? AND status='Half-Day'", (today,)
    ).fetchone()["c"]

    on_leave_today = db.execute(
        """SELECT COUNT(*) c FROM leave_requests
           WHERE status='Approved' AND start_date<=? AND end_date>=?""",
        (today, today),
    ).fetchone()["c"]

    pending_leaves = db.execute(
        "SELECT COUNT(*) c FROM leave_requests WHERE status='Pending'"
    ).fetchone()["c"]

    this_month = date.today().strftime("%Y-%m")
    monthly_payroll = db.execute(
        "SELECT COALESCE(SUM(net_salary),0) s FROM payroll WHERE printf('%04d-%02d', year, month) = ?",
        (this_month,),
    ).fetchone()["s"]

    if not monthly_payroll:
        monthly_payroll = db.execute(
            "SELECT COALESCE(SUM(basic_salary + allowance - deduction),0) s FROM employees WHERE role='employee' AND is_active=1"
        ).fetchone()["s"]

    recent_leaves = db.execute(
        """SELECT lr.*, e.full_name, e.employee_code FROM leave_requests lr
           JOIN employees e ON e.id = lr.employee_id
           ORDER BY lr.created_at DESC LIMIT 6"""
    ).fetchall()

    recent_employees = db.execute(
        "SELECT * FROM employees WHERE role='employee' ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    # --- Detailed rosters backing the clickable Present / Absent / Half-Day cards ---
    present_list = db.execute(
        """SELECT e.full_name, e.employee_code, e.department, a.status, a.check_in, a.check_out
           FROM attendance a JOIN employees e ON e.id = a.employee_id
           WHERE a.att_date=? AND a.status='Present' ORDER BY e.full_name""",
        (today,),
    ).fetchall()

    half_day_list = db.execute(
        """SELECT e.full_name, e.employee_code, e.department, a.status, a.check_in, a.check_out
           FROM attendance a JOIN employees e ON e.id = a.employee_id
           WHERE a.att_date=? AND a.status='Half-Day' ORDER BY e.full_name""",
        (today,),
    ).fetchall()

    absent_list = db.execute(
        """SELECT e.full_name, e.employee_code, e.department, 'Absent' AS status, NULL AS check_in, NULL AS check_out
           FROM employees e
           WHERE e.role='employee' AND e.is_active=1
             AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.employee_id=e.id AND a.att_date=?)
           ORDER BY e.full_name""",
        (today,),
    ).fetchall()
    absent_today = len(absent_list)

    # --- Data for the HR Communication box (send-to dropdown + recent activity log) ---
    hr_comm_employees = db.execute(
        "SELECT id, full_name, employee_code, department FROM employees "
        "WHERE role='employee' AND is_active=1 ORDER BY full_name"
    ).fetchall()

    hr_comm_recent = db.execute(
        "SELECT * FROM hr_communications ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    return render_template(
        "admin/dashboard.html",
        total_employees=total_employees,
        present_today=present_today,
        absent_today=absent_today,
        half_day_today=half_day_today,
        on_leave_today=on_leave_today,
        pending_leaves=pending_leaves,
        monthly_payroll=monthly_payroll,
        recent_leaves=recent_leaves,
        recent_employees=recent_employees,
        present_list=present_list,
        half_day_list=half_day_list,
        absent_list=absent_list,
        hr_comm_employees=hr_comm_employees,
        hr_comm_recent=hr_comm_recent,
    )


# ---------------------------------------------------------------- Employees
@admin_bp.route("/employees")
@role_required("admin")
def employees():
    db = get_db()
    search = request.args.get("search", "").strip()
    department = request.args.get("department", "").strip()

    query = "SELECT * FROM employees WHERE role='employee'"
    params = []
    if search:
        query += " AND (full_name LIKE ? OR employee_code LIKE ? OR email LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if department:
        query += " AND department = ?"
        params.append(department)
    query += " ORDER BY created_at DESC"

    rows = db.execute(query, params).fetchall()
    departments = db.execute(
        "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department"
    ).fetchall()

    return render_template(
        "admin/employees.html", employees=rows, departments=departments,
        search=search, department=department
    )


@admin_bp.route("/employees/add", methods=["GET", "POST"])
@role_required("admin")
def add_employee():
    if request.method == "POST":
        f = request.form
        employee_code = f.get("employee_id", "").strip()
        full_name = f.get("full_name", "").strip()
        email = f.get("email", "").strip().lower()
        password = f.get("password", "")
        role = f.get("role", "employee")
        department = f.get("department", "").strip()
        job_title = f.get("job_title", "").strip()
        phone = f.get("phone", "").strip()
        address = f.get("address", "").strip()
        joining_date = f.get("joining_date") or date.today().isoformat()
        basic_salary = float(f.get("basic_salary") or 0)
        allowance = float(f.get("allowance") or 0)
        deduction = float(f.get("deduction") or 0)

        errors = []
        if not employee_code:
            errors.append("Employee ID is required.")
        if not full_name:
            errors.append("Full name is required.")
        if not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        if not is_valid_password(password):
            errors.append("Password must be at least 8 characters long.")

        db = get_db()
        if not errors:
            if db.execute("SELECT id FROM employees WHERE email=?", (email,)).fetchone():
                errors.append("An account with this email already exists.")
            if db.execute("SELECT id FROM employees WHERE employee_code=?", (employee_code,)).fetchone():
                errors.append("This Employee ID is already in use.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/add_employee.html", form=f)

        photo_filename = None
        photo = request.files.get("profile_photo")
        if photo and photo.filename:
            if _allowed_file(photo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
                photo_filename = f"{employee_code}_{secure_filename(photo.filename)}"
                photo.save(os.path.join(current_app.config["UPLOAD_FOLDER_PROFILE"], photo_filename))
            else:
                flash("Profile photo must be a PNG/JPG/JPEG/GIF file. Employee saved without photo.", "warning")

        db.execute(
            """INSERT INTO employees
               (employee_code, full_name, email, password_hash, role, department, job_title,
                phone, address, joining_date, basic_salary, allowance, deduction, profile_photo, welcomed)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (employee_code, full_name, email, generate_password_hash(password), role, department,
             job_title, phone, address, joining_date, basic_salary, allowance, deduction, photo_filename),
        )
        new_id = db.execute("SELECT id FROM employees WHERE employee_code=?", (employee_code,)).fetchone()["id"]
        db.commit()

        flash(f"Employee {full_name} added successfully.", "success")
        return redirect(url_for("admin.employees"))

    return render_template("admin/add_employee.html", form={})


@admin_bp.route("/employees/<int:emp_id>")
@role_required("admin")
def employee_profile(emp_id):
    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        abort(404)
    documents = db.execute("SELECT * FROM documents WHERE employee_id=? ORDER BY uploaded_at DESC", (emp_id,)).fetchall()
    attendance_count = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE employee_id=? AND status='Present'", (emp_id,)
    ).fetchone()["c"]
    leave_count = db.execute(
        "SELECT COUNT(*) c FROM leave_requests WHERE employee_id=? AND status='Approved'", (emp_id,)
    ).fetchone()["c"]
    return render_template(
        "admin/employee_profile.html", employee=employee, documents=documents,
        attendance_count=attendance_count, leave_count=leave_count
    )


@admin_bp.route("/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_employee(emp_id):
    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        abort(404)

    if request.method == "POST":
        f = request.form
        full_name = f.get("full_name", "").strip()
        email = f.get("email", "").strip().lower()
        department = f.get("department", "").strip()
        job_title = f.get("job_title", "").strip()
        phone = f.get("phone", "").strip()
        address = f.get("address", "").strip()
        gender = f.get("gender", "").strip()
        dob = f.get("dob") or None
        joining_date = f.get("joining_date") or employee["joining_date"]
        employment_type = f.get("employment_type", "Full-Time")
        basic_salary = float(f.get("basic_salary") or 0)
        allowance = float(f.get("allowance") or 0)
        deduction = float(f.get("deduction") or 0)
        annual_leave_allowance = float(f.get("annual_leave_allowance") or 24)
        emergency_contact_name = f.get("emergency_contact_name", "").strip()
        emergency_contact_phone = f.get("emergency_contact_phone", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        dup = db.execute("SELECT id FROM employees WHERE email=? AND id != ?", (email, emp_id)).fetchone()
        if dup:
            errors.append("Another account already uses this email.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/edit_employee.html", employee=employee)

        photo_filename = employee["profile_photo"]
        photo = request.files.get("profile_photo")
        if photo and photo.filename:
            if _allowed_file(photo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
                photo_filename = f"{employee['employee_code']}_{secure_filename(photo.filename)}"
                photo.save(os.path.join(current_app.config["UPLOAD_FOLDER_PROFILE"], photo_filename))
            else:
                flash("Profile photo must be a PNG/JPG/JPEG/GIF file.", "warning")

        old_allowance = employee["annual_leave_allowance"]

        db.execute(
            """UPDATE employees SET full_name=?, email=?, department=?, job_title=?, phone=?, address=?,
               gender=?, dob=?, joining_date=?, employment_type=?, basic_salary=?, allowance=?, deduction=?,
               profile_photo=?, annual_leave_allowance=?, emergency_contact_name=?, emergency_contact_phone=?
               WHERE id=?""",
            (full_name, email, department, job_title, phone, address, gender, dob, joining_date,
             employment_type, basic_salary, allowance, deduction, photo_filename,
             annual_leave_allowance, emergency_contact_name, emergency_contact_phone, emp_id),
        )
        if old_allowance != annual_leave_allowance:
            _notify(
                db, emp_id,
                f"Your annual leave allowance was updated to {annual_leave_allowance:g} days. "
                f"Your leave balance has been recalculated automatically.",
                "info", title="Leave Allowance Updated",
            )
        db.commit()
        flash("Employee details updated successfully.", "success")
        return redirect(url_for("admin.employee_profile", emp_id=emp_id))

    return render_template("admin/edit_employee.html", employee=employee)


@admin_bp.route("/employees/<int:emp_id>/delete", methods=["POST"])
@role_required("admin")
def delete_employee(emp_id):
    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        abort(404)
    if employee["id"] == session.get("user_id"):
        flash("You cannot delete your own account while signed in.", "danger")
        return redirect(url_for("admin.employees"))
    db.execute("DELETE FROM employees WHERE id=?", (emp_id,))
    db.commit()
    flash(f"Employee {employee['full_name']} was removed.", "success")
    return redirect(url_for("admin.employees"))


# ---------------------------------------------------------------- Attendance
@admin_bp.route("/attendance")
@role_required("admin")
def attendance():
    db = get_db()
    filter_date = request.args.get("date", date.today().isoformat())
    department = request.args.get("department", "").strip()
    search = request.args.get("search", "").strip()

    query = """
        SELECT e.id AS employee_id, e.full_name, e.employee_code, e.department,
               a.id AS attendance_id, a.check_in, a.check_out, a.status, a.remarks
        FROM employees e
        LEFT JOIN attendance a ON a.employee_id = e.id AND a.att_date = ?
        WHERE e.role = 'employee' AND e.is_active = 1
    """
    params = [filter_date]
    if department:
        query += " AND e.department = ?"
        params.append(department)
    if search:
        query += " AND (e.full_name LIKE ? OR e.employee_code LIKE ?)"
        like = f"%{search}%"
        params += [like, like]
    query += " ORDER BY e.full_name"

    rows = db.execute(query, params).fetchall()
    departments = db.execute(
        "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department"
    ).fetchall()

    return render_template(
        "admin/attendance.html", rows=rows, filter_date=filter_date,
        department=department, search=search, departments=departments
    )


@admin_bp.route("/attendance/mark", methods=["POST"])
@role_required("admin")
def mark_attendance():
    db = get_db()
    employee_id = request.form.get("employee_id")
    att_date = request.form.get("att_date") or date.today().isoformat()
    status = request.form.get("status", "Present")
    check_in = request.form.get("check_in") or None
    check_out = request.form.get("check_out") or None

    existing = db.execute(
        "SELECT id FROM attendance WHERE employee_id=? AND att_date=?", (employee_id, att_date)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE attendance SET status=?, check_in=?, check_out=? WHERE id=?",
            (status, check_in, check_out, existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO attendance (employee_id, att_date, status, check_in, check_out) VALUES (?,?,?,?,?)",
            (employee_id, att_date, status, check_in, check_out),
        )
    db.commit()
    flash("Attendance saved.", "success")
    return redirect(url_for("admin.attendance", date=att_date))


@admin_bp.route("/attendance/<int:att_id>/edit", methods=["POST"])
@role_required("admin")
def edit_attendance(att_id):
    db = get_db()
    status = request.form.get("status", "Present")
    check_in = request.form.get("check_in") or None
    check_out = request.form.get("check_out") or None
    db.execute(
        "UPDATE attendance SET status=?, check_in=?, check_out=? WHERE id=?",
        (status, check_in, check_out, att_id),
    )
    db.commit()
    flash("Attendance record updated.", "success")
    return redirect(request.referrer or url_for("admin.attendance"))


@admin_bp.route("/attendance/<int:att_id>/delete", methods=["POST"])
@role_required("admin")
def delete_attendance(att_id):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE id=?", (att_id,))
    db.commit()
    flash("Attendance record deleted.", "success")
    return redirect(request.referrer or url_for("admin.attendance"))


# ---------------------------------------------------------------- Leave
@admin_bp.route("/leave-requests")
@role_required("admin")
def leave_requests():
    db = get_db()
    status_filter = request.args.get("status", "").strip()
    query = """SELECT lr.*, e.full_name, e.employee_code, e.department FROM leave_requests lr
               JOIN employees e ON e.id = lr.employee_id"""
    params = []
    if status_filter:
        query += " WHERE lr.status = ?"
        params.append(status_filter)
    query += " ORDER BY lr.created_at DESC"
    rows = db.execute(query, params).fetchall()
    return render_template("admin/leave_requests.html", rows=rows, status_filter=status_filter)


@admin_bp.route("/leave-requests/<int:leave_id>/decide", methods=["POST"])
@role_required("admin")
def decide_leave(leave_id):
    db = get_db()
    decision = request.form.get("decision")
    comment = request.form.get("comment", "").strip()

    lr = db.execute("SELECT * FROM leave_requests WHERE id=?", (leave_id,)).fetchone()
    if not lr:
        abort(404)

    new_status = "Approved" if decision == "approve" else "Rejected"
    db.execute(
        "UPDATE leave_requests SET status=?, admin_comment=?, decided_at=? WHERE id=?",
        (new_status, comment, datetime.now().isoformat(timespec="seconds"), leave_id),
    )

    employee = db.execute("SELECT * FROM employees WHERE id=?", (lr["employee_id"],)).fetchone()

    if new_status == "Approved":
        # Mark attendance as Leave for each day in range
        start = datetime.strptime(lr["start_date"], "%Y-%m-%d").date()
        end = datetime.strptime(lr["end_date"], "%Y-%m-%d").date()
        cur_day = start
        while cur_day <= end:
            iso = cur_day.isoformat()
            existing = db.execute(
                "SELECT id FROM attendance WHERE employee_id=? AND att_date=?", (lr["employee_id"], iso)
            ).fetchone()
            if existing:
                db.execute("UPDATE attendance SET status='Leave' WHERE id=?", (existing["id"],))
            else:
                db.execute(
                    "INSERT INTO attendance (employee_id, att_date, status) VALUES (?,?,'Leave')",
                    (lr["employee_id"], iso),
                )
            cur_day += timedelta(days=1)
        _notify(db, lr["employee_id"], f"Your {lr['leave_type']} request was approved.", "success")
        send_leave_approved_email(employee["email"], employee["full_name"], lr["start_date"], lr["end_date"])
    else:
        _notify(db, lr["employee_id"], f"Your {lr['leave_type']} request was rejected.", "danger")
        send_leave_rejected_email(employee["email"], employee["full_name"], lr["start_date"], lr["end_date"], comment)

    db.commit()
    flash(f"Leave request {new_status.lower()}.", "success")
    return redirect(url_for("admin.leave_requests"))


# ---------------------------------------------------------------- Payroll
@admin_bp.route("/payroll")
@role_required("admin")
def payroll():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM employees WHERE role='employee' AND is_active=1 ORDER BY full_name"
    ).fetchall()
    today = date.today()
    return render_template("admin/payroll.html", employees=rows, month=today.month, year=today.year)


@admin_bp.route("/payroll/<int:emp_id>/update", methods=["POST"])
@role_required("admin")
def update_payroll(emp_id):
    db = get_db()
    basic_salary = float(request.form.get("basic_salary") or 0)
    allowance = float(request.form.get("allowance") or 0)
    deduction = float(request.form.get("deduction") or 0)

    db.execute(
        "UPDATE employees SET basic_salary=?, allowance=?, deduction=? WHERE id=?",
        (basic_salary, allowance, deduction, emp_id),
    )
    _notify(db, emp_id, "Your salary structure has been updated.", "info")
    db.commit()
    flash("Salary structure updated. Employee dashboard will reflect this immediately.", "success")
    return redirect(url_for("admin.payroll"))


@admin_bp.route("/payroll/<int:emp_id>/generate", methods=["POST"])
@role_required("admin")
def generate_payroll(emp_id):
    db = get_db()
    month = int(request.form.get("month") or date.today().month)
    year = int(request.form.get("year") or date.today().year)

    employee = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        abort(404)

    net = employee["basic_salary"] + employee["allowance"] - employee["deduction"]
    existing = db.execute(
        "SELECT id FROM payroll WHERE employee_id=? AND month=? AND year=?", (emp_id, month, year)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE payroll SET basic_salary=?, allowance=?, deduction=?, net_salary=?, generated_at=datetime('now') WHERE id=?",
            (employee["basic_salary"], employee["allowance"], employee["deduction"], net, existing["id"]),
        )
    else:
        db.execute(
            """INSERT INTO payroll (employee_id, month, year, basic_salary, allowance, deduction, net_salary)
               VALUES (?,?,?,?,?,?,?)""",
            (emp_id, month, year, employee["basic_salary"], employee["allowance"], employee["deduction"], net),
        )
    _notify(db, emp_id, f"Your salary slip for {MONTH_NAMES[month]} {year} is ready.", "success")
    db.commit()
    send_payroll_generated_email(employee["email"], employee["full_name"], f"{MONTH_NAMES[month]} {year}", net)
    flash(f"Payroll generated for {employee['full_name']} — {MONTH_NAMES[month]} {year}.", "success")
    return redirect(url_for("admin.payroll"))


@admin_bp.route("/payroll/<int:emp_id>/slip/<int:year>/<int:month>")
@role_required("admin")
def download_slip(emp_id, year, month):
    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        abort(404)
    buf = generate_salary_slip_pdf(employee, month, year, current_app.config["COMPANY_NAME"])
    filename = f"SalarySlip_{employee['employee_code']}_{MONTH_NAMES[month]}{year}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


# ---------------------------------------------------------------- Reports
@admin_bp.route("/reports")
@role_required("admin")
def reports():
    db = get_db()

    dept_rows = db.execute(
        """SELECT COALESCE(NULLIF(department,''),'Unassigned') department, COUNT(*) c
           FROM employees WHERE role='employee' AND is_active=1 GROUP BY department"""
    ).fetchall()

    last_30 = (date.today() - timedelta(days=30)).isoformat()
    attendance_rows = db.execute(
        """SELECT status, COUNT(*) c FROM attendance WHERE att_date >= ? GROUP BY status""",
        (last_30,),
    ).fetchall()

    payroll_rows = db.execute(
        """SELECT year, month, SUM(net_salary) total FROM payroll
           GROUP BY year, month ORDER BY year DESC, month DESC LIMIT 6"""
    ).fetchall()

    leave_rows = db.execute(
        """SELECT leave_type, COUNT(*) c FROM leave_requests WHERE status='Approved' GROUP BY leave_type"""
    ).fetchall()

    return render_template(
        "admin/reports.html",
        dept_rows=dept_rows, attendance_rows=attendance_rows,
        payroll_rows=payroll_rows, leave_rows=leave_rows, month_names=MONTH_NAMES
    )


@admin_bp.route("/reports/export/<report_type>/<fmt>")
@role_required("admin")
def export_report(report_type, fmt):
    db = get_db()

    if report_type == "employees":
        headers = ["Employee ID", "Name", "Department", "Job Title", "Email", "Phone", "Joining Date"]
        data = db.execute(
            "SELECT employee_code, full_name, department, job_title, email, phone, joining_date FROM employees WHERE role='employee'"
        ).fetchall()
        rows = [[r["employee_code"], r["full_name"], r["department"] or "-", r["job_title"] or "-",
                  r["email"], r["phone"] or "-", r["joining_date"] or "-"] for r in data]
        title = "Employee Report"

    elif report_type == "attendance":
        headers = ["Employee ID", "Name", "Date", "Status", "Check In", "Check Out"]
        data = db.execute(
            """SELECT e.employee_code, e.full_name, a.att_date, a.status, a.check_in, a.check_out
               FROM attendance a JOIN employees e ON e.id = a.employee_id
               ORDER BY a.att_date DESC LIMIT 500"""
        ).fetchall()
        rows = [[r["employee_code"], r["full_name"], r["att_date"], r["status"],
                  r["check_in"] or "-", r["check_out"] or "-"] for r in data]
        title = "Attendance Report"

    elif report_type == "leave":
        headers = ["Employee ID", "Name", "Type", "Start", "End", "Status"]
        data = db.execute(
            """SELECT e.employee_code, e.full_name, lr.leave_type, lr.start_date, lr.end_date, lr.status
               FROM leave_requests lr JOIN employees e ON e.id = lr.employee_id
               ORDER BY lr.created_at DESC LIMIT 500"""
        ).fetchall()
        rows = [[r["employee_code"], r["full_name"], r["leave_type"], r["start_date"], r["end_date"], r["status"]]
                 for r in data]
        title = "Leave Report"

    elif report_type == "payroll":
        headers = ["Employee ID", "Name", "Month", "Year", "Basic", "Allowance", "Deduction", "Net Salary"]
        data = db.execute(
            """SELECT e.employee_code, e.full_name, p.month, p.year, p.basic_salary, p.allowance, p.deduction, p.net_salary
               FROM payroll p JOIN employees e ON e.id = p.employee_id
               ORDER BY p.year DESC, p.month DESC LIMIT 500"""
        ).fetchall()
        rows = [[r["employee_code"], r["full_name"], MONTH_NAMES[r["month"]], r["year"],
                  f"{r['basic_salary']:,.2f}", f"{r['allowance']:,.2f}", f"{r['deduction']:,.2f}", f"{r['net_salary']:,.2f}"]
                 for r in data]
        title = "Payroll Report"
    else:
        abort(404)

    if fmt == "pdf":
        buf = generate_report_pdf(title, headers, rows, subtitle=f"Generated on {date.today().strftime('%d %b %Y')}")
        return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"{report_type}_report.pdf")
    elif fmt == "excel":
        buf = generate_report_excel(title, headers, rows)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=f"{report_type}_report.xlsx"
        )
    else:
        abort(404)


# ---------------------------------------------------------------- Notifications
@admin_bp.route("/notifications/mark-read", methods=["POST"])
@role_required("admin")
def mark_notifications_read():
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE employee_id=?", (session["user_id"],))
    db.commit()
    return redirect(request.referrer or url_for("admin.dashboard"))


# ---------------------------------------------------------------- Ask HR (employee queries)
@admin_bp.route("/queries")
@role_required("admin")
def queries():
    db = get_db()
    status_filter = request.args.get("status", "").strip()
    query = """SELECT q.*, e.full_name, e.employee_code, e.department
               FROM hr_queries q JOIN employees e ON e.id = q.employee_id"""
    params = []
    if status_filter:
        query += " WHERE q.status = ?"
        params.append(status_filter)
    query += " ORDER BY q.updated_at DESC"
    rows = db.execute(query, params).fetchall()
    return render_template("admin/queries.html", rows=rows, status_filter=status_filter)


@admin_bp.route("/queries/<int:query_id>", methods=["GET", "POST"])
@role_required("admin")
def query_detail(query_id):
    db = get_db()
    q = db.execute(
        """SELECT q.*, e.full_name, e.employee_code, e.department, e.id AS emp_id
           FROM hr_queries q JOIN employees e ON e.id = q.employee_id WHERE q.id=?""",
        (query_id,),
    ).fetchone()
    if not q:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action", "reply")
        if action == "resolve":
            db.execute("UPDATE hr_queries SET status='Resolved', updated_at=datetime('now') WHERE id=?", (query_id,))
            db.commit()
            flash("Query marked as resolved.", "success")
        else:
            message = request.form.get("message", "").strip()
            if message:
                db.execute(
                    "INSERT INTO hr_query_messages (query_id, sender_role, sender_name, message) VALUES (?,?,?,?)",
                    (query_id, "hr", session.get("full_name", "HR"), message),
                )
                db.execute(
                    "UPDATE hr_queries SET status='Replied', updated_at=datetime('now') WHERE id=?", (query_id,)
                )
                _notify(
                    db, q["emp_id"],
                    f"HR replied to your query \"{q['subject']}\". Check My Queries for details.",
                    "info", title="HR Replied to Your Query",
                )
                db.commit()
                flash("Reply sent to employee.", "success")
        return redirect(url_for("admin.query_detail", query_id=query_id))

    messages = db.execute(
        "SELECT * FROM hr_query_messages WHERE query_id=? ORDER BY created_at ASC", (query_id,)
    ).fetchall()
    return render_template("admin/query_detail.html", q=q, messages=messages)


# ---------------------------------------------------------------- Announcements
@admin_bp.route("/announcements", methods=["GET", "POST"])
@role_required("admin")
def announcements():
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        ann_date = request.form.get("announcement_date") or date.today().isoformat()

        if not title or not message:
            flash("Please provide both a title and a message.", "danger")
            return redirect(url_for("admin.announcements"))

        db.execute(
            "INSERT INTO announcements (title, message, announcement_date, created_by) VALUES (?,?,?,?)",
            (title, message, ann_date, session.get("full_name", "HR")),
        )
        notify_all_active_employees(
            db, message, ntype="announcement", title=f"📢 {title}"
        )
        db.commit()
        flash("Announcement published and sent to all employees.", "success")
        return redirect(url_for("admin.announcements"))

    rows = db.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
    return render_template("admin/announcements.html", rows=rows)


# ---------------------------------------------------------------- Recognition
@admin_bp.route("/recognize", methods=["GET", "POST"])
@role_required("admin")
def recognize():
    db = get_db()
    if request.method == "POST":
        employee_id = request.form.get("employee_id")
        message = request.form.get("message", "").strip()
        category = request.form.get("category", "").strip()

        employee = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
        if not employee or not message:
            flash("Please choose an employee and enter a recognition message.", "danger")
            return redirect(url_for("admin.recognize"))

        db.execute(
            "INSERT INTO recognitions (employee_id, message, category, given_by) VALUES (?,?,?,?)",
            (employee_id, message, category or None, session.get("full_name", "HR")),
        )
        _notify(
            db, employee_id, message,
            "recognition", title="⭐ You've Been Recognized!",
        )
        db.commit()
        flash(f"{employee['full_name']} has been recognized.", "success")
        return redirect(url_for("admin.recognize"))

    employees_list = db.execute(
        "SELECT id, full_name, employee_code, department FROM employees WHERE role='employee' AND is_active=1 ORDER BY full_name"
    ).fetchall()
    recent = db.execute(
        """SELECT r.*, e.full_name, e.employee_code FROM recognitions r
           JOIN employees e ON e.id = r.employee_id ORDER BY r.created_at DESC LIMIT 15"""
    ).fetchall()
    return render_template("admin/recognize.html", employees=employees_list, recent=recent)


# ---------------------------------------------------------------- HR Communication
@admin_bp.route("/hr-communication/send", methods=["POST"])
@role_required("admin")
def send_hr_communication():
    """Send an ad-hoc HR message to one employee or all active employees,
    via in-app notification, email, or both. Restricted to admin/HR users
    by the @role_required('admin') decorator above.
    """
    db = get_db()
    anchor = url_for("admin.dashboard") + "#hr-communication"

    to_type = request.form.get("to_type", "").strip()
    employee_id = request.form.get("employee_id", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    channel = request.form.get("channel", "").strip()

    if to_type not in ("individual", "all"):
        flash("Please choose who this message is for.", "danger")
        return redirect(anchor)
    if not subject or not message:
        flash("Please provide both a subject and a message.", "danger")
        return redirect(anchor)
    if channel not in ("notification", "email", "both"):
        flash("Please choose how to send this message.", "danger")
        return redirect(anchor)
    if to_type == "individual" and not employee_id:
        flash("Please select an employee.", "danger")
        return redirect(anchor)

    send_notification = channel in ("notification", "both")
    send_email_flag = channel in ("email", "both")

    notified_count = 0
    emailed_count = 0
    email_failed_count = 0

    if to_type == "individual":
        employee = db.execute(
            "SELECT * FROM employees WHERE id=? AND role='employee' AND is_active=1",
            (employee_id,),
        ).fetchone()
        if not employee:
            flash("Selected employee was not found or is inactive.", "danger")
            return redirect(anchor)

        recipient_label = f"{employee['full_name']} ({employee['employee_code']})"
        recipients = [employee]
    else:
        recipient_label = "All Employees"
        recipients = db.execute(
            "SELECT * FROM employees WHERE role='employee' AND is_active=1"
        ).fetchall()
        if not recipients:
            flash("There are no active employees to send this message to.", "danger")
            return redirect(anchor)

    if send_notification:
        for emp in recipients:
            _notify(db, emp["id"], message, "hr_communication", title=f"📩 {subject}")
        notified_count = len(recipients)

    if send_email_flag:
        for emp in recipients:
            if send_hr_communication_email(emp["email"], emp["full_name"], subject, message):
                emailed_count += 1
            else:
                email_failed_count += 1

    db.execute(
        """INSERT INTO hr_communications
           (recipient_type, recipient_id, recipient_label, subject, message, channel,
            notified_count, emailed_count, email_failed_count, sent_by)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            to_type,
            employee_id if to_type == "individual" else None,
            recipient_label,
            subject,
            message,
            channel,
            notified_count,
            emailed_count,
            email_failed_count,
            session.get("full_name", "HR"),
        ),
    )
    db.commit()

    if send_email_flag and email_failed_count and emailed_count == 0:
        flash(
            f"Could not send email to {recipient_label} — please check the mail server "
            f"configuration. No email was delivered.", "danger",
        )
    elif send_email_flag and email_failed_count:
        flash(
            f"Message sent, but email failed for {email_failed_count} of "
            f"{email_failed_count + emailed_count} recipient(s).", "warning",
        )
    else:
        parts = []
        if send_notification:
            parts.append(f"{notified_count} notification(s)")
        if send_email_flag:
            parts.append(f"{emailed_count} email(s)")
        flash(f"Message sent to {recipient_label} — {', '.join(parts)} delivered.", "success")

    return redirect(anchor)
