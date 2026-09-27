"""
routes/expenses.py - Expense Tracking, Categorisation and Category CRUD.

SECURITY NOTE
-------------
Two ownership checks are used everywhere:
  1. Finding a row  ->  filter_by(id=..., user_id=current_user.id)
  2. Using a category ->  ExpenseCategory.query.filter_by(
                            id=..., user_id=current_user.id)
The second one stops a user from tagging their expense with somebody
else's category just by changing the id in the form.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Expense, ExpenseCategory
from services import finance_service as fin
from services.validators import (parse_amount, parse_date, clean_text,
                                 parse_month, current_month)

expense_bp = Blueprint("expenses", __name__, url_prefix="/expenses")

PAYMENT_METHODS = ["cash", "upi", "card", "bank", "other"]

# A small fixed palette so charts stay readable and consistent.
CATEGORY_COLORS = [
    "#dc2626", "#f97316", "#0ea5e9", "#a855f7", "#16a34a",
    "#eab308", "#06b6d4", "#ec4899", "#10b981", "#64748b",
    "#ef4444", "#8b5cf6", "#14b8a6", "#f59e0b",
]


def _month_from_request():
    raw = (request.args.get("month") or "").strip()
    if not raw:
        return current_month(), None
    return parse_month(raw, "Month")


def _own_category(category_id):
    """Return the user's category, or None if it isn't theirs."""
    return ExpenseCategory.query.filter_by(
        id=category_id, user_id=current_user.id).first()


def _own_expense(expense_id):
    """Return the user's expense, or None if it isn't theirs."""
    return Expense.query.filter_by(
        id=expense_id, user_id=current_user.id).first()


def _resolve_category(raw_value):
    """Turn the category id from the form into a real category.

    IMPORTANT: request.form always gives us TEXT, so "5" not 5. The
    database id column is an Integer, so we must convert before the
    query - otherwise SQLAlchemy raises an error.

    Returns (category_or_None, error_message_or_None)
    """
    text = (raw_value or "").strip()
    if text == "":
        return None, None                      # "no category" is allowed
    if not text.isdigit():
        return None, "That category does not exist in your account."
    category = _own_category(int(text))
    if category is None:
        return None, "That category does not exist in your account."
    return category, None


def _form_values(source=None, record=None):
    """Build a plain dict for the template.

    Templates work much more easily with dict['key'] than with model
    attributes, and it lets the add form and the edit form share ONE
    template file instead of duplicating the markup.
    """
    if record is not None:
        return {
            "title": record.title,
            "amount": record.amount,
            "expense_date": record.expense_date.isoformat(),
            "category_id": record.category_id or "",
            "payment_method": record.payment_method,
            "notes": record.notes or "",
        }
    source = source or {}
    return {
        "title": source.get("title", ""),
        "amount": source.get("amount", ""),
        "expense_date": source.get("expense_date", ""),
        "category_id": source.get("category_id", ""),
        "payment_method": source.get("payment_method", "cash"),
        "notes": source.get("notes", ""),
    }


@expense_bp.route("")
@login_required
def index():
    month, error = _month_from_request()
    if error:
        flash(error, "danger")
        return redirect(url_for("expenses.index"))

    user_id = current_user.id
    records = fin.expense_records(user_id, month)
    breakdown = fin.category_breakdown(user_id, month)

    return render_template(
        "expenses/list.html",
        month=month,
        records=records,
        total=fin.total_expenses(user_id, month),
        income=fin.total_income(user_id, month),
        savings=fin.total_savings(user_id, month),
        breakdown=breakdown,
        colors=fin.category_colors(user_id),
        weeks=fin.weekly_spending(user_id, month),
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )


@expense_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id).order_by(ExpenseCategory.name).all()

    if request.method == "POST":
        title, title_error = clean_text(request.form.get("title"),
                                        "Expense title", 150)
        amount, amount_error = parse_amount(request.form.get("amount"), "Amount")
        expense_date, date_error = parse_date(request.form.get("expense_date"),
                                             "Expense date")
        payment = (request.form.get("payment_method") or "cash").strip()
        notes = (request.form.get("notes") or "").strip()[:1000]

        errors = [e for e in (title_error, amount_error, date_error) if e]

        if payment not in PAYMENT_METHODS:
            payment = "cash"

        # ---- category validation (and ownership check) ----
        category, category_error = _resolve_category(
            request.form.get("category_id"))
        if category_error:
            errors.append(category_error)

        if expense_date and expense_date.year > 2100:
            errors.append("Expense date looks wrong (year is too far ahead).")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("expenses/add.html", categories=categories,
                                   payment_methods=PAYMENT_METHODS,
                                   form=_form_values(source=request.form))

        record = Expense(
            user_id=current_user.id,
            category_id=category.id if category else None,
            title=title,
            amount=amount,
            expense_date=expense_date,
            payment_method=payment,
            notes=notes or None,
        )
        db.session.add(record)
        db.session.commit()

        flash(f"Expense of {amount} added successfully.", "success")
        return redirect(url_for("expenses.index",
                                month=expense_date.strftime("%Y-%m")))

    return render_template("expenses/add.html", categories=categories,
                           payment_methods=PAYMENT_METHODS,
                           form=_form_values())


@expense_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    record = _own_expense(expense_id)
    if not record:
        flash("That expense was not found in your account.", "danger")
        return redirect(url_for("expenses.index"))

    categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id).order_by(ExpenseCategory.name).all()

    if request.method == "POST":
        title, title_error = clean_text(request.form.get("title"),
                                        "Expense title", 150)
        amount, amount_error = parse_amount(request.form.get("amount"), "Amount")
        expense_date, date_error = parse_date(request.form.get("expense_date"),
                                             "Expense date")
        payment = (request.form.get("payment_method") or "cash").strip()
        notes = (request.form.get("notes") or "").strip()[:1000]

        errors = [e for e in (title_error, amount_error, date_error) if e]
        if payment not in PAYMENT_METHODS:
            payment = "cash"

        category, category_error = _resolve_category(
            request.form.get("category_id"))
        if category_error:
            errors.append(category_error)

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("expenses/add.html", categories=categories,
                                   payment_methods=PAYMENT_METHODS,
                                   form=_form_values(source=request.form),
                                   editing=record)

        record.title = title
        record.amount = amount
        record.expense_date = expense_date
        record.payment_method = payment
        record.notes = notes or None
        record.category_id = category.id if category else None
        db.session.commit()

        flash("Expense updated successfully.", "success")
        return redirect(url_for("expenses.index",
                                month=expense_date.strftime("%Y-%m")))

    return render_template("expenses/add.html", categories=categories,
                           payment_methods=PAYMENT_METHODS,
                           form=_form_values(record=record), editing=record)


@expense_bp.post("/<int:expense_id>/delete")
@login_required
def delete(expense_id):
    record = _own_expense(expense_id)
    if not record:
        flash("That expense was not found in your account.", "danger")
        return redirect(url_for("expenses.index"))

    month = record.expense_date.strftime("%Y-%m")
    db.session.delete(record)
    db.session.commit()

    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.index", month=month))


# ------------------------------------------------------------------
# CATEGORY MANAGEMENT  (Expense Category Management)
# ------------------------------------------------------------------
@expense_bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    if request.method == "POST":
        name, name_error = clean_text(request.form.get("name"),
                                      "Category name", 60)
        color = (request.form.get("color") or CATEGORY_COLORS[0]).strip()
        if color not in CATEGORY_COLORS:
            color = CATEGORY_COLORS[0]

        errors = []
        if name_error:
            errors.append(name_error)
        else:
            # Category names must be unique FOR THIS USER
            existing = ExpenseCategory.query.filter_by(
                user_id=current_user.id, name=name).first()
            if existing:
                errors.append(f"You already have a category called '{name}'.")

        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            db.session.add(ExpenseCategory(
                user_id=current_user.id, name=name,
                color=color, is_default=False))
            db.session.commit()
            flash(f"Category '{name}' created.", "success")
            return redirect(url_for("expenses.categories"))

    rows = (ExpenseCategory.query
            .filter_by(user_id=current_user.id)
            .order_by(ExpenseCategory.is_default.desc(),
                      ExpenseCategory.name)
            .all())

    # How much has been spent in each category (all time)
    usage = {}
    for row in rows:
        total = db.session.query(db.func.coalesce(
            db.func.sum(Expense.amount), 0)).filter(
            Expense.category_id == row.id).scalar()
        usage[row.id] = float(total or 0)

    return render_template("expenses/categories.html", categories=rows,
                           usage=usage, colors=CATEGORY_COLORS)


@expense_bp.post("/categories/<int:category_id>/delete")
@login_required
def category_delete(category_id):
    category = _own_category(category_id)
    if not category:
        flash("That category was not found in your account.", "danger")
        return redirect(url_for("expenses.categories"))

    # We refuse to delete a category that still has expenses, because
    # the database relationship would silently delete those expenses too.
    used = Expense.query.filter_by(category_id=category.id).count()
    if used:
        flash(f"'{category.name}' still has {used} expense(s). "
              "Move or delete them first, then remove the category.",
              "warning")
        return redirect(url_for("expenses.categories"))

    name = category.name
    db.session.delete(category)
    db.session.commit()

    flash(f"Category '{name}' deleted.", "success")
    return redirect(url_for("expenses.categories"))
