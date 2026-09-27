"""
services/budget_service.py - The Budget Planning Engine.

WHAT IS THE BUDGET PLANNING ENGINE?
------------------------------------
A budget is a LIMIT: "spend no more than 3000 on Food in September".
This file compares that limit against what was ACTUALLY spent (real
numbers from the database) and tells you:

    planned  -  spent  =  remaining
    and whether you are on_track / warning / OVER budget.

Every function filters by user_id, so budgets stay private.
"""

from extensions import db
from models import BudgetPlan, ExpenseCategory
from services import finance_service as fin

# Spending percentage at which a category turns amber, then red.
WARN_AT = 80     # 80% used  -> warning
OVER_AT = 100    # 100% used -> overspent


def budget_status(planned, spent):
    """Turn two numbers into a status word + a CSS class."""
    if not planned or planned <= 0:
        return "no_budget", ""
    used_percent = (spent / planned) * 100
    if spent > planned:
        return "over", "over"
    if used_percent >= WARN_AT:
        return "warn", "warn"
    return "on_track", ""


def get_budget(user_id, month, category_id=None):
    """Find the budget for one month (and optionally one category)."""
    return BudgetPlan.query.filter_by(
        user_id=user_id, month=month, category_id=category_id).first()


def budgets_for_month(user_id, month):
    """All category budgets for one month."""
    return (BudgetPlan.query
            .filter_by(user_id=user_id, month=month)
            .filter(BudgetPlan.category_id.isnot(None))
            .all())


def overall_budget(user_id, month):
    """The single whole-month budget (category_id is NULL), or None."""
    return BudgetPlan.query.filter_by(
        user_id=user_id, month=month, category_id=None).first()


def set_budget(user_id, month, amount, category_id=None, source="manual"):
    """Create a budget, or update it if one already exists.

    Returns (budget, error_message_or_None)
    """
    if amount is None or amount <= 0:
        return None, "Budget amount must be greater than zero."

    existing = get_budget(user_id, month, category_id)
    if existing:
        existing.planned_amount = amount
        existing.source = source
    else:
        existing = BudgetPlan(user_id=user_id, month=month,
                              category_id=category_id,
                              planned_amount=amount, source=source)
        db.session.add(existing)
    db.session.commit()
    return existing, None


def delete_budget(budget_id, user_id):
    """Delete a budget only if it really belongs to this user."""
    plan = BudgetPlan.query.filter_by(id=budget_id, user_id=user_id).first()
    if not plan:
        return False
    db.session.delete(plan)
    db.session.commit()
    return True


def category_progress(user_id, month):
    """One row per category: planned, spent, remaining, percent, status.

    Returns a list of dictionaries, sorted with the biggest budget first
    so the page reads top-down in importance.
    """
    plans = budgets_for_month(user_id, month)
    spent_by_cat = fin.category_breakdown(user_id, month)

    rows = []
    for plan in plans:
        category = db.session.get(ExpenseCategory, plan.category_id)
        name = category.name if category else "(deleted category)"
        colour = category.color if category else "#64748b"
        planned = float(plan.planned_amount or 0)
        spent = float(spent_by_cat.get(name, 0))
        remaining = round(planned - spent, 2)
        percent = round((spent / planned) * 100, 1) if planned else 0
        status, css = budget_status(planned, spent)
        rows.append({
            "plan": plan,
            "name": name,
            "color": colour,
            "planned": planned,
            "spent": spent,
            "remaining": remaining,
            "percent": percent,
            "status": status,
            "css": css,
        })

    rows.sort(key=lambda r: r["planned"], reverse=True)
    return rows


# ------------------------------------------------------------------
# THE SUGGESTION ENGINE (rule based, no AI needed)
# ------------------------------------------------------------------
# This is the simple version of "Personalized Budget Generation".
# In STAGE 11 the same idea is upgraded so Gemini writes the advice.
# Here the maths is done by clear, testable rules using REAL numbers.

# What share of income is a healthy spending target?
TARGET_SPEND_RATIO = 0.70      # spend at most 70% of income
SAVINGS_RATIO = 0.20            # aim to save 20%
FLEXIBLE_CATEGORIES = {"Food", "Entertainment", "Transport", "Groceries"}


def suggest_allocation(user_id, month):
    """Suggest a sensible budget for each category, based on real data.

    The rules are simple on purpose:
      1. Look at what was ACTUALLY spent in each category this month.
      2. Cap total spending at 70% of income.
      3. Essential categories (rent etc.) get what they actually cost.
      4. Flexible categories share whatever is left.
      5. Always keep 20% of income aside for savings.

    Returns a list of dicts ready for the template.
    """
    income = fin.total_income(user_id, month)
    if income <= 0:
        return []

    spending = fin.category_breakdown(user_id, month)
    categories = (ExpenseCategory.query
                  .filter_by(user_id=user_id)
                  .order_by(ExpenseCategory.name).all())

    target_total = round(income * TARGET_SPEND_RATIO, 2)
    savings_target = round(income * SAVINGS_RATIO, 2)

    # Split spending into "needs" and "wants"
    needs = {}
    wants = {}
    for category in categories:
        spent = float(spending.get(category.name, 0))
        if spent <= 0:
            continue
        if category.name in FLEXIBLE_CATEGORIES:
            wants[category.name] = spent
        else:
            needs[category.name] = spent

    needs_total = round(sum(needs.values()), 2)
    wants_total = round(sum(wants.values()), 2)

    suggestions = []

    # 1. Essential categories get exactly what they cost.
    for category in categories:
        if category.name in needs:
            suggestions.append({
                "category_id": category.id,
                "name": category.name,
                "color": category.color,
                "suggested": needs[category.name],
                "reason": "Essential - you actually spent this much",
                "current": needs[category.name],
            })

    # 2. If essentials already eat the whole target, warn about it.
    if needs_total > target_total:
        suggestions.append({
            "category_id": None,
            "name": "WARNING",
            "color": "#dc2626",
            "suggested": target_total,
            "reason": (f"Essential costs ({needs_total}) already exceed the "
                       f"70% target ({target_total}). Cut fixed costs."),
            "current": needs_total,
        })
        return suggestions

    # 3. Flexible categories share what is left, pro-rata - BUT we never
    #    suggest spending MORE than the user actually spends. A budget
    #    above real spending is useless advice, so anything left over
    #    goes to savings instead.
    left_for_wants = round(target_total - needs_total, 2)
    used_for_wants = 0.0

    if wants_total > 0 and wants:
        scale = left_for_wants / wants_total
        for category in categories:
            if category.name not in wants:
                continue
            actual = wants[category.name]
            share = round(actual * scale, 2)
            # the cap is the important part
            suggested = round(min(share, actual), 2)
            used_for_wants += suggested
            cut = round(actual - suggested, 2)

            if cut > 0:
                reason = f"Flexible - trim by {cut} to stay on target"
            else:
                reason = "Flexible - you are already under the target"

            suggestions.append({
                "category_id": category.id,
                "name": category.name,
                "color": category.color,
                "suggested": suggested,
                "reason": reason,
                "current": actual,
            })

    # 4. Savings: the 20% target, plus anything the spending caps freed up.
    leftover = round(left_for_wants - used_for_wants, 2)
    if leftover < 0:
        leftover = 0.0
    savings_suggested = round(savings_target + leftover, 2)

    savings_reason = f"Save {SAVINGS_RATIO:.0%} of income ({savings_target})"
    if leftover > 0:
        savings_reason += f" + {leftover} freed up by the limits above"

    suggestions.append({
        "category_id": None,
        "name": "Savings",
        "color": "#10b981",
        "suggested": savings_suggested,
        "reason": savings_reason,
        "current": max(fin.total_savings(user_id, month), 0),
    })

    return suggestions


def totals(user_id, month):
    """Whole-month budget numbers: planned vs actually spent."""
    total_planned = round(
        sum(float(p.planned_amount or 0) for p in budgets_for_month(user_id, month)), 2)

    whole = overall_budget(user_id, month)
    whole_planned = float(whole.planned_amount or 0) if whole else 0.0

    spent = fin.total_expenses(user_id, month)
    income = fin.total_income(user_id, month)
    status, css = budget_status(whole_planned, spent)

    return {
        "total_planned": total_planned,
        "whole_planned": whole_planned,
        "whole_plan": whole,
        "spent": spent,
        "income": income,
        "remaining": round(whole_planned - spent, 2) if whole_planned else 0.0,
        "percent": round((spent / whole_planned) * 100, 1) if whole_planned else 0.0,
        "status": status,
        "css": css,
    }
