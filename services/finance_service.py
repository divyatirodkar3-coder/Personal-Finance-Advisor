"""
services/finance_service.py - All the money calculations live here.

WHY A SEPARATE FILE?
--------------------
If every route file worked out its own totals, we would end up with
five slightly different versions of "total expenses". Putting the
maths in one place means the dashboard, the reports and the budget
page can never disagree with each other.

IMPORTANT: every function takes a user_id and filters by it. That is
what stops one user from ever seeing another user's money.
"""

from calendar import monthrange
from datetime import date

from sqlalchemy import func

from extensions import db
from models import IncomeRecord, Expense, ExpenseCategory

# The income types the form offers. These cover all four scenarios:
#   salary    -> Scenario 1 (salaried professional)
#   allowance -> Scenario 2 (college student)
#   freelance -> Scenario 3 (freelancer, many clients)
#   business  -> Scenario 4 (household / shared family income)
INCOME_TYPES = [
    ("salary", "Salary"),
    ("freelance", "Freelance / Client payment"),
    ("allowance", "Allowance (student)"),
    ("business", "Business income"),
    ("investment", "Investment / Interest"),
    ("other", "Other"),
]


def month_bounds(month):
    """'2026-09' -> (first day, last day) of that month.

    Example result: (date(2026, 9, 1), date(2026, 9, 30))
    """
    year = int(month[:4])
    mon = int(month[5:7])
    last_day = monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


def previous_month(month):
    """'2026-01' -> '2025-12'  (used by the month arrows)."""
    year, mon = int(month[:4]), int(month[5:7])
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"


def next_month(month):
    """'2026-12' -> '2027-01'"""
    year, mon = int(month[:4]), int(month[5:7])
    if mon == 12:
        return f"{year + 1}-01"
    return f"{year}-{mon + 1:02d}"


# ------------------------------------------------------------------
# TOTALS
# ------------------------------------------------------------------
def total_income(user_id, month):
    """All money received in one month."""
    start, end = month_bounds(month)
    value = db.session.query(
        func.coalesce(func.sum(IncomeRecord.amount), 0)
    ).filter(
        IncomeRecord.user_id == user_id,
        IncomeRecord.income_date >= start,
        IncomeRecord.income_date <= end,
    ).scalar()
    return float(value or 0)


# ------------------------------------------------------------------
# LISTS AND BREAKDOWNS
# ------------------------------------------------------------------
def income_records(user_id, month=None):
    """Income rows for one month (newest first), or all months."""
    query = IncomeRecord.query.filter_by(user_id=user_id)
    if month:
        start, end = month_bounds(month)
        query = query.filter(IncomeRecord.income_date >= start,
                             IncomeRecord.income_date <= end)
    return query.order_by(IncomeRecord.income_date.desc(),
                          IncomeRecord.id.desc()).all()


def expense_records(user_id, month=None):
    """Expense rows for one month (newest first), or all months."""
    query = Expense.query.filter_by(user_id=user_id)
    if month:
        start, end = month_bounds(month)
        query = query.filter(Expense.expense_date >= start,
                             Expense.expense_date <= end)
    return query.order_by(Expense.expense_date.desc(),
                          Expense.id.desc()).all()


def income_by_type(user_id, month):
    """{'salary': 50000, 'freelance': 12000, ...} for one month."""
    start, end = month_bounds(month)
    rows = db.session.query(
        IncomeRecord.income_type,
        func.coalesce(func.sum(IncomeRecord.amount), 0),
    ).filter(
        IncomeRecord.user_id == user_id,
        IncomeRecord.income_date >= start,
        IncomeRecord.income_date <= end,
    ).group_by(IncomeRecord.income_type).all()
    return {row[0]: float(row[1] or 0) for row in rows}


def category_breakdown(user_id, month):
    """{'Food': 4200.5, 'Rent': 12000} - spending per category.

    Only categories that actually have spending are returned, which
    keeps the doughnut chart clean.
    """
    start, end = month_bounds(month)
    rows = db.session.query(
        ExpenseCategory.name,
        func.coalesce(func.sum(Expense.amount), 0),
    ).select_from(Expense).join(
        ExpenseCategory, Expense.category_id == ExpenseCategory.id
    ).filter(
        Expense.user_id == user_id,
        Expense.expense_date >= start,
        Expense.expense_date <= end,
    ).group_by(ExpenseCategory.name).all()
    return {row[0]: float(row[1] or 0) for row in rows}


def category_colors(user_id):
    """{'Food': '#f97316', ...} - colours for the charts."""
    rows = ExpenseCategory.query.filter_by(user_id=user_id).all()
    return {row.name: row.color for row in rows}


def weekly_spending(user_id, month):
    """Split one month into 7-day blocks and total spending in each.

    The project spec talks about tracking DAILY and WEEKLY expenses.
    Daily tracking is just the individual expense rows; this function
    produces the weekly view on top of them.

    Returns a list of (label, total, first_day, last_day) tuples, for
    example:
        [("Week 1 (1-7 Sep)", 4200.0, date(2026,9,1), date(2026,9,7)), ...]
    """
    start, end = month_bounds(month)
    rows = expense_records(user_id, month)

    buckets = {}
    for record in rows:
        # day 0-6 -> week 1, day 7-13 -> week 2, and so on
        week_number = ((record.expense_date - start).days // 7) + 1
        buckets[week_number] = buckets.get(week_number, 0) + float(record.amount or 0)

    results = []
    for week_number in sorted(buckets):
        first_day = start.fromordinal(start.toordinal() + (week_number - 1) * 7)
        last_day = min(first_day.fromordinal(first_day.toordinal() + 6),
                       end)
        label = f"Week {week_number} ({first_day.day}-{last_day.day} " \
                f"{first_day.strftime('%b')})"
        results.append((label, round(buckets[week_number], 2),
                        first_day, last_day))
    return results


def daily_totals(user_id, month):
    """{'2026-09-01': 450.0, '2026-09-02': 200.0} - spending per day."""
    start, end = month_bounds(month)
    rows = db.session.query(
        Expense.expense_date,
        func.coalesce(func.sum(Expense.amount), 0),
    ).filter(
        Expense.user_id == user_id,
        Expense.expense_date >= start,
        Expense.expense_date <= end,
    ).group_by(Expense.expense_date).all()
    return {row[0].isoformat(): float(row[1] or 0) for row in rows}


def months_with_data(user_id):
    """All months that have income or expenses, newest first.

    Used by the month picker and by the 6-month trend chart.
    """
    income_months = db.session.query(
        func.strftime("%Y-%m", IncomeRecord.income_date)
    ).filter(IncomeRecord.user_id == user_id).distinct().all()
    expense_months = db.session.query(
        func.strftime("%Y-%m", Expense.expense_date)
    ).filter(Expense.user_id == user_id).distinct().all()

    found = {row[0] for row in income_months if row[0]}
    found |= {row[0] for row in expense_months if row[0]}
    return sorted(found, reverse=True)



def total_expenses(user_id, month):
    """All money spent in one month."""
    start, end = month_bounds(month)
    value = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.user_id == user_id,
        Expense.expense_date >= start,
        Expense.expense_date <= end,
    ).scalar()
    return float(value or 0)


def total_savings(user_id, month):
    """Savings = income - expenses (the simplest honest definition)."""
    return round(total_income(user_id, month)
                 - total_expenses(user_id, month), 2)
