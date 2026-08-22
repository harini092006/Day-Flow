"""
Email helper for DayFlow HRMS.

This module centralizes all outgoing email logic. In this demo build, emails
are logged to the console instead of actually being sent, so the project runs
out of the box without SMTP credentials. To enable real email delivery, wire
`_send_email` to an SMTP provider (e.g. smtplib, SendGrid, SES) using
environment variables for credentials.
"""

import smtplib
import os
from email.message import EmailMessage

SMTP_HOST = os.environ.get("DAYFLOW_SMTP_HOST")
SMTP_PORT = os.environ.get("DAYFLOW_SMTP_PORT", 587)
SMTP_USER = os.environ.get("DAYFLOW_SMTP_USER")
SMTP_PASSWORD = os.environ.get("DAYFLOW_SMTP_PASSWORD")
FROM_ADDRESS = os.environ.get("DAYFLOW_FROM_EMAIL", "no-reply@dayflow.com")


def _send_email(to_address, subject, body):
    """Send an email if SMTP is configured, otherwise log to console."""
    if not SMTP_HOST or not SMTP_USER:
        print(f"[DayFlow Mailer] (console mode) To: {to_address} | Subject: {subject}\n{body}\n")
        return True
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = FROM_ADDRESS
        msg["To"] = to_address
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT)) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[DayFlow Mailer] Failed to send email to {to_address}: {exc}")
        return False


def send_welcome_email(to_address, full_name, employee_code):
    subject = "Welcome to DayFlow HRMS"
    body = (
        f"Hi {full_name},\n\n"
        f"Your DayFlow account has been created successfully.\n"
        f"Employee ID: {employee_code}\n\n"
        f"You can now sign in and access your dashboard.\n\n"
        f"— The DayFlow Team"
    )
    return _send_email(to_address, subject, body)


def send_leave_approved_email(to_address, full_name, start_date, end_date):
    subject = "Leave Request Approved"
    body = (
        f"Hi {full_name},\n\n"
        f"Your leave request from {start_date} to {end_date} has been approved.\n\n"
        f"— The DayFlow Team"
    )
    return _send_email(to_address, subject, body)


def send_leave_rejected_email(to_address, full_name, start_date, end_date, reason=""):
    subject = "Leave Request Update"
    body = (
        f"Hi {full_name},\n\n"
        f"Your leave request from {start_date} to {end_date} was not approved.\n"
        f"{('Reason: ' + reason) if reason else ''}\n\n"
        f"— The DayFlow Team"
    )
    return _send_email(to_address, subject, body)


def send_hr_communication_email(to_address, full_name, subject, message):
    """Send an ad-hoc HR communication (see admin HR Communication box)."""
    body = (
        f"Hi {full_name},\n\n"
        f"{message}\n\n"
        f"— HR Team, DayFlow"
    )
    return _send_email(to_address, subject, body)


def send_payroll_generated_email(to_address, full_name, month_label, net_salary):
    subject = "Salary Slip Generated"
    body = (
        f"Hi {full_name},\n\n"
        f"Your salary slip for {month_label} has been generated.\n"
        f"Net Salary: Rs. {net_salary:,.2f}\n\n"
        f"— The DayFlow Team"
    )
    return _send_email(to_address, subject, body)
