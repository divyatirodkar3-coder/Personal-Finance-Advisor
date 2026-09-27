"""
extensions.py - Shared Flask tools.

Why a separate file?
--------------------
These objects (the database and the login manager) are needed by many
different files, but those files need to import each other in a circle.
Python cannot handle circular imports, so we create the objects ONCE here
and let every other file import them from this single place.

This is the standard "avoid circular imports" trick in Flask projects.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# The database object. Used like: db.session.add(...)  db.session.commit()
db = SQLAlchemy()

# Handles "who is logged in?" for the whole app
login_manager = LoginManager()

# If a logged-out user visits a protected page, send them here
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access that page."
login_manager.login_message_category = "info"
