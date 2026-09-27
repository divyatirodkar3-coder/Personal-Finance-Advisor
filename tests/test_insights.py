"""
tests/test_insights.py - AI, Analysis, Dashboard and Reports
Spec categories: "AI Recommendation Testing", "Dashboard Testing",
"Financial Report Testing", "Frontend-Backend Communication Testing"

The Gemini tests run with the key REMOVED on purpose, so the suite
never depends on the internet, never burns quota, and always passes.
"""

import pytest

from models import (AIInsight, MonthlyReport, FinancialAnalytics,
                    ExpenseCategory)
from services import ai_service as ai
from services import analysis_service as asvc
from services import report_service as rsvc


# ==================================================================
# FINANCIAL HEALTH EVALUATION
# ==================================================================
def test_health_score_is_bounded(sample_data, app, month):
    score = asvc.health_score(sample_data["user_id"], month)
    assert 0 <= score["score"] <= 100
    assert score["label"] in ("Excellent", "Good", "Needs work", "At risk")


def test_health_score_parts_sum_to_total(sample_data, app, month):
    health = asvc.health_score(sample_data["user_id"], month)
    total = round(sum(r["points"] for r in health["reasons"]))
    assert total == health["score"], "score does not match its parts"


def test_health_score_with_no_data_is_not_a_crash(app, user):
    health = asvc.health_score(user.id, "2020-01")
    assert 0 <= health["score"] <= 100


# ==================================================================
# OVERSPENDING DETECTION
# ==================================================================
def test_overspending_is_detected(sample_data, app, month):
    from services import budget_service as bsvc
    bsvc.set_budget(sample_data["user_id"], month, 1000,
                    category_id=sample_data["food_id"])
    over = asvc.overspending(sample_data["user_id"], month)
    assert [r["name"] for r in over] == ["Food"]


def test_no_overspending_when_within_budget(sample_data, app, month):
    assert asvc.overspending(sample_data["user_id"], month) == []


# ==================================================================
# AI RECOMMENDATION TESTING
# ==================================================================
AI_KEYS = [key for key, _, _ in ai.AI_FEATURES]


@pytest.mark.parametrize("key", AI_KEYS)
def test_every_ai_feature_falls_back(app, sample_data, month, monkeypatch,
                                    key):
    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "")
    result = ai.run_feature(sample_data["user_id"], month, key)
    assert result is not None, "{0} returned None".format(key)
    assert result["is_fallback"] is True
    assert len(result["text"]) > 20, "{0} gave no advice".format(key)


def test_ai_insight_is_saved(app, sample_data, month, monkeypatch):
    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "")
    uid = sample_data["user_id"]
    before = AIInsight.query.filter_by(user_id=uid).count()
    ai.run_feature(uid, month, "analysis")
    assert AIInsight.query.filter_by(user_id=uid).count() == before + 1


def test_ai_budget_plan_never_crashes(app, sample_data, month, monkeypatch):
    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "")
    result = ai.generate_budget_plan(sample_data["user_id"], month, apply=True)
    assert result["applied"] == 0, "fallback must not invent budgets"


def test_ai_falls_back_when_gemini_raises(app, sample_data, month,
                                         monkeypatch):
    """A network error, 429 or bad key must all degrade the same way."""

    def explode(prompt, purpose):
        raise RuntimeError("simulated 429 quota exceeded")

    monkeypatch.setattr(ai, "call_gemini", explode)
    app.config["GEMINI_API_KEY"] = "AIzaFakeKeyThatDoesNotExist1234567890"
    result = ai.run_feature(sample_data["user_id"], month, "health")
    assert result is not None
    assert result["is_fallback"] is True
    assert len(result["text"]) > 10


def test_ai_uses_a_successful_gemini_reply(app, sample_data, month,
                                          monkeypatch):
    """When Gemini answers, its text is used and NOT marked as fallback."""
    monkeypatch.setattr(ai, "call_gemini",
                        lambda prompt, purpose: ("You spent most on Food.",
                                                 True))
    result = ai.run_feature(sample_data["user_id"], month, "analysis")
    assert result["is_fallback"] is False
    assert "Food" in result["text"]


def test_ai_page_works_without_key(app, client, sample_data, month,
                                  monkeypatch):
    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "")
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    assert client.get("/ai/insights").status_code == 200


def test_apply_plan_only_accepts_real_categories(sample_data, app, month):
    """A hallucinating AI must not create nonsense rows."""
    reply = "Food: 4500\nMade Up Category: 999\nTotal: nonsense\n"
    applied = ai.apply_plan(sample_data["user_id"], month, reply)
    assert applied == 1, "only the real category should be applied"
    assert ExpenseCategory.query.filter_by(
        user_id=sample_data["user_id"],
        name="Made Up Category").first() is None



# ==================================================================
# FINANCIAL REPORT TESTING
# ==================================================================
def test_report_numbers_are_correct(sample_data, app, month):
    report = rsvc.build_report(sample_data["user_id"], month)
    assert report["income"] == 50000
    assert report["expenses"] == 10000
    assert report["savings"] == 40000
    assert report["savings_rate"] == 80.0


def test_report_is_saved_and_read_back(sample_data, app, month):
    rsvc.save_report(sample_data["user_id"], month)
    row = MonthlyReport.query.filter_by(user_id=sample_data["user_id"],
                                        month=month).first()
    assert row.total_income == 50000
    assert row.get_category_breakdown() == {"Food": 6000.0,
                                            "Entertainment": 4000.0}


def test_report_resave_does_not_duplicate(sample_data, app, month):
    uid = sample_data["user_id"]
    rsvc.save_report(uid, month)
    rsvc.save_report(uid, month)
    assert MonthlyReport.query.filter_by(user_id=uid).count() == 1


def test_report_page_renders(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    response = client.get("/reports/" + month)
    assert response.status_code == 200
    assert b"Financial Report" in response.data


def test_deleting_report_keeps_underlying_data(sample_data, app, month):
    from models import Expense
    uid = sample_data["user_id"]
    before = Expense.query.filter_by(user_id=uid).count()
    rsvc.save_report(uid, month)
    assert rsvc.delete_report(uid, month) is True
    assert MonthlyReport.query.filter_by(user_id=uid).count() == 0
    assert Expense.query.filter_by(user_id=uid).count() == before, \
        "deleting a report must never delete expenses"


# ==================================================================
# DASHBOARD TESTING
# ==================================================================
def test_dashboard_renders_with_real_numbers(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    body = client.get("/dashboard?month=" + month).data.decode()
    assert "50000.00" in body
    assert "10000.00" in body
    assert "{{" not in body and "{%" not in body


def test_dashboard_has_three_charts(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    body = client.get("/dashboard?month=" + month).data.decode()
    for chart in ('id="categoryChart"', 'id="budgetChart"',
                  'id="trendChart"'):
        assert chart in body


def test_dashboard_creates_analytics_row(sample_data, client, month):
    client.post("/auth/login", data={"login": "tester",
                                     "password": "secret123"})
    client.get("/dashboard?month=" + month)
    row = FinancialAnalytics.query.filter_by(
        user_id=sample_data["user_id"], month=month).first()
    assert row is not None
    assert row.total_income == 50000
