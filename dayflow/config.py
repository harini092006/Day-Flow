import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("DAYFLOW_SECRET_KEY", "dayflow-dev-secret-key-change-in-production")
    DATABASE = os.path.join(BASE_DIR, "dayflow.db")

    UPLOAD_FOLDER_PROFILE = os.path.join(BASE_DIR, "static", "uploads", "profile")
    UPLOAD_FOLDER_DOCUMENTS = os.path.join(BASE_DIR, "static", "uploads", "documents")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

    SESSION_PERMANENT = False

    COMPANY_NAME = "DayFlow Technologies Pvt. Ltd."
