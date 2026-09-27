"""
routes/api.py - Small JSON API that feeds the dashboard charts.

WHY A SEPARATE API FILE?
------------------------
JavaScript cannot read the server's Python variables. These routes turn
the real database numbers into simple JSON that Chart.js can draw.

Every route is protected, and every query is filtered by the logged-in
user, exactly like the page routes.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from services import finance_service as fin
from services import analysis_service as asvc
from services import budget_service as bsvc
from services.validators import parse_month, current_month

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _month():
    raw = (request.args.get("month") or "").strip()
    if not raw:
        return current_month()
    month, error = parse_month(raw, "Month")
    return current_month() if error else month


def _last_n_months(end_month, count):
    """Build a list of the last N months ending at end_month, oldest first."""
    months = [end_month]
    for _ in range(count - 1):
        months.append(fin.previous_month(months[-1]))
    return list(reversed(months))


@api_bp.route("/summary")
@login_required
def summary():
    """Headline numbers for the dashboard cards."""
    month = _month()
    uid = current_user.id
    return jsonify({
        "month": month,
        "income": fin.total_income(uid, month),
        "expenses": fin.total_expenses(uid, month),
        "savings": fin.total_savings(uid, month),
        "daily": asvc.avg_daily_spend(uid, month),
        "health": asvc.health_score(uid, month),
        "overspent": [row["name"] for row in asvc.overspending(uid, month)],
    })


@api_bp.route("/expenses/by-category")
@login_required
def by_category():
    """Category-wise expense analytics (used by the doughnut chart)."""
    month = _month()
    uid = current_user.id
    breakdown = fin.category_breakdown(uid, month)
    colors = fin.category_colors(uid)
    return jsonify({
        "month": month,
        "labels": list(breakdown.keys()),
        "values": [round(v, 2) for v in breakdown.values()],
        "colors": [colors.get(name, "#64748b") for name in breakdown],
        "total": round(sum(breakdown.values()), 2),
    })


@api_bp.route("/budget-progress")
@login_required
def budget_progress():
    """Planned versus actual per category (used by the bar chart)."""
    month = _month()
    rows = bsvc.category_progress(current_user.id, month)
    return jsonify({
        "month": month,
        "labels": [r["name"] for r in rows],
        "planned": [round(r["planned"], 2) for r in rows],
        "spent": [round(r["spent"], 2) for r in rows],
        "status": [r["status"] for r in rows],
    })


@api_bp.route("/trend")
@login_required
def trend():
    """Income versus expenses over the last N months (line chart)."""
    end_month = _month()
    try:
        count = int(request.args.get("months", 6))
    except (TypeError, ValueError):
        count = 6
    count = max(2, min(count, 12))

    months = _last_n_months(end_month, count)
    uid = current_user.id
    return jsonify({
        "months": months,
        "income": [fin.total_income(uid, m) for m in months],
        "expenses": [fin.total_expenses(uid, m) for m in months],
        "savings": [fin.total_savings(uid, m) for m in months],
    })


@api_bp.route("/recent")
@login_required
def recent():
    """The five most recent transactions for the dashboard table."""
    month = _month()
    uid = current_user.id
    incomes = fin.income_records(uid, month)[:5]
    expenses = fin.expense_records(uid, month)[:5]

    items = []
    for row in incomes:
        items.append({
            "kind": "income",
            "date": row.income_date.isoformat(),
            "label": row.source,
            "category": row.income_type,
            "amount": float(row.amount),
        })
    for row in expenses:
        items.append({
            "kind": "expense",
            "date": row.expense_date.isoformat(),
            "label": row.title,
            "category": row.category.name if row.category else "Uncategorised",
            "amount": float(row.amount),
        })
    items.sort(key=lambda item: item["date"], reverse=True)

    return jsonify({"month": month, "items": items[:8]})
