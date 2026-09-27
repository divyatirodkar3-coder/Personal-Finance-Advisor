"""
models/ai_insight.py - Stores AI responses (supporting table)

This is NOT one of the eight database requirements. It is a small
supporting table so AI advice can be saved and shown again later
without calling Gemini twice for the same question.
"""

from extensions import db
from models.user import utcnow


class AIInsight(db.Model):
    """One saved Gemini AI answer."""

    __tablename__ = "ai_insights"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # budget | analysis | recommendations | emergency_fund | health
    insight_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=True)

    # The full text answer from Gemini (or from our offline fallback)
    content = db.Column(db.Text, nullable=False)

    # True means Gemini was unavailable and we used the built-in
    # rule-based advice instead, so the page can show an honest badge.
    is_fallback = db.Column(db.Boolean, default=False, nullable=False)

    month = db.Column(db.String(7), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
