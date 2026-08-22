from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db
from utils.auth_helper import is_valid_email, is_valid_password
from utils.email_helper import send_welcome_email
from utils.notify_helper import notify

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("admin.dashboard" if session.get("role") == "admin" else "employee.dashboard"))
    return redirect(url_for("auth.signin"))


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        employee_code = request.form.get("employee_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "employee")

        errors = []
        if not employee_code:
            errors.append("Employee ID is required.")
        if not full_name:
            errors.append("Full name is required.")
        if not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        if not is_valid_password(password):
            errors.append("Password must be at least 8 characters long.")
        if password != confirm_password:
            errors.append("Password and confirm password do not match.")
        if role not in ("employee", "admin"):
            errors.append("Please select a valid role.")

        db = get_db()
        if not errors:
            existing_email = db.execute("SELECT id FROM employees WHERE email = ?", (email,)).fetchone()
            if existing_email:
                errors.append("An account with this email already exists.")
            existing_code = db.execute(
                "SELECT id FROM employees WHERE employee_code = ?", (employee_code,)
            ).fetchone()
            if existing_code:
                errors.append("This Employee ID is already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/signup.html", form=request.form)

        db.execute(
            """INSERT INTO employees
               (employee_code, full_name, email, password_hash, role, joining_date, welcomed)
               VALUES (?,?,?,?,?,?,0)""",
            (employee_code, full_name, email, generate_password_hash(password), role, date.today().isoformat()),
        )
        db.commit()
        send_welcome_email(email, full_name, employee_code)
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("auth.signin"))

    return render_template("auth/signup.html", form={})


@auth_bp.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM employees WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "danger")
            return render_template("auth/signin.html", email=email)

        if not user["is_active"]:
            flash("This account has been deactivated. Contact HR.", "danger")
            return render_template("auth/signin.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        session["employee_code"] = user["employee_code"]

        if not user["welcomed"]:
            notify(
                db, user["id"],
                f"Welcome, {user['full_name']}! We're happy to have you with us. Wishing you a "
                f"successful and rewarding journey with our organization!",
                ntype="welcome",
                title="👋 Welcome to the Team!",
            )
            db.execute("UPDATE employees SET welcomed=1 WHERE id=?", (user["id"],))
            db.commit()

        flash(f"Welcome back, {user['full_name']}!", "success")
        next_url = request.args.get("next")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("admin.dashboard" if user["role"] == "admin" else "employee.dashboard"))

    return render_template("auth/signin.html", email="")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM employees WHERE email = ?", (email,)).fetchone()
        # Always show a generic success message to avoid leaking which emails are registered.
        if user:
            flash("If that email is registered, password reset instructions have been sent.", "success")
        else:
            flash("If that email is registered, password reset instructions have been sent.", "success")
        return redirect(url_for("auth.signin"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.signin"))
