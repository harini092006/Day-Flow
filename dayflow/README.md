# DayFlow — Human Resource Management System

*Every workday, perfectly aligned.*

DayFlow is a full-stack HRMS built with **Flask**, **SQLite**, and vanilla **HTML/CSS/JS**, styled in a Sage Green + Cream corporate theme. It covers authentication, employee management, attendance, leave, payroll, reports and notifications for both employees and HR/Admin users.

---

## ✨ Features

- **Authentication** — Sign up, sign in, forgot password, role-based sessions (Employee / HR-Admin), hashed passwords.
- **Dashboards** — Live, database-driven stats for both employee and admin roles.
- **Employee Management** — Full CRUD, search, department filters, profile photos, documents.
- **Attendance** — Employee check-in/check-out, daily/weekly/monthly history; HR can view, mark, edit and delete records for anyone. "Present Today" always reflects the live count.
- **Leave & Time-Off** — Employees apply for leave; HR approves/rejects with comments; approved leave auto-marks attendance as "Leave".
- **Payroll** — HR updates salary structure and generates monthly salary slips; employees view salary and download professional PDF payslips.
- **Reports** — Attendance, leave, payroll and employee reports with simple visual charts, exportable as PDF or Excel.
- **Notifications** — In-app bell notifications for leave decisions, payroll generation and new accounts.
- **Documents** — Upload/preview Aadhaar, resume, offer letter and certificates (PDF/PNG/JPG).

---

## 🗂 Project Structure

```
DayFlow-HRMS/
├── app.py                  # App factory & route registration
├── config.py                # App configuration
├── database.py               # SQLite connection & schema
├── requirements.txt
├── blueprints/
│   ├── auth.py               # Sign up / sign in / logout
│   ├── admin.py               # HR/Admin routes
│   └── employee.py            # Employee routes
├── utils/
│   ├── auth_helper.py          # Decorators & validation
│   ├── email_helper.py          # Email notification stubs
│   └── report_helper.py         # PDF / Excel generation
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── uploads/{profile,documents}/
└── templates/
    ├── base.html
    ├── auth/
    ├── admin/
    └── employee/
```

---

## 🚀 Getting Started (VS Code / Local)

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**:
   ```bash
   python app.py
   ```
   The database (`dayflow.db`) and upload folders are created automatically on first run, along with a seeded HR/Admin account.

4. **Open** `http://127.0.0.1:5000` in your browser.

---

## 🔑 Demo Login

| Role  | Email               | Password   |
|-------|----------------------|------------|
| Admin | admin@dayflow.com    | Admin@123  |

You can also sign up new Employee or HR/Admin accounts from the **Sign Up** page.

---

## 🧱 Tech Stack

- **Backend:** Python, Flask, Flask Blueprints
- **Database:** SQLite (raw `sqlite3`, no ORM)
- **Frontend:** HTML5, CSS3 (custom design system), vanilla JavaScript
- **Auth:** Werkzeug password hashing, Flask sessions
- **Documents:** ReportLab (PDF salary slips & reports), openpyxl (Excel exports)

---

## 📝 Notes

- Email sending is stubbed to the console by default (see `utils/email_helper.py`). Set `DAYFLOW_SMTP_HOST`, `DAYFLOW_SMTP_USER`, `DAYFLOW_SMTP_PASSWORD` environment variables to enable real SMTP delivery.
- Default leave balance is a fixed 24 days/year for demo purposes — adjust in `blueprints/employee.py` if your organization uses a different policy.
- For production use, set a strong `DAYFLOW_SECRET_KEY` environment variable and switch off Flask debug mode.
