"""
routes/analysis.py - Spending Analysis and Overspending Detection page.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from services import finance_service as fin
from services import analysis_service as asvc
from services.validators import parse_month, current_month

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


def _month_from_request():
    raw = (request.args.get("month") or "").strip()
    if not raw:
        return current_month(), None
    return parse_month(raw, "Month")


@analysis_bp.route("")
@login_required
def index():
    month, error = _month_from_request()
    if error:
        flash(error, "danger")
        return redirect(url_for("analysis.index"))

    data = asvc.analyse(current_user.id, month)

    return render_template(
        "analysis.html",
        data=data,
        month=month,
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )
