"""
models/user.py - The User table (User Accounts)

A "model" is just a Python class that describes one database table.
Each class attribute becomes a column (a column is one piece of
information, like "email address").

HOW SQLALCHEMY TALKS TO THE DATABASE
------------------------------------
db.session.add(record)     -> stage a change
db.session.commit()        -> save the changes for real
db.session.rollback()      -> undo unsaved changes
"""

from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def utcnow():
    """Current date+time (used for 'created_at' columns)."""
    return datetime.now(timezone.utc)


class User(db.Model):
    """One row = one registered user."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # NEVER store the real password here. We store this scrambled hash.
    # Two users with the same password get DIFFERENT hashes (because
    # Werkzeug adds random salt), but check_password_hash still works.
    password_hash = db.Column(db.String(255), nullable=False)

    full_name = db.Column(db.String(120), nullable=True)
    currency = db.Column(db.String(8), nullable=False, default="INR")

    # User's monthly savings target - used by Savings Tracking
    savings_goal = db.Column(db.Numeric(12, 2, asdecimal=False),
                             nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # ---------------------------------------------------------------
    # PASSWORD HELPERS
    # ---------------------------------------------------------------
    def set_password(self, raw_password):
        """Turn a plain password into a safe hash and store it."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Return True if the typed password matches the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    # ---------------------------------------------------------------
    # RELATIONSHIPS
    # backref="user" means every IncomeRecord row can jump back to
    # its owner with  record.user
    # cascade="all, delete-orphan" means: delete the user, and their
    # income/expense rows are deleted automatically too.
    # ---------------------------------------------------------------
    incomes = db.relationship(
        "IncomeRecord", backref="user", lazy=True,
        cascade="all, delete-orphan")
    categories = db.relationship(
        "ExpenseCategory", backref="user", lazy=True,
        cascade="all, delete-orphan")
    expenses = db.relationship(
        "Expense", backref="user", lazy=True,
        cascade="all, delete-orphan")
    budgets = db.relationship(
        "BudgetPlan", backref="user", lazy=True,
        cascade="all, delete-orphan")
    reports = db.relationship(
        "MonthlyReport", backref="user", lazy=True,
        cascade="all, delete-orphan")
    analytics = db.relationship(
        "FinancialAnalytics", backref="user", lazy=True,
        cascade="all, delete-orphan")
    savings = db.relationship(
        "SavingsProgress", backref="user", lazy=True,
        cascade="all, delete-orphan")
    ai_insights = db.relationship(
        "AIInsight", backref="user", lazy=True,
        cascade="all, delete-orphan")

    # ---------------------------------------------------------------
    # FLASK-LOGIN INTERFACE
    # Flask-Login asks the logged-in user these four questions.
    # ---------------------------------------------------------------
    @property
    def is_authenticated(self):
        return True          # a real, logged-in user

    @property
    def is_active(self):
        return True          # account is not disabled

    @property
    def is_anonymous(self):
        return False         # not a guest

    def get_id(self):
        """Flask-Login saves this in the cookie to remember the user."""
        return str(self.id)

    def __repr__(self):
        return f"<User {self.username}>"
