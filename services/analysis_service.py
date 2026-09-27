"""
services/analysis_service.py - Spending Analysis and Overspending Detection.

THE FINANCIAL HEALTH SCORE
--------------------------
The score is deliberately SIMPLE and BREAKABLE DOWN. It is built from
three parts, each worth a known number of points, so it can be
explained rather than being a mysterious black box:

    Savings health        40 points
    Budget discipline     30 points
    Spending level        30 points
    ---------------------------
    Total                100 points

That matters for two reasons: a user can understand their own score,
and it is easy to test.
"""

from extensions import db
from models import FinancialAnalytics
from services import finance_service as fin
from services import budget_service as bsvc
from services import savings_service as ssvc

# Points available for each part of the score
SAVINGS_POINTS = 40
BUDGET_POINTS = 30
SPENDING_POINTS = 30

# Spending above this share of income is considered unhealthy
HEALTHY_SPEND_RATIO = 0.70

SCORE_LABELS = [
    (80, "Excellent", "green"),
    (60, "Good", "blue"),
    (40, "Needs work", "amber"),
    (0, "At risk", "red"),
]


def label_for(score):
    """Turn a number into a friendly label + badge colour."""
    for threshold, label, colour in SCORE_LABELS:
        if score >= threshold:
            return label, colour
    return "At risk", "red"


def health_score(user_id, month):
    """Calculate the 0-100 financial health score, with the reasons."""
    income = fin.total_income(user_id, month)
    expenses = fin.total_expenses(user_id, month)
    saved = round(income - expenses, 2)

    reasons = []
    score = 0

    # ---------- PART 1: SAVINGS HEALTH (40 pts) ----------
    if income > 0:
        savings_rate = saved / income
        # 20% saved is treated as the ideal
        part1 = max(0, min(SAVINGS_POINTS,
                           (savings_rate / 0.20) * SAVINGS_POINTS))
        reasons.append({
            "label": "Savings health",
            "points": round(part1, 1),
            "max": SAVINGS_POINTS,
            "note": (f"You saved {savings_rate:.0%} of income "
                     f"(ideal is 20%)."),
        })
    else:
        part1 = 0
        reasons.append({
            "label": "Savings health",
            "points": 0,
            "max": SAVINGS_POINTS,
            "note": "No income recorded for this month.",
        })
    score += part1

    # ---------- PART 2: BUDGET DISCIPLINE (30 pts) ----------
    rows = bsvc.category_progress(user_id, month)
    if rows:
        on_track = sum(1 for r in rows if r["status"] != "over")
        part2 = (on_track / len(rows)) * BUDGET_POINTS
        reasons.append({
            "label": "Budget discipline",
            "points": round(part2, 1),
            "max": BUDGET_POINTS,
            "note": (f"{on_track} of {len(rows)} budgeted categories "
                     f"are within their limit."),
        })
    else:
        part2 = BUDGET_POINTS / 2
        reasons.append({
            "label": "Budget discipline",
            "points": round(part2, 1),
            "max": BUDGET_POINTS,
            "note": "No budgets set yet - set some to improve this score.",
        })
    score += part2

    # ---------- PART 3: SPENDING LEVEL (30 pts) ----------
    if income > 0:
        spend_ratio = expenses / income
        if spend_ratio <= HEALTHY_SPEND_RATIO:
            part3 = SPENDING_POINTS
        elif spend_ratio <= 0.90:
            part3 = 20
        elif spend_ratio <= 1.00:
            part3 = 10
        else:
            part3 = 0
        reasons.append({
            "label": "Spending level",
            "points": part3,
            "max": SPENDING_POINTS,
            "note": (f"You spent {spend_ratio:.0%} of income "
                     f"(healthy is {HEALTHY_SPEND_RATIO:.0%} or less)."),
        })
    else:
        part3 = 0
        reasons.append({
            "label": "Spending level",
            "points": 0,
            "max": SPENDING_POINTS,
            "note": "No income recorded, so this cannot be scored.",
        })
    score += part3

    total = int(round(min(100, max(0, score))))
    label, colour = label_for(total)
    return {"score": total, "label": label, "colour": colour,
            "reasons": reasons}


# ------------------------------------------------------------------
# OVERSPENDING DETECTION
# ------------------------------------------------------------------
def overspending(user_id, month):
    """Categories where spending has gone past the budget.

    Returns a list of dictionaries, worst offender first.
    """
    rows = bsvc.category_progress(user_id, month)
    over = [r for r in rows if r["status"] == "over"]
    over.sort(key=lambda r: r["remaining"])   # most negative first
    return over


def near_limit(user_id, month):
    """Categories that are between 80% and 100% of their budget."""
    return [r for r in bsvc.category_progress(user_id, month)
            if r["status"] == "warn"]


def overall_overspend(user_id, month):
    """By how much the WHOLE month is over its overall budget (0 if fine)."""
    totals = bsvc.totals(user_id, month)
    if not totals["whole_planned"]:
        return 0.0
    return round(max(totals["spent"] - totals["whole_planned"], 0), 2)


def top_categories(user_id, month, limit=5):
    """The categories with the most spending, biggest first."""
    spending = fin.category_breakdown(user_id, month)
    ordered = sorted(spending.items(), key=lambda item: item[1], reverse=True)
    return ordered[:limit]


def avg_daily_spend(user_id, month):
    """Average spend per day so far in the month.

    For a finished month this uses the whole month. For the current
    month it divides by the days that have actually passed, which is
    the more useful number right now.
    """
    expenses = fin.total_expenses(user_id, month)
    if expenses <= 0:
        return 0.0

    progress = ssvc.month_progress(month)
    total_days = ssvc.days_in_month(month)

    if progress >= 1.0:                 # finished month
        used_days = total_days
    elif progress <= 0.0:               # future month
        return 0.0
    else:                               # month in progress
        used_days = max(1, round(total_days * progress))

    return round(expenses / used_days, 2)


def month_comparison(user_id, month):
    """Compare this month with the one before it."""
    previous = fin.previous_month(month)
    now_exp = fin.total_expenses(user_id, month)
    prev_exp = fin.total_expenses(user_id, previous)

    change = round(now_exp - prev_exp, 2)
    percent = round((change / prev_exp) * 100, 1) if prev_exp else None

    return {
        "previous_month": previous,
        "current": now_exp,
        "previous": prev_exp,
        "change": change,
        "percent": percent,
        "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
    }


# ------------------------------------------------------------------
# PLAIN-LANGUAGE INSIGHTS
# ------------------------------------------------------------------
def insights(user_id, month):
    """Short, readable observations built from real numbers.

    This is the rule-based version. STAGE 11 sends the same numbers
    to Gemini so the AI can write richer advice.
    """
    messages = []
    income = fin.total_income(user_id, month)
    expenses = fin.total_expenses(user_id, month)
    saved = round(income - expenses, 2)

    if income <= 0:
        return ["No income recorded for this month, so there is nothing "
                "to analyse yet. Add your income first."]

    # savings
    if saved < 0:
        messages.append(
            f"You spent {expenses:,.2f} against {income:,.2f} of income, "
            f"so you overspent by {abs(saved):,.2f} this month.")
    else:
        rate = (saved / income) * 100
        if rate >= 20:
            messages.append(
                f"You saved {saved:,.2f} ({rate:.0f}% of income). "
                f"That is a strong savings rate - keep it up.")
        elif rate >= 0:
            messages.append(
                f"You saved {saved:,.2f} ({rate:.0f}% of income). "
                f"Aiming for 20% would mean saving "
                f"{income * 0.20:,.2f} this month.")
        else:
            messages.append("You saved nothing this month.")

    # overspending
    over = overspending(user_id, month)
    for row in over[:3]:
        messages.append(
            f"OVERSPENDING: {row['name']} - you spent "
            f"{row['spent']:,.2f} against a {row['planned']:,.2f} budget "
            f"({abs(row['remaining']):,.2f} over).")

    for row in near_limit(user_id, month)[:2]:
        messages.append(
            f"{row['name']} is at {row['percent']:.0f}% of its budget. "
            f"Only {row['remaining']:,.2f} left.")

    # top category
    top = top_categories(user_id, month, limit=1)
    if top and expenses > 0:
        share = (top[0][1] / expenses) * 100
        messages.append(
            f"Your biggest spending category is {top[0][0]} at "
            f"{top[0][1]:,.2f} ({share:.0f}% of all spending).")

    # daily pace
    daily = avg_daily_spend(user_id, month)
    if daily > 0:
        messages.append(f"You are spending about {daily:,.2f} per day "
                        f"so far this month.")

    # comparison
    comparison = month_comparison(user_id, month)
    if comparison["previous"] > 0:
        word = {"up": "more", "down": "less", "flat": "the same"}[
            comparison["direction"]]
        messages.append(
            f"You spent {word} than {comparison['previous_month']} "
            f"({comparison['percent']:+.1f}%).")

    return messages


# ------------------------------------------------------------------
# PERSIST TO THE financial_analytics TABLE
# ------------------------------------------------------------------
def sync_analytics(user_id, month):
    """Store this month's analysis in the financial_analytics table."""
    row = FinancialAnalytics.query.filter_by(
        user_id=user_id, month=month).first()
    if row is None:
        row = FinancialAnalytics(user_id=user_id, month=month)
        db.session.add(row)

    score = health_score(user_id, month)
    over = overspending(user_id, month)
    top = top_categories(user_id, month, limit=1)

    row.total_income = fin.total_income(user_id, month)
    row.total_expenses = fin.total_expenses(user_id, month)
    row.savings = fin.total_savings(user_id, month)
    row.top_expense_category = top[0][0] if top else None
    row.overspend_count = len(over)
    row.avg_daily_spend = avg_daily_spend(user_id, month)
    row.health_score = score["score"]
    db.session.commit()
    return row


def analyse(user_id, month):
    """Everything the Analysis page needs, in one call."""
    sync_analytics(user_id, month)
    return {
        "month": month,
        "income": fin.total_income(user_id, month),
        "expenses": fin.total_expenses(user_id, month),
        "savings": fin.total_savings(user_id, month),
        "health": health_score(user_id, month),
        "overspent": overspending(user_id, month),
        "near_limit": near_limit(user_id, month),
        "top": top_categories(user_id, month),
        "daily": avg_daily_spend(user_id, month),
        "comparison": month_comparison(user_id, month),
        "insights": insights(user_id, month),
        "totals": bsvc.totals(user_id, month),
    }
