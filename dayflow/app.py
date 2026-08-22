import os
from flask import Flask, redirect, url_for, session

from config import Config
from database import close_db, init_db, get_db
from blueprints.auth import auth_bp
from blueprints.admin import admin_bp
from blueprints.employee import employee_bp
from utils.notify_helper import check_and_send_auto_notifications


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER_PROFILE"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER_DOCUMENTS"], exist_ok=True)

    app.teardown_appcontext(close_db)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)

    @app.route("/")
    def home():
        if "user_id" in session:
            return redirect(url_for("admin.dashboard" if session.get("role") == "admin" else "employee.dashboard"))
        return redirect(url_for("auth.signin"))

    @app.context_processor
    def inject_globals():
        db = get_db()
        unread_count = 0
        recent_notifications = []
        if "user_id" in session:
            if session.get("role") == "employee":
                emp_row = db.execute(
                    "SELECT * FROM employees WHERE id=?", (session["user_id"],)
                ).fetchone()
                if emp_row:
                    check_and_send_auto_notifications(db, emp_row)
            row = db.execute(
                "SELECT COUNT(*) c FROM notifications WHERE employee_id=? AND is_read=0",
                (session["user_id"],),
            ).fetchone()
            unread_count = row["c"] if row else 0
            recent_notifications = db.execute(
                "SELECT * FROM notifications WHERE employee_id=? ORDER BY created_at DESC LIMIT 6",
                (session["user_id"],),
            ).fetchall()
        return dict(
            company_name=app.config["COMPANY_NAME"],
            unread_notifications=unread_count,
            recent_notifications=recent_notifications,
        )

    @app.errorhandler(404)
    def not_found(e):
        return "<h1>404 — Page Not Found</h1><p><a href='/'>Go home</a></p>", 404

    @app.errorhandler(413)
    def too_large(e):
        return "<h1>File too large</h1><p>Please upload a file under 8 MB.</p>", 413

    init_db(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
