"""
services/defaults.py - Default expense categories created for new users.

WHY?
----
An empty category list makes the app confusing ("which category do I
pick? there are none"). So when someone registers, we give them a
sensible starter set.

The list covers ALL FOUR scenarios in the project specification:
  Scenario 1 (salaried)  -> Rent, Food, Transport, Entertainment
  Scenario 2 (student)   -> Food, Transport, Entertainment, Other
  Scenario 3 (freelancer)-> Transport, Utilities, Other
  Scenario 4 (household) -> Groceries, Utilities, Education, Healthcare
"""

from extensions import db
from models import ExpenseCategory

# (name, colour used by the Chart.js doughnut chart)
DEFAULT_CATEGORIES = [
    ("Rent", "#dc2626"),
    ("Food", "#f97316"),
    ("Transport", "#0ea5e9"),
    ("Entertainment", "#a855f7"),
    ("Groceries", "#16a34a"),
    ("Utilities", "#eab308"),
    ("Education", "#06b6d4"),
    ("Healthcare", "#ec4899"),
    ("Savings", "#10b981"),
    ("Other", "#64748b"),
]


def seed_default_categories(user_id):
    """Give this new user the starter categories (only once)."""
    already = {
        row.name for row in
        ExpenseCategory.query.filter_by(user_id=user_id).all()
    }
    added = 0
    for name, color in DEFAULT_CATEGORIES:
        if name not in already:
            db.session.add(ExpenseCategory(
                user_id=user_id,
                name=name,
                color=color,
                is_default=True,
            ))
            added += 1
    return added
