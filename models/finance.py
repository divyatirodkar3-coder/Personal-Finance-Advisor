"""
models/finance.py - Income Records, Expense Categories, Expense Transactions

These three tables are the heart of the app. Everything else (budgets,
reports, analytics) is calculated FROM these.
"""

from extensions import db
from models.user import utcnow


class IncomeRecord(db.Model):
    """Money the user received (salary, freelance payment, allowance...)."""

    __tablename__ = "income_records"

    id = db.Column(db.Integer, primary_key=True)

    # THE OWNERSHIP LINK.
    # Every financial row points back to the user who owns it.
    # This is what stops one user from ever seeing another's money.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    source = db.Column(db.String(120), nullable=False)
    income_type = db.Column(db.String(30), nullable=False, default="other")
    amount = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    income_date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def __repr__(self):
        return f"<Income {self.source} {self.amount}>"


class ExpenseCategory(db.Model):
    """A spending bucket, e.g. Rent, Food, Transport, Healthcare.

    Each user gets their own set of categories, so two users never
    share or mix up category records.
    """

    __tablename__ = "expense_categories"
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_category_user_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    name = db.Column(db.String(60), nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    # Hex colour used by the Chart.js doughnut chart
    color = db.Column(db.String(20), default="#2563eb", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    expenses = db.relationship(
        "Expense", backref="category", lazy=True,
        cascade="all, delete-orphan")
    budgets = db.relationship("BudgetPlan", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Expense(db.Model):
    """One expense entry - e.g. 'Lunch' 250 rupees under 'Food'."""

    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # NULL is allowed here on purpose: an expense can exist before the
    # user assigns it a category.
    category_id = db.Column(
        db.Integer, db.ForeignKey("expense_categories.id"),
        nullable=True, index=True)

    title = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, index=True)
    payment_method = db.Column(db.String(30), default="cash", nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def __repr__(self):
        return f"<Expense {self.title} {self.amount}>"
