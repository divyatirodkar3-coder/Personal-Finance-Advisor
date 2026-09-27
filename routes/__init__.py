"""
routes/__init__.py - Collects all blueprints so app.py can register them.

BLUEPRINTS_TODO
---------------
New route files must be added here AND registered in app.py.
Keeping the list in one place means we never forget one.
"""

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.income import income_bp
from routes.expenses import expense_bp
from routes.budgets import budget_bp
from routes.savings import savings_bp
from routes.analysis import analysis_bp
from routes.ai import ai_bp
from routes.api import api_bp
from routes.reports import report_bp

ALL_BLUEPRINTS = [auth_bp, dashboard_bp, income_bp, expense_bp,
                  budget_bp, savings_bp, analysis_bp, ai_bp, api_bp,
                  report_bp]

__all__ = ["ALL_BLUEPRINTS", "auth_bp", "dashboard_bp", "income_bp",
           "expense_bp", "budget_bp", "savings_bp", "analysis_bp",
           "ai_bp", "api_bp", "report_bp"]
