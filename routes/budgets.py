"""
routes/budgets.py - Budget Planning, Monitoring and Overspending warnings.

The "Generate budget with AI" route is added in STAGE 11 together with
the Gemini service, so the button on the page always does something
real. The rule-based suggestion engine is already live below.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import BudgetPlan, ExpenseCategory
from services import finance_service as fin
from services import budget_service as bsvc
from services.validators import parse_amount, parse_month, current_month

budget_bp = Blueprint("budgets", __name__, url_prefix="/budgets")


def _month_from_request():
    raw = (request.args.get("month") or "").strip()
    if not raw:
        return current_month(), None
    return parse_month(raw, "Month")


def _own_budget(budget_id):
    return BudgetPlan.query.filter_by(
        id=budget_id, user_id=current_user.id).first()


def _own_category(category_id):
    """Same ownership check as the expenses module."""
    return ExpenseCategory.query.filter_by(
        id=category_id, user_id=current_user.id).first()


@budget_bp.route("")
@login_required
def index():
    month, error = _month_from_request()
    if error:
        flash(error, "danger")
        return redirect(url_for("budgets.index"))

    user_id = current_user.id
    return render_template(
        "budgets/list.html",
        month=month,
        rows=bsvc.category_progress(user_id, month),
        totals=bsvc.totals(user_id, month),
        suggestions=bsvc.suggest_allocation(user_id, month),
        categories=ExpenseCategory.query.filter_by(
            user_id=user_id).order_by(ExpenseCategory.name).all(),
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )


@budget_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        month, month_error = parse_month(request.form.get("month"), "Month")
        amount, amount_error = parse_amount(request.form.get("amount"),
                                           "Budget amount")
        choice = (request.form.get("budget_type") or "category").strip()
        errors = [e for e in (month_error, amount_error) if e]

        category = None
        if choice == "overall":
            # An overall monthly budget: no category attached
            category = None
        else:
            raw_id = (request.form.get("category_id") or "").strip()
            if not raw_id.isdigit():
                errors.append("Please choose a category.")
            else:
                category = _own_category(int(raw_id))
                if category is None:
                    errors.append("That category does not exist in your account.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template(
                "budgets/add.html",
                categories=ExpenseCategory.query.filter_by(
                    user_id=current_user.id).order_by(ExpenseCategory.name).all(),
                form=request.form)

        category_id = category.id if category else None
        plan, err = bsvc.set_budget(current_user.id, month, amount,
                                    category_id=category_id, source="manual")
        if err:
            flash(err, "danger")
        else:
            label = category.name if category else "Overall monthly"
            flash(f"Budget for {label} set to {amount} for {month}.", "success")
        return redirect(url_for("budgets.index", month=month))

    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id).order_by(ExpenseCategory.name).all()
    return render_template("budgets/add.html", categories=categories,
                           form={"month": current_month(),
                                 "budget_type": "category",
                                 "amount": "", "category_id": ""})


@budget_bp.post("/<int:budget_id>/delete")
@login_required
def delete(budget_id):
    plan = _own_budget(budget_id)
    if not plan:
        flash("That budget was not found in your account.", "danger")
        return redirect(url_for("budgets.index"))

    month = plan.month
    db.session.delete(plan)
    db.session.commit()

    flash("Budget deleted.", "success")
    return redirect(url_for("budgets.index", month=month))


@budget_bp.post("/suggestions/apply")
@login_required
def apply_suggestion():
    """Save one suggested amount as a real budget (button on the list page)."""
    month, month_error = parse_month(request.form.get("month"), "Month")
    amount, amount_error = parse_amount(request.form.get("amount"),
                                       "Suggested amount")
    raw_id = (request.form.get("category_id") or "").strip()

    if month_error or amount_error:
        flash(month_error or amount_error, "danger")
        return redirect(url_for("budgets.index", month=month or current_month()))

    # category_id empty means "Savings" - not a real budget row, so we
    # only save it when a genuine category id was supplied.
    if not raw_id.isdigit():
        flash("That suggestion cannot be saved as a budget.", "warning")
        return redirect(url_for("budgets.index", month=month))

    category = _own_category(int(raw_id))
    if category is None:
        flash("That category does not exist in your account.", "danger")
        return redirect(url_for("budgets.index", month=month))

    plan, err = bsvc.set_budget(current_user.id, month, amount,
                                category_id=category.id, source="manual")
    if err:
        flash(err, "danger")
    else:
        flash(f"Suggested budget applied to {category.name}.", "success")
    return redirect(url_for("budgets.index", month=month))
