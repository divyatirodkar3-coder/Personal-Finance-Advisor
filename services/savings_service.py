"""
services/savings_service.py - Savings Tracking.

WHERE DO THE NUMBERS COME FROM?
-------------------------------
Nothing is typed in by the user for the savings figure. It is always
calculated from the database:

    savings = total income - total expenses

The user only chooses a TARGET ("I want to save 5000 a month").
Everything else is real data.

WHY IS THE STATUS TIME-AWARE?
-----------------------------
Saving 50% of your goal on the 15th is fine. Saving only 50% on the
30th is not. So we compare against how far through the month we are,
not just against a flat percentage.
"""

from calendar import monthrange
from datetime import date

from extensions import db
from models import SavingsProgress
from services import finance_service as fin

# If you have reached this share of the month's expected progress,
# you count as "on track".
ON_TRACK_RATIO = 1.0


def days_in_month(month):
    """How many days does 'YYYY-MM' have? Handles leap years."""
    year, mon = int(month[:4]), int(month[5:7])
    return monthrange(year, mon)[1]


def month_progress(month):
    """How far through this month are we? Returns 0.0 to 1.0.

    past month    -> 1.0  (it is finished)
    current month -> day / total days
    future month  -> 0.0  (nothing has happened yet)
    """
    today = date.today()
    this_month = today.strftime("%Y-%m")

    if month < this_month:
        return 1.0
    if month > this_month:
        return 0.0
    return min(today.day / days_in_month(month), 1.0)


def savings_status(saved, target, progress):
    """Decide: achieved / on_track / behind / no_target."""
    if not target or target <= 0:
        return "no_target"
    if saved >= target:
        return "achieved"
    if saved >= target * progress * ON_TRACK_RATIO:
        return "on_track"
    return "behind"


STATUS_WORDS = {
    "achieved": "Goal achieved",
    "on_track": "On track",
    "behind": "Behind target",
    "no_target": "No goal set",
}


def compute(user_id, month, target=None):
    """Work out the savings numbers for one month."""
    if target is None:
        target = _stored_target(user_id, month)

    income = fin.total_income(user_id, month)
    expenses = fin.total_expenses(user_id, month)
    saved = round(income - expenses, 2)

    progress = month_progress(month)
    status = savings_status(saved, target, progress)
    percent = round((saved / target) * 100, 1) if target and target > 0 else 0.0

    # How much still needed to hit the goal
    remaining = round(max(target - saved, 0), 2)

    return {
        "month": month,
        "income": income,
        "expenses": expenses,
        "saved": saved,
        "target": float(target or 0),
        "remaining": remaining,
        "percent": percent,
        "progress": round(progress * 100, 1),
        "status": status,
        "status_word": STATUS_WORDS[status],
    }


def profile_goal(user_id):
    """The default savings goal taken from the user profile."""
    from models import User
    user = db.session.get(User, user_id)
    return float(user.savings_goal or 0) if user else 0.0


def _stored_target(user_id, month):
    """The target saved for a month, or the profile goal as a fallback.

    Note the `is not None` test. A plain `if row.target_amount:` would be
    False when the user deliberately set the target to 0, and we would
    wrongly fall back to the profile goal. Zero means "no goal this
    month", and it must stay zero.
    """
    row = SavingsProgress.query.filter_by(user_id=user_id, month=month).first()
    if row is not None and row.target_amount is not None:
        return float(row.target_amount)
    return profile_goal(user_id)


def history(user_id, limit=12):
    """Stored savings records, newest month first."""
    rows = (SavingsProgress.query
            .filter_by(user_id=user_id)
            .order_by(SavingsProgress.month.desc())
            .limit(limit).all())
    return rows


def overall(user_id):
    """All-time summary across every month that has data."""
    months = fin.months_with_data(user_id)
    achieved = 0
    total_saved = 0.0
    total_target = 0.0

    for month in months:
        result = compute(user_id, month)
        total_saved += result["saved"]
        total_target += result["target"]
        if result["status"] == "achieved":
            achieved += 1

    return {
        "months": len(months),
        "achieved": achieved,
        "total_saved": round(total_saved, 2),
        "total_target": round(total_target, 2),
        "rate": round((achieved / len(months)) * 100, 1) if months else 0.0,
    }


def sync_month(user_id, month):
    """Create or update the savings_progress row for one month.

    This is what fills the savings_progress table with real records
    instead of leaving it empty.
    """
    row = SavingsProgress.query.filter_by(user_id=user_id, month=month).first()
    is_new = row is None
    if is_new:
        row = SavingsProgress(user_id=user_id, month=month)
        db.session.add(row)

    # For a brand new month we take the profile goal directly. We do NOT
    # let the database decide, because SQLAlchemy autoflush would insert
    # the new row with the column default of 0 before we could read it.
    if is_new:
        target = profile_goal(user_id)
    else:
        target = float(row.target_amount or 0)

    result = compute(user_id, month, target=target)

    row.target_amount = result["target"]
    row.saved_amount = result["saved"]
    row.status = result["status"]
    db.session.commit()
    return row, result


def sync_all(user_id):
    """Fill in savings records for every month that has data."""
    months = fin.months_with_data(user_id)
    results = [sync_month(user_id, month)[1] for month in months]
    return results


