"""
routes/dashboard.py - The main dashboard.

This page brings every module together:
  income overview, expense breakdown, budget performance,
  savings progress, spending analysis, monthly summary and
  the AI recommendation display.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import AIInsight
from services import finance_service as fin
from services import analysis_service as asvc
from services import savings_service as ssvc
from services import ai_service as ai
from services.validators import parse_month, current_month

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    raw = (request.args.get("month") or "").strip()
    if raw:
        month, error = parse_month(raw, "Month")
        if error:
            flash(error, "danger")
            return redirect(url_for("dashboard.index"))
    else:
        month = current_month()

    uid = current_user.id

    # Keep the analytics table up to date whenever the page is opened.
    data = asvc.analyse(uid, month)
    ssvc.sync_month(uid, month)

    # The most recent AI advice, if any has been generated.
    latest_ai = (AIInsight.query
                 .filter_by(user_id=uid)
                 .order_by(AIInsight.created_at.desc())
                 .first())

    # Recent transactions for the table at the bottom of the page.
    recent = []
    for row in fin.income_records(uid, month)[:4]:
        recent.append({
            "kind": "income", "date": row.income_date,
            "label": row.source, "category": row.income_type,
            "amount": float(row.amount),
        })
    for row in fin.expense_records(uid, month)[:4]:
        recent.append({
            "kind": "expense", "date": row.expense_date,
            "label": row.title,
            "category": row.category.name if row.category else "Uncategorised",
            "amount": float(row.amount),
        })
    recent.sort(key=lambda item: item["date"], reverse=True)
    recent = recent[:8]

    return render_template(
        "dashboard.html",
        month=month,
        income=fin.total_income(uid, month),
        expenses=fin.total_expenses(uid, month),
        savings=fin.total_savings(uid, month),
        health=data["health"],
        overspent=data["overspent"],
        daily=data["daily"],
        insights=data["insights"],
        savings_summary=ssvc.compute(uid, month),
        ai_configured=ai.is_configured(),
        latest_ai=latest_ai,
        recent=recent,
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )
