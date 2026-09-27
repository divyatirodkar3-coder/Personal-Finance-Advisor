"""
tests/test_finance.py - Income, Expense, Budget and Savings
Spec categories: "Income Tracking Testing", "Expense Management Testing",
"Budget Generation Validation"

Every assertion checks REAL numbers pulled back out of the database,
not the values that were typed in.
"""

import pytest

from extensions import db
from models import (IncomeRecord, Expense, ExpenseCategory,
                    BudgetPlan, SavingsProgress)
from services import finance_service as fin
from services import budget_service as bsvc
from services import savings_service as ssvc


def add_income(client, month, amount, source="Salary", kind="salary"):
    return client.post("/income/add", data={
        "source": source, "income_type": kind, "amount": str(amount),
        "income_date": "{0}-01".format(month)})


def add_expense(client, month, amount, title="Test", category_id=None,
                day=5):
    data = {"title": title, "amount": str(amount),
            "expense_date": "{0}-{1:02d}".format(month, day),
            "payment_method": "cash"}
    if category_id:
        data["category_id"] = str(category_id)
    return client.post("/expenses/add", data=data)


def cat(user, name):
    return ExpenseCategory.query.filter_by(user_id=user.id,
                                           name=name).first()


# ==================================================================
# INCOME TRACKING
# ==================================================================
def test_income_recorded_and_counted(auth_client, app, user, month):
    add_income(auth_client, month, 50000)
    assert IncomeRecord.query.filter_by(user_id=user.id).count() == 1
    assert fin.total_income(user.id, month) == 50000


def test_income_totals_separate_months(auth_client, app, user, month):
    add_income(auth_client, month, 50000)
    add_income(auth_client, "2026-01", 20000)
    assert fin.total_income(user.id, month) == 50000
    assert fin.total_income(user.id, "2026-01") == 20000


def test_income_types_are_grouped(auth_client, app, user, month):
    add_income(auth_client, month, 50000, kind="salary")
    add_income(auth_client, month, 15000, source="Client A", kind="freelance")
    by_type = fin.income_by_type(user.id, month)
    assert by_type["salary"] == 50000
    assert by_type["freelance"] == 15000


def test_income_page_shows_total(auth_client, app, user, month):
    add_income(auth_client, month, 50000)
    body = auth_client.get("/income?month=" + month).data.decode()
    assert "50000.00" in body


@pytest.mark.parametrize("amount", ["-1", "0", "abc", "", "1e999"])
def test_income_rejects_bad_amounts(auth_client, app, user, month, amount):
    auth_client.post("/income/add", data={
        "source": "X", "income_type": "salary", "amount": amount,
        "income_date": "{0}-01".format(month)})
    assert IncomeRecord.query.filter_by(user_id=user.id).count() == 0


# ==================================================================
# EXPENSE MANAGEMENT
# ==================================================================
def test_expense_recorded_with_category(auth_client, app, user, month):
    add_expense(auth_client, month, 2500, "Groceries", cat(user, "Food").id)
    record = Expense.query.filter_by(user_id=user.id).first()
    assert record.amount == 2500
    assert record.category.name == "Food"


def test_expense_can_have_no_category(auth_client, app, user, month):
    add_expense(auth_client, month, 80, "Mystery")
    assert Expense.query.filter_by(user_id=user.id).first().category_id is None


def test_category_breakdown_is_correct(auth_client, app, user, month):
    add_expense(auth_client, month, 6000, "G", cat(user, "Food").id)
    add_expense(auth_client, month, 4000, "C", cat(user, "Entertainment").id)
    assert fin.category_breakdown(user.id, month) == {
        "Food": 6000.0, "Entertainment": 4000.0}


def test_expense_edit_works(auth_client, app, user, month):
    add_expense(auth_client, month, 100, "Lunch")
    record = Expense.query.filter_by(user_id=user.id).first()
    auth_client.post("/expenses/{0}/edit".format(record.id), data={
        "title": "Dinner", "amount": "250", "payment_method": "card",
        "expense_date": "{0}-06".format(month)})
    fresh = db.session.get(Expense, record.id)
    assert fresh.title == "Dinner"
    assert fresh.amount == 250


# ==================================================================
# WEEKLY SPENDING
# ==================================================================
def test_weekly_totals_add_up_to_monthly(auth_client, app, user, month):
    add_expense(auth_client, month, 1000, "A", day=2)
    add_expense(auth_client, month, 2000, "B", day=9)
    add_expense(auth_client, month, 3000, "C", day=25)
    weeks = fin.weekly_spending(user.id, month)
    assert round(sum(w[1] for w in weeks), 2) == 6000.0
    assert fin.total_expenses(user.id, month) == 6000.0


# ==================================================================
# BUDGET GENERATION VALIDATION
# ==================================================================
def test_budget_progress_on_track(auth_client, app, user, month):
    """2000 of a 3000 budget is 66%, which is under the 80% warn line."""
    add_expense(auth_client, month, 2000, "G", cat(user, "Food").id)
    bsvc.set_budget(user.id, month, 3000, category_id=cat(user, "Food").id)
    row = bsvc.category_progress(user.id, month)[0]
    assert row["status"] == "on_track"
    assert row["remaining"] == 1000.0


def test_budget_warns_near_limit(auth_client, app, user, month):
    add_expense(auth_client, month, 2700, "G", cat(user, "Food").id)
    bsvc.set_budget(user.id, month, 3000, category_id=cat(user, "Food").id)
    assert bsvc.category_progress(user.id, month)[0]["status"] == "warn"


def test_budget_detects_overspend(auth_client, app, user, month):
    add_expense(auth_client, month, 6000, "G", cat(user, "Food").id)
    bsvc.set_budget(user.id, month, 3000, category_id=cat(user, "Food").id)
    row = bsvc.category_progress(user.id, month)[0]
    assert row["status"] == "over"
    assert row["remaining"] == -3000.0


def test_setting_budget_twice_updates_not_duplicates(app, user, month):
    food = cat(user, "Food")
    bsvc.set_budget(user.id, month, 1000, category_id=food.id)
    bsvc.set_budget(user.id, month, 2000, category_id=food.id)
    rows = BudgetPlan.query.filter_by(user_id=user.id, month=month,
                                      category_id=food.id).all()
    assert len(rows) == 1
    assert rows[0].planned_amount == 2000


def test_budget_page_shows_progress(auth_client, app, user, month):
    add_expense(auth_client, month, 2500, "G", cat(user, "Food").id)
    auth_client.post("/budgets/add", data={
        "month": month, "amount": "3000", "budget_type": "category",
        "category_id": str(cat(user, "Food").id)})
    body = auth_client.get("/budgets?month=" + month).data.decode()
    assert "3000.00" in body and "2500.00" in body


# ==================================================================
# SAVINGS
# ==================================================================
def test_savings_is_income_minus_expenses(auth_client, app, user, month):
    add_income(auth_client, month, 50000)
    add_expense(auth_client, month, 17500, "Rent", cat(user, "Rent").id)
    assert fin.total_savings(user.id, month) == 32500.0


def test_savings_record_is_written(auth_client, app, user, month):
    add_income(auth_client, month, 50000)
    add_expense(auth_client, month, 10000, "X", cat(user, "Food").id)
    ssvc.sync_month(user.id, month)
    row = SavingsProgress.query.filter_by(user_id=user.id,
                                          month=month).first()
    assert row is not None
    assert row.saved_amount == 40000.0
    assert row.status == "achieved"


def test_zero_target_means_no_goal(auth_client, app, user, month):
    add_income(auth_client, month, 50000)
    auth_client.post("/savings?month=" + month, data={"target": "0"})
    ssvc.sync_month(user.id, month)
    row = SavingsProgress.query.filter_by(user_id=user.id,
                                          month=month).first()
    assert row.target_amount == 0
    assert row.status == "no_target"


def test_expense_delete_works(auth_client, app, user, month):
    add_expense(auth_client, month, 100, "Lunch")
    record = Expense.query.filter_by(user_id=user.id).first()
    auth_client.post("/expenses/{0}/delete".format(record.id))
    assert Expense.query.filter_by(user_id=user.id).count() == 0


def test_category_in_use_cannot_be_deleted(auth_client, app, user, month):
    food = cat(user, "Food")
    add_expense(auth_client, month, 100, "Lunch", food.id)
    response = auth_client.post(
        "/expenses/categories/{0}/delete".format(food.id),
        follow_redirects=True)
    assert b"still has" in response.data
    assert db.session.get(ExpenseCategory, food.id) is not None


def test_unused_category_can_be_deleted(auth_client, app, user):
    auth_client.post("/expenses/categories", data={"name": "Pet care"})
    pet = ExpenseCategory.query.filter_by(user_id=user.id,
                                         name="Pet care").first()
    auth_client.post("/expenses/categories/{0}/delete".format(pet.id))
    assert ExpenseCategory.query.filter_by(user_id=user.id,
                                           name="Pet care").first() is None


def test_duplicate_category_name_rejected(auth_client, app, user):
    response = auth_client.post("/expenses/categories", data={"name": "Food"})
    assert b"already have" in response.data
