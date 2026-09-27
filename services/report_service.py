"""
services/report_service.py - Monthly Financial Summaries.

WHAT IS A MONTHLY REPORT?
-------------------------
A frozen summary of one month: income, expenses, savings, per-category
spending, budget performance and any overspending.

WHY FREEZE IT IF WE CAN ALWAYS RECALCULATE?
--------------------------------------------
Because a report answers "how was March?" even if you have since added
or deleted a March expense. The report remembers what it saw at the
time, which is what a real statement does.

The stored numbers always come from the same calculation functions the
dashboard uses, so the two can never disagree.
"""

from datetime import date

from extensions import db
from models import MonthlyReport
from services import finance_service as fin
from services import analysis_service as asvc
from services import budget_service as bsvc
from services import savings_service as ssvc

def build_report(user_id, month):
    """Build a complete report dictionary for one month (not saved yet)."""
    income = fin.total_income(user_id, month)
    expenses = fin.total_expenses(user_id, month)
    saved = fin.total_savings(user_id, month)
    breakdown = fin.category_breakdown(user_id, month)

    savings_rate = round((saved / income) * 100, 2) if income > 0 else 0.0

    budget_rows = bsvc.category_progress(user_id, month)
    budget_total = round(sum(row["planned"] for row in budget_rows), 2)
    budget_used = round(sum(min(row["spent"], row["planned"])
                            for row in budget_rows), 2)
    if not budget_total:
        # No category budgets: fall back to the overall budget
        whole = bsvc.overall_budget(user_id, month)
        if whole:
            budget_total = float(whole.planned_amount or 0)
            budget_used = round(min(expenses, budget_total), 2)

    over = asvc.overspending(user_id, month)
    health = asvc.health_score(user_id, month)
    start, end = fin.month_bounds(month)
    days = (end - start).days + 1

    # spending ranked biggest first
    ranked = sorted(breakdown.items(), key=lambda item: item[1], reverse=True)
    top_category = ranked[0][0] if ranked else None
    top_amount = ranked[0][1] if ranked else 0.0

    return {
        "month": month,
        "start": start,
        "end": end,
        "days": days,
        "income": income,
        "expenses": expenses,
        "savings": saved,
        "savings_rate": savings_rate,
        "budget_total": budget_total,
        "budget_used": budget_used,
        "budget_remaining": round(budget_total - budget_used, 2),
        "breakdown": ranked,
        "budget_rows": budget_rows,
        "overspent": over,
        "overspent_names": [row["name"] for row in over],
        "health": health,
        "top_category": top_category,
        "top_amount": top_amount,
        "top_share": round((top_amount / expenses) * 100, 1) if expenses else 0.0,
        "daily_average": asvc.avg_daily_spend(user_id, month),
        "income_types": fin.income_by_type(user_id, month),
        "weeks": fin.weekly_spending(user_id, month),
        "savings_target": ssvc.profile_goal(user_id),
        "insights": asvc.insights(user_id, month),
        "generated_on": date.today().isoformat(),
    }


def save_report(user_id, month):
    """Build a report and store it in the monthly_reports table.

    Re-generating for the same month UPDATES the existing row rather
    than creating a duplicate.
    """
    report = build_report(user_id, month)

    row = MonthlyReport.query.filter_by(user_id=user_id, month=month).first()
    if row is None:
        row = MonthlyReport(user_id=user_id, month=month)
        db.session.add(row)

    row.total_income = report["income"]
    row.total_expenses = report["expenses"]
    row.total_savings = report["savings"]
    row.savings_rate = report["savings_rate"]
    row.budget_total = report["budget_total"]
    row.budget_used = report["budget_used"]
    row.set_category_breakdown(dict(report["breakdown"]))
    row.set_overspent_categories(report["overspent_names"])
    row.health_score = report["health"]["score"]
    db.session.commit()
    return row


def delete_report(user_id, month):
    """Delete one stored report, only if it belongs to this user."""
    row = MonthlyReport.query.filter_by(user_id=user_id, month=month).first()
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def saved_reports(user_id):
    """All stored reports, newest month first."""
    return (MonthlyReport.query
            .filter_by(user_id=user_id)
            .order_by(MonthlyReport.month.desc())
            .all())


def months_with_data(user_id):
    """Months that have any income or expense recorded."""
    return fin.months_with_data(user_id)


def sync_all(user_id):
    """Create or update a report for every month that has data."""
    months = fin.months_with_data(user_id)
    for month in months:
        save_report(user_id, month)
    return months
