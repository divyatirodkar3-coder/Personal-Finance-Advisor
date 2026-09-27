"""
config.py - Configuration settings for the Personal Finance Advisor Bot.

Simple idea: this file is the ONE place that knows about passwords, API keys
and the database address. The rest of the app never needs to know them.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

# Load the .env file so we can read SECRET_KEY, GEMINI_API_KEY etc.
load_dotenv()

# Folder where this file lives (the project root)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Settings shared by the whole app."""

    # --- Security -------------------------------------------------------
    # SECRET_KEY is like a signature stamp on your login cookie.
    # If someone forges or edits the cookie, Flask rejects it.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # --- Database -------------------------------------------------------
    # "sqlite:///finance.db" means: a SQLite file named finance.db
    # Flask automatically places it inside the project's instance/ folder.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI", "sqlite:///finance.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Session / cookie security -------------------------------------
    # HttpOnly = JavaScript cannot read the cookie (blocks XSS attacks)
    SESSION_COOKIE_HTTPONLY = True
    # SameSite = protects against cross-site request forgery
    SESSION_COOKIE_SAMESITE = "Lax"
    # Log the user out after 7 days of inactivity
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # --- Google Gemini AI ----------------------------------------------
    # Read from .env - never hard-coded in the app code.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    # --- Upload / misc -------------------------------------------------
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB limit


class DevelopmentConfig(Config):
    """Used while we are building the project."""

    DEBUG = True


class TestingConfig(Config):
    """Used by the automated tests so they never touch real user data."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

    # TESTING ONLY. The real app hashes passwords with scrypt, which is
    # deliberately slow (about 1-2 seconds per hash). That is the correct
    # choice for production, but every test that registers or logs in a
    # user would pay for it, and the whole suite would take minutes.
    # Werkzeug reads this setting as the default method for
    # generate_password_hash(), so a cheap iteration count keeps the
    # hashing REAL (still salted, still one-way, still verified the same
    # way) while making the suite fast. DevelopmentConfig and production
    # are untouched and keep the strong default.
    SECURITY_PASSWORD_HASH = "pbkdf2:sha256:1000"
