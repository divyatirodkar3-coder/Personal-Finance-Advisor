"""
tests/conftest.py - Shared test fixtures.

WHAT IS A FIXTURE?
------------------
A helper that is set up once and reused by many tests, so you do not
repeat the same five lines in every test file. The @pytest.fixture
decorator marks it.

Every test runs against an IN-MEMORY database, so the tests can never
damage your real finance.db.
"""

import os
import sys
from datetime import date

import pytest

# Make sure the project folder is importable when running pytest.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app                      # noqa: E402
from config import TestingConfig                # noqa: E402
from extensions import db                        # noqa: E402
from models import (User, IncomeRecord, Expense,  # noqa: E402
                    ExpenseCategory)
from services.defaults import seed_default_categories  # noqa: E402
from services.validators import current_month   # noqa: E402


@pytest.fixture
def app():
    """A fresh Flask app with an empty in-memory database."""
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client that is NOT logged in."""
    return app.test_client()


def make_user(username="tester", password="secret123", goal=5000,
              full_name="Test User"):
    """Helper that creates and returns a user row."""
    user = User(username=username, email=username + "@test.com",
                full_name=full_name, savings_goal=goal)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    seed_default_categories(user.id)
    return user


@pytest.fixture
def user(app):
    """One registered user, not logged in."""
    return make_user()


@pytest.fixture
def other_user(app):
    """A second user, used to prove data isolation."""
    return make_user(username="other", goal=0)


@pytest.fixture
def auth_client(app, user):
    """A client already logged in as `user`."""
    client = app.test_client()
    client.post("/auth/login",
                data={"login": user.username, "password": "secret123"})
    return client


@pytest.fixture(autouse=True)
def no_live_gemini(app):
    """No test is allowed to call the real Gemini API.

    The suite has to pass with no internet, must not burn the free-tier
    quota, and must not stall for 30 seconds on a timeout. Tests that
    want the "Gemini answered" path mock ai_service.call_gemini instead.
    """
    original = app.config.get("GEMINI_API_KEY")
    app.config["GEMINI_API_KEY"] = ""
    yield
    app.config["GEMINI_API_KEY"] = original


@pytest.fixture
def month():
    """The current month as 'YYYY-MM'."""
    return current_month()


@pytest.fixture
def sample_data(app, auth_client, month):
    """A month of realistic data: income, two categories, one overspend.

    Returns a dict of the ids and figures the tests need.
    """
    year = int(month[:4])
    mon = int(month[5:7])

    user = User.query.filter_by(username="tester").first()
    uid = user.id
    food = ExpenseCategory.query.filter_by(
        user_id=uid, name="Food").first()
    fun = ExpenseCategory.query.filter_by(
        user_id=uid, name="Entertainment").first()

    db.session.add(IncomeRecord(user_id=uid, source="Salary", amount=50000,
                                income_date=date(year, mon, 1)))
    db.session.add(Expense(user_id=uid, category_id=food.id, title="Groceries",
                           amount=6000, expense_date=date(year, mon, 3)))
    db.session.add(Expense(user_id=uid, category_id=fun.id, title="Concert",
                           amount=4000, expense_date=date(year, mon, 8)))
    db.session.commit()

    return {
        "user_id": uid,
        "food_id": food.id,
        "fun_id": fun.id,
        "income": 50000,
        "expenses": 10000,
        "year": year,
        "month_num": mon,
    }
