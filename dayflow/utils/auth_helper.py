import re
from functools import wraps
from flask import session, redirect, url_for, flash, request


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    return bool(email) and bool(EMAIL_REGEX.match(email))


def is_valid_password(password):
    """Password must be at least 8 characters."""
    return bool(password) and len(password) >= 8


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.signin", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in to continue.", "warning")
                return redirect(url_for("auth.signin", next=request.path))
            if session.get("role") not in roles:
                flash("You do not have permission to access that page.", "danger")
                if session.get("role") == "admin":
                    return redirect(url_for("admin.dashboard"))
                return redirect(url_for("employee.dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")
