"""Application configuration, read from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _database_uri():
    """Return the SQLAlchemy database URI.

    Locally DATABASE_URL is unset and we fall back to a SQLite file, so the
    project runs with no database server installed. On Railway DATABASE_URL is
    provided by the managed MySQL service. Railway hands out URLs starting with
    mysql://, which SQLAlchemy cannot drive on its own, so the PyMySQL driver is
    named explicitly.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///" + os.path.join(BASE_DIR, "aliyot.db")
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # Admin dashboard, phase 4. Two levels behind the same login screen:
    # ADMIN changes things, VIEWER only reads. Either password empty means that
    # level cannot be logged into at all, which is the safe default.
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "")

    # How long after placing a bid the bidder may still cancel it themselves,
    # from the same browser. Long enough to catch a typo, short enough that
    # nobody can hold a high bid over the room and withdraw it at the end.
    SELF_CANCEL_MINUTES = int(os.environ.get("SELF_CANCEL_MINUTES", "10"))

    # Outgoing email. Not used yet, phase 3.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
