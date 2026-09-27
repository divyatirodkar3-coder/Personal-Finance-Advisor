"""
routes/savings.py - Savings Tracking page.

The savings FIGURE is never typed in. It is always calculated as
income - expenses from the database. The user only sets a TARGET.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import SavingsProgress
from services import finance_service as fin
from services import savings_service as ssvc
from services.validators import parse_amount, parse_month, current_month

savings_bp = Blueprint("savings", __name__, url_prefix="/savings")


@savings_bp.route("", methods=["GET", "POST"])
@login_required
def index():
    # An empty month in the URL is normal - it just means "this month".
    raw_month = (request.args.get("month") or "").strip()
    if raw_month:
        month, month_error = parse_month(raw_month, "Month")
        if month_error:
            flash(month_error, "danger")
            return redirect(url_for("savings.index"))
    else:
        month = current_month()

    # ---- set a target for this month (optional) ----
    if request.method == "POST":
        amount, amount_error = parse_amount(
            request.form.get("target"), "Savings target", allow_zero=True)
        if amount_error:
            flash(amount_error, "danger")
        else:
            row = SavingsProgress.query.filter_by(
                user_id=current_user.id, month=month).first()
            if row is None:
                row = SavingsProgress(user_id=current_user.id, month=month)
                db.session.add(row)
            row.target_amount = amount
            db.session.commit()
            flash(f"Savings target for {month} set to {amount}.", "success")
            return redirect(url_for("savings.index", month=month))

    # Keep the savings_progress table filled with real records
    ssvc.sync_month(current_user.id, month)

    summary = ssvc.compute(current_user.id, month)
    rows = ssvc.history(current_user.id)
    totals = ssvc.overall(current_user.id)

    return render_template(
        "savings.html",
        summary=summary,
        rows=rows,
        totals=totals,
        month=month,
        months=fin.months_with_data(current_user.id),
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )


@savings_bp.post("/refresh")
@login_required
def refresh():
    """Rebuild the savings record for every month that has data."""
    count = len(ssvc.sync_all(current_user.id))
    flash(f"Savings records refreshed for {count} month(s).", "success")
    return redirect(url_for("savings.index"))


@savings_bp.post("/goal")
@login_required
def set_profile_goal():
    """Update the savings goal in the user profile (used by all months)."""
    amount, amount_error = parse_amount(
        request.form.get("goal"), "Savings goal", allow_zero=True)
    if amount_error:
        flash(amount_error, "danger")
    else:
        current_user.savings_goal = amount
        db.session.commit()
        flash(f"Monthly savings goal updated to {amount}.", "success")
    return redirect(url_for("savings.index"))
