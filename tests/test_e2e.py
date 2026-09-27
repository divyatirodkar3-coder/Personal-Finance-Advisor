"""
tests/test_e2e.py - API, End-to-End workflow and Performance
Spec categories: "API Integration Testing",
"End-to-End Workflow Testing", "Performance & Reliability Evaluation"
"""

import time
from datetime import date

from extensions import db
from models import (IncomeRecord, Expense, ExpenseCategory, BudgetPlan,
                    MonthlyReport, SavingsProgress, FinancialAnalytics,
                    AIInsight)
from services import report_service as rsvc
from services.validators import current_month as month_now


# ==================================================================
# API INTEGRATION TESTING
# ==================================================================
API_ENDPOINTS = ["/api/summary", "/api/expenses/by-category",
                 "/api/budget-progress", "/api/trend", "/api/recent"]


def test_all_api_endpoints_require_login(client):
    for path in API_ENDPOINTS:
        assert client.get(path).status_code == 302


def test_api_endpoints_return_json(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    for path in API_ENDPOINTS:
        response = client.get(path + "?month=" + month)
        assert response.status_code == 200, path
        assert response.is_json, path + " did not return JSON"


def test_api_summary_matches_database(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    data = client.get("/api/summary?month=" + month).get_json()
    assert data["income"] == 50000
    assert data["expenses"] == 10000
    assert data["savings"] == 40000


def test_api_category_data_is_real(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    data = client.get("/api/expenses/by-category?month=" + month).get_json()
    assert set(data["labels"]) == {"Food", "Entertainment"}
    assert sorted(data["values"]) == [4000.0, 6000.0]
    assert len(data["colors"]) == len(data["labels"])


def test_api_trend_length_matches_months(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    data = client.get("/api/trend?months=6&month=" + month).get_json()
    assert len(data["months"]) == 6
    assert len(data["income"]) == 6
    assert len(data["savings"]) == 6


def test_api_rejects_nonsense_month(client, user):
    """A garbage month must not crash the API; it falls back to this month."""
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    data = client.get("/api/summary?month=zzz").get_json()
    assert data["month"] == month_now()
    assert data["income"] == 0


def test_api_clamps_month_count(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    data = client.get("/api/trend?months=9999&month=" + month).get_json()
    assert len(data["months"]) == 12


def test_api_does_not_leak_other_users_data(client, user, other_user,
                                            sample_data):
    """Log in as a SECOND user and prove the first user's rows are invisible.

    NOTE: two test clients built from the same app share a cookie jar, so
    the client is already signed in as `user` by this point. We log out
    first, otherwise the login POST just redirects and proves nothing.

    If the second login still failed, the API calls below would return a
    302 login redirect and .get_json() would blow up loudly, so this test
    cannot pass by accident.
    """
    assert Expense.query.filter_by(user_id=user.id).count() == 2, \
        "the first user should really have two expenses"

    client.post("/auth/logout")
    client.post("/auth/login",
                data={"login": "other", "password": "secret123"})

    data = client.get("/api/expenses/by-category").get_json()
    assert data["labels"] == [], "saw another user's categories"
    assert data["total"] == 0

    summary = client.get("/api/summary").get_json()
    assert summary["income"] == 0
    assert summary["expenses"] == 0
    assert summary["savings"] == 0

    recent = client.get("/api/recent").get_json()
    assert recent["items"] == [], "saw another user's transactions"



# ==================================================================
# END-TO-END WORKFLOW TESTING
# ==================================================================
def test_full_user_journey(client, month):
    """Register -> profile -> income -> expense -> budget -> analysis ->
    savings -> AI -> dashboard -> report -> logout -> login again."""
    client.post("/auth/register", data={
        "username": "rahul", "email": "rahul@test.com",
        "password": "secret123", "confirm_password": "secret123",
        "full_name": "Rahul Sharma", "savings_goal": "5000"})
    assert client.get("/dashboard").status_code == 200, "1 register"

    client.post("/auth/profile", data={
        "action": "details", "full_name": "Rahul S",
        "email": "rahul@test.com", "currency": "INR",
        "savings_goal": "5000"})

    client.post("/income/add", data={
        "source": "Salary", "income_type": "salary", "amount": "50000",
        "income_date": "{0}-01".format(month)})
    assert IncomeRecord.query.count() == 1, "3 income"

    food = ExpenseCategory.query.filter_by(name="Food").first()
    client.post("/expenses/add", data={
        "title": "Groceries", "amount": "2500.50", "category_id": food.id,
        "payment_method": "upi", "expense_date": "{0}-03".format(month)})
    assert Expense.query.count() == 1, "4 expense"

    db.session.add(BudgetPlan(user_id=food.user_id, category_id=food.id,
                              month=month, planned_amount=2000,
                              source="manual"))
    db.session.commit()
    assert BudgetPlan.query.count() == 1, "5 budget"

    assert client.get("/analysis?month=" + month).status_code == 200
    assert FinancialAnalytics.query.count() == 1, "6 analysis"

    assert client.get("/savings?month=" + month).status_code == 200
    assert SavingsProgress.query.filter_by(month=month).count() == 1, "7 sav"

    assert client.post("/ai/generate?month=" + month,
                       data={"feature": "analysis"}).status_code == 302
    assert AIInsight.query.count() >= 1, "8 ai"

    body = client.get("/dashboard?month=" + month).data.decode()
    assert "50000.00" in body, "9 dashboard income"
    assert "2500.50" in body, "9 dashboard expense"

    client.post("/reports/{0}/generate".format(month))
    assert MonthlyReport.query.filter_by(month=month).count() == 1, "10 rep"

    client.post("/auth/logout")
    assert client.get("/dashboard").status_code == 302, "11 logout"

    client.post("/auth/login", data={"login": "rahul",
                                     "password": "secret123"})
    assert client.get("/dashboard").status_code == 200
    assert IncomeRecord.query.count() == 1, "12 data survived"
    assert Expense.query.count() == 1


def test_savings_math_is_consistent_everywhere(client, sample_data, month):
    """The dashboard, the API and the report must agree to the rupee."""
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    api = client.get("/api/summary?month=" + month).get_json()
    report = rsvc.build_report(sample_data["user_id"], month)
    assert api["income"] == report["income"]
    assert api["expenses"] == report["expenses"]
    assert api["savings"] == report["savings"]


# ==================================================================
# PERFORMANCE & RELIABILITY
# ==================================================================
def test_ten_requests_stay_fast(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    start = time.time()
    for _ in range(10):
        assert client.get("/budgets?month=" + month).status_code == 200
    elapsed = time.time() - start
    assert elapsed < 10, "10 loads took {0:.1f}s".format(elapsed)


def test_bulk_insert_is_fast(app, user, month):
    year, mon = int(month[:4]), int(month[5:7])
    cat = ExpenseCategory.query.filter_by(user_id=user.id, name="Food").first()
    start = time.time()
    for i in range(200):
        db.session.add(Expense(
            user_id=user.id, category_id=cat.id, title="Item{0}".format(i),
            amount=10, expense_date=date(year, mon, 1 + (i % 28))))
    db.session.commit()
    elapsed = time.time() - start
    assert Expense.query.filter_by(user_id=user.id).count() == 200
    assert elapsed < 20, "200 inserts took {0:.1f}s".format(elapsed)


def test_repeated_failures_do_not_crash(client, app, user):
    for _ in range(20):
        client.post("/auth/login", data={"login": "ghost",
                                         "password": "wrong"})
        client.post("/expenses/add", data={"title": "", "amount": "-9",
                                           "expense_date": "nope"})
    assert client.get("/auth/login").status_code == 200


def test_app_survives_unknown_url(client):
    for path in ["/nope", "/income/nope", "/api/nope"]:
        assert client.get(path).status_code in (302, 404, 405, 400)
