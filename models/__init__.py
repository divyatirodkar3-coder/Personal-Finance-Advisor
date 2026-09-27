"""
models/__init__.py - Loads every table definition.

WHY THIS FILE EXISTS
--------------------
Python only creates a database table when the class is IMPORTED.
So app.py does:  from models import *   <- runs this file
and every model class below gets registered with SQLAlchemy,
which is what makes db.create_all() work.
"""

from models.user import User
from models.finance import IncomeRecord, ExpenseCategory, Expense
from models.budget import BudgetPlan
from models.report import MonthlyReport, FinancialAnalytics
from models.savings import SavingsProgress
from models.ai_insight import AIInsight

__all__ = [
    "User",
    "IncomeRecord",
    "ExpenseCategory",
    "Expense",
    "BudgetPlan",
    "MonthlyReport",
    "FinancialAnalytics",
    "SavingsProgress",
    "AIInsight",
]
