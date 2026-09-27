"""
routes/income.py - The Income Recording System.

Every route here is protected with @login_required, and every database
lookup is filtered by current_user.id. That combination is what keeps
financial data private.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import IncomeRecord
from services import finance_service as fin
from services.validators import (parse_amount, parse_date, clean_text,
                                 parse_month, current_month)

income_bp = Blueprint("income", __name__, url_prefix="/income")


@income_bp.route("")
@login_required
def index():
    """Income list for a chosen month (defaults to the current month)."""
    month, error = _month_from_request()
    if error:
        flash(error, "danger")
        return redirect(url_for("income.index"))

    records = fin.income_records(current_user.id, month)

    return render_template(
        "income/list.html",
        month=month,
        records=records,
        total=fin.total_income(current_user.id, month),
        by_type=fin.income_by_type(current_user.id, month),
        income_types=fin.INCOME_TYPES,
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )


@income_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        source, source_error = clean_text(request.form.get("source"),
                                          "Income source", 120)
        income_type = (request.form.get("income_type") or "").strip()
        amount, amount_error = parse_amount(request.form.get("amount"), "Amount")
        income_date, date_error = parse_date(request.form.get("income_date"),
                                             "Income date")
        notes = (request.form.get("notes") or "").strip()[:1000]

        errors = [e for e in (source_error, amount_error, date_error) if e]

        # Only accept an income type we actually offer
        valid_types = {value for value, _ in fin.INCOME_TYPES}
        if income_type not in valid_types:
            errors.append("Please choose a valid income type.")
            income_type = "other"

        # A date in the far future is almost always a typing mistake
        if income_date and income_date.year > 2100:
            errors.append("Income date looks wrong (year is too far ahead).")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("income/add.html",
                                   income_types=fin.INCOME_TYPES,
                                   form=request.form)

        record = IncomeRecord(
            user_id=current_user.id,          # ownership - always the logged-in user
            source=source,
            income_type=income_type,
            amount=amount,
            income_date=income_date,
            notes=notes or None,
        )
        db.session.add(record)
        db.session.commit()

        flash(f"Income of {amount} added successfully.", "success")
        return redirect(url_for("income.index",
                                month=income_date.strftime("%Y-%m")))

    return render_template("income/add.html",
                           income_types=fin.INCOME_TYPES, form={})


@income_bp.post("/<int:record_id>/delete")
@login_required
def delete(record_id):
    # NOTE: filtering by BOTH id and user_id is essential. Without the
    # user_id part, anyone could delete anyone else's income by
    # guessing the id in the URL.
    record = IncomeRecord.query.filter_by(
        id=record_id, user_id=current_user.id).first()

    if not record:
        flash("That income record was not found in your account.", "danger")
        return redirect(url_for("income.index"))

    month = record.income_date.strftime("%Y-%m")
    db.session.delete(record)
    db.session.commit()

    flash("Income record deleted.", "success")
    return redirect(url_for("income.index", month=month))


def _month_from_request():
    """Read ?month=YYYY-MM from the URL and validate it.

    Falls back to the current month when nothing is given.
    """
    raw = (request.args.get("month") or "").strip()
    if not raw:
        return current_month(), None
    return parse_month(raw, "Month")
