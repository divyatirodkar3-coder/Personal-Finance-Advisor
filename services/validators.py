"""
services/validators.py - Input validation helpers.

WHY A SEPARATE FILE?
--------------------
Every form in this app needs the same checks: is the amount a real
number? is it negative? is the date valid? Writing these once and
reusing them keeps the rules identical everywhere and stops crashes.

HOW IT WORKS
------------
Each function returns TWO values:  (good_value, error_message)
  - If everything is fine -> (the_clean_value, None)
  - If something is wrong   -> (None, "a friendly message")

The route then does:   value, error = parse_amount(form["amount"])
                       if error: flash(error); return redirect(...)
"""

import re
from datetime import date, datetime

# A simple, practical email check
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# Largest amount we will accept (guards against silly typing)
MAX_AMOUNT = 99_999_999


def parse_amount(raw, field="Amount", allow_zero=False):
    """Turn form text into a clean positive number, or return an error."""
    text = (raw or "").strip().replace(",", "")

    if text == "":
        return None, f"{field} is required."
    try:
        value = float(text)
    except (ValueError, TypeError):
        return None, f"{field} must be a number (letters are not allowed)."

    if value != value or value in (float("inf"), float("-inf")):
        return None, f"{field} must be a real number."
    if value < 0:
        return None, f"{field} cannot be negative."
    if value == 0 and not allow_zero:
        return None, f"{field} must be greater than zero."
    if value > MAX_AMOUNT:
        return None, f"{field} is too large."
    return round(value, 2), None


def parse_date(raw, field="Date"):
    """Turn 'YYYY-MM-DD' text into a real date object, or return an error.

    Always returns a TUPLE:  (date_or_None, error_or_None)
    """
    text = (raw or "").strip()
    if text == "":
        return None, f"{field} is required."
    try:
        return datetime.strptime(text, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"{field} is not a valid date. Use YYYY-MM-DD."


def parse_month(raw, field="Month"):
    """Turn 'YYYY-MM' text into a 'YYYY-MM' string, or return an error."""
    text = (raw or "").strip()
    if text == "":
        return None, f"{field} is required."
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", text):
        return None, f"{field} must look like YYYY-MM (for example 2026-09)."
    return text, None


def current_month():
    """Today's month as 'YYYY-MM'."""
    return date.today().strftime("%Y-%m")


def clean_text(raw, field="Field", max_len=150, required=True):
    """Trim a text field and check its length."""
    text = (raw or "").strip()
    if text == "" and required:
        return None, f"{field} is required."
    if len(text) > max_len:
        return None, f"{field} must be under {max_len} characters."
    return text, None


def is_valid_email(email):
    """True if the text looks like a real email address."""
    return bool(email and EMAIL_PATTERN.match(email.strip()))


def normalise_email(email):
    """Emails are not case sensitive for our purposes - lower them."""
    return (email or "").strip().lower()
