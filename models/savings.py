"""
models/savings.py - Savings Progress Records

Tracks "how much did I save this month?" against the user's savings goal
set in their profile.
"""

from extensions import db
from models.user import utcnow


class SavingsProgress(db.Model):
    """One row per user per month showing savings achieved."""

    __tablename__ = "savings_progress"
    __table_args__ = (
        db.UniqueConstraint("user_id", "month", name="uq_savings_user_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False, index=True)

    # Copied from the user profile when the record is created, so that
    # changing the goal later does not rewrite history.
    target_amount = db.Column(
        db.Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    # Real calculation: total income - total expenses
    saved_amount = db.Column(
        db.Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    # 'achieved' | 'on_track' | 'behind'
    status = db.Column(db.String(20), default="behind", nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
