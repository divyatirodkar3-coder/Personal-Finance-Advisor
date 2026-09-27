"""
routes/auth.py - Registration, Login, Logout and Profile.

WHAT IS A BLUEPRINT?
-------------------
A Blueprint is a group of related routes that Flask registers as one
unit. Instead of many routes crowding app.py, we split them:
  routes/auth.py      -> login, register, logout, profile
  routes/income.py    -> income pages
  routes/expenses.py  -> expense pages

WHAT IS @login_required?
------------------------
A decorator (a wrapper). It checks "is someone logged in?".
If not, it redirects to the login page. This is how we protect
financial pages so nobody can see another person's money.
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)
from flask_login import (login_user, logout_user, login_required,
                         current_user)

from extensions import db, login_manager
from models import User
from services.defaults import seed_default_categories
from services.validators import parse_amount, is_valid_email, normalise_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ------------------------------------------------------------------
# USER LOADER  (required by Flask-Login)
# ------------------------------------------------------------------
# After login, Flask stores the user's ID inside a signed cookie.
# On every later request, Flask calls this function to turn that ID
# back into a real User object. Returning None means "logged out".
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))



# ------------------------------------------------------------------
# REGISTER
# ------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = normalise_email(request.form.get("email"))
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        full_name = (request.form.get("full_name") or "").strip()
        goal_raw = (request.form.get("savings_goal") or "").strip()

        # ---------- validation ----------
        errors = []

        if not username:
            errors.append("Username is required.")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        elif len(username) > 80:
            errors.append("Username must be under 80 characters.")
        elif not username.replace("_", "").replace(".", "").isalnum():
            errors.append("Username can use letters, numbers, dot and underscore only.")

        if not email:
            errors.append("Email is required.")
        elif not is_valid_email(email):
            errors.append("Please enter a valid email address.")

        if not password:
            errors.append("Password is required.")
        elif len(password) < 6:
            errors.append("Password must be at least 6 characters.")

        if password != confirm:
            errors.append("Passwords do not match.")

        # The savings goal is OPTIONAL in the form. An empty box simply
        # means "no goal set yet" (0), so it must not block registration.
        goal_raw = (request.form.get("savings_goal") or "").strip()
        if goal_raw == "":
            goal = 0
        else:
            goal, goal_error = parse_amount(goal_raw, "Savings goal",
                                            allow_zero=True)
            if goal_error:
                errors.append(goal_error)

        # ---------- duplicate checks ----------
        if username and User.query.filter_by(username=username).first():
            errors.append("That username is already taken.")
        if email and User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("auth/register.html", username=username,
                                   email=email, full_name=full_name,
                                   savings_goal=goal_raw)

        # ---------- create the user ----------
        user = User(username=username, email=email,
                    full_name=full_name or username,
                    currency="INR", savings_goal=goal)
        user.set_password(password)   # hashed - never stored as plain text
        db.session.add(user)
        db.session.commit()

        # Give the new user the starter expense categories
        seed_default_categories(user.id)

        login_user(user)
        flash("Welcome! Your account is ready. Start by adding your income.",
              "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/register.html", username="", email="",
                           full_name="", savings_goal="")


def _safe_next(target):
    """Only allow redirects to our own pages (blocks open-redirect tricks)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


# ------------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        login_id = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        if not login_id or not password:
            flash("Please enter both your username/email and password.", "danger")
            return render_template("auth/login.html", login=login_id)

        # Accept EITHER the username OR the email address
        user = User.query.filter(
            (User.username == login_id)
            | (User.email == normalise_email(login_id))
        ).first()

        # One message for both cases, so we never reveal which
        # usernames or emails actually exist.
        if not user or not user.check_password(password):
            flash("Incorrect username/email or password.", "danger")
            return render_template("auth/login.html", login=login_id)

        login_user(user, remember=remember)
        session.permanent = True

        flash(f"Welcome back, {user.full_name or user.username}!", "success")
        return redirect(_safe_next(request.args.get("next"))
                        or url_for("dashboard.index"))

    return render_template("auth/login.html", login="")


# ------------------------------------------------------------------
# LOGOUT
# ------------------------------------------------------------------
# WHY POST IS THE ONLY METHOD THAT ACTUALLY LOGS YOU OUT
# Logging out destroys server-side state, so it must not happen just
# because a browser fetched a URL. A GET would let any other site log
# the user out with a hidden <img> tag, and a link prefetcher would log
# people out simply by opening a page. POST keeps that safe.
#
# GET is still allowed, but it only shows a small "are you sure?" page.
# That way typing /auth/logout in the address bar still works instead of
# hitting a bare 405, and the destructive click stays a deliberate POST.
@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    if request.method == "GET":
        return render_template("auth/logout.html")

    logout_user()
    session.clear()

    # WHY THE MARKER HAS TO BE PUT BACK
    # logout_user() does not delete the "remember me" cookie itself. It only
    # writes session["_remember"] = "clear", and Flask-Login's after_request
    # hook is what actually sends the cookie-deletion header later. The
    # session.clear() above wipes that marker, so the browser keeps its
    # remember_token cookie and the very next request logs the user straight
    # back in - logout looks like it did nothing. Put the marker back.
    session["_remember"] = "clear"

    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------
# PROFILE  (User Profile Management)
# ------------------------------------------------------------------
@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        action = request.form.get("action", "details")

        # ---- update the basic details ----
        if action == "details":
            full_name = (request.form.get("full_name") or "").strip()
            email = normalise_email(request.form.get("email"))
            currency = (request.form.get("currency") or "INR").strip().upper()[:8]
            goal, goal_error = parse_amount(
                request.form.get("savings_goal"), "Savings goal", allow_zero=True)

            errors = []
            if full_name and len(full_name) > 120:
                errors.append("Full name is too long.")
            if not is_valid_email(email):
                errors.append("Please enter a valid email address.")
            else:
                taken = User.query.filter_by(email=email).first()
                if taken and taken.id != current_user.id:
                    errors.append("That email is already used by another account.")
            if goal_error:
                errors.append(goal_error)

            if errors:
                for message in errors:
                    flash(message, "danger")
            else:
                current_user.full_name = full_name
                current_user.email = email
                current_user.currency = currency or "INR"
                current_user.savings_goal = goal
                db.session.commit()
                flash("Profile updated successfully.", "success")

        # ---- change the password ----
        elif action == "password":
            current_pw = request.form.get("current_password") or ""
            new_pw = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""

            if not current_user.check_password(current_pw):
                flash("Your current password is incorrect.", "danger")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "danger")
            elif new_pw != confirm:
                flash("New passwords do not match.", "danger")
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash("Password changed successfully.", "success")

    counts = {
        "incomes": len(current_user.incomes),
        "expenses": len(current_user.expenses),
        "categories": len(current_user.categories),
    }
    return render_template("profile.html", counts=counts)

