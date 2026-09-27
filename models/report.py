"""
models/report.py - Monthly Reports and Financial Analytics

These two tables STORE the results of our calculations, so we can show
"how was March?" even when the user only added data in April.

The "Text" columns that hold JSON store a list of numbers, for example:
    {"Food": 4200.50, "Rent": 12000, "Transport": 850}
JSON is just a simple way to store a small list inside one text field.
"""

import json

from extensions import db
from models.user import utcnow


class MonthlyReport(db.Model):
    """A finished summary of one month (Income vs Expenses vs Savings)."""

    __tablename__ = "monthly_reports"
    __table_args__ = (
        db.UniqueConstraint("user_id", "month", name="uq_report_user_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False, index=True)

    total_income = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    total_expenses = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    total_savings = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    savings_rate = db.Column(db.Numeric(6, 2, asdecimal=False), default=0)
    budget_total = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    budget_used = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)

    # JSON stored as text
    category_breakdown = db.Column(db.Text, nullable=True)
    overspent_categories = db.Column(db.Text, nullable=True)

    health_score = db.Column(db.Integer, default=0, nullable=False)
    generated_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_category_breakdown(self, data):
        """data = {'Food': 4200.5, 'Rent': 12000}"""
        self.category_breakdown = json.dumps(data)

    def set_overspent_categories(self, data):
        """data = ['Food', 'Entertainment']"""
        self.overspent_categories = json.dumps(data)

    def get_category_breakdown(self):
        return json.loads(self.category_breakdown) if self.category_breakdown else {}

    def get_overspent_categories(self):
        return json.loads(self.overspent_categories) if self.overspent_categories else []


class FinancialAnalytics(db.Model):
    """Per-month spending analysis results used by the dashboard charts."""

    __tablename__ = "financial_analytics"
    __table_args__ = (
        db.UniqueConstraint("user_id", "month", name="uq_analytics_user_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False, index=True)

    total_income = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    total_expenses = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    savings = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)

    top_expense_category = db.Column(db.String(60), nullable=True)
    overspend_count = db.Column(db.Integer, default=0, nullable=False)
    avg_daily_spend = db.Column(db.Numeric(12, 2, asdecimal=False), default=0)
    health_score = db.Column(db.Integer, default=0, nullable=False)

    computed_at = db.Column(db.DateTime, default=utcnow, nullable=False)
