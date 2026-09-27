"""
tests/test_auth.py - User Authentication Testing
Spec category: "User Authentication Testing"

Covers: registration, login, logout, session, protected routes,
password hashing, and data isolation between users.
"""

from datetime import date

from extensions import db
from models import User, Expense, ExpenseCategory, IncomeRecord


# ------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------
def test_register_creates_user(client, app):
    client.post("/auth/register", data={
        "username": "rahul", "email": "rahul@test.com",
        "password": "secret123", "confirm_password": "secret123",
        "full_name": "Rahul", "savings_goal": "5000"})
    user = User.query.filter_by(username="rahul").first()
    assert user is not None, "user row was not created"
    assert user.email == "rahul@test.com"
    assert user.savings_goal == 5000


def test_register_hashes_password(client, app):
    client.post("/auth/register", data={
        "username": "rahul", "email": "r@t.com", "password": "secret123",
        "confirm_password": "secret123"})
    user = User.query.filter_by(username="rahul").first()
    assert "secret123" not in user.password_hash, "password stored in plain!"
    assert user.check_password("secret123")


def test_register_seeds_default_categories(client, app):
    client.post("/auth/register", data={
        "username": "rahul", "email": "r@t.com", "password": "secret123",
        "confirm_password": "secret123"})
    user = User.query.filter_by(username="rahul").first()
    count = ExpenseCategory.query.filter_by(user_id=user.id).count()
    assert count == 10, "expected 10 starter categories"


def test_register_rejects_duplicate_username(client, app, user):
    response = client.post("/auth/register", data={
        "username": user.username, "email": "new@test.com",
        "password": "secret123", "confirm_password": "secret123"})
    assert b"already taken" in response.data
    assert User.query.filter_by(username=user.username).count() == 1


def test_register_rejects_duplicate_email(client, app, user):
    response = client.post("/auth/register", data={
        "username": "brandnew", "email": user.email,
        "password": "secret123", "confirm_password": "secret123"})
    assert b"already exists" in response.data


def test_register_rejects_mismatched_passwords(client, app):
    response = client.post("/auth/register", data={
        "username": "rahul", "email": "r@t.com",
        "password": "secret123", "confirm_password": "different"})
    assert b"do not match" in response.data
    assert User.query.filter_by(username="rahul").first() is None


def test_register_rejects_short_password(client, app):
    response = client.post("/auth/register", data={
        "username": "rahul", "email": "r@t.com",
        "password": "123", "confirm_password": "123"})
    assert b"at least 6" in response.data
    assert User.query.filter_by(username="rahul").first() is None


def test_register_rejects_bad_email(client, app):
    response = client.post("/auth/register", data={
        "username": "rahul", "email": "not-an-email",
        "password": "secret123", "confirm_password": "secret123"})
    assert b"valid email" in response.data
    assert User.query.filter_by(username="rahul").first() is None


# ------------------------------------------------------------------
# LOGOUT
# ------------------------------------------------------------------
# These cover the whole logout story: the control is on the page, it
# uses the right HTTP method, it really ends the session, protected
# pages bounce you to login, and you can sign in again afterwards.
# ------------------------------------------------------------------
def test_logout_button_is_visible_on_every_authenticated_page(
        auth_client, month):
    """The user has to be able to SEE and FIND the control."""
    pages = ["/dashboard", "/income", "/expenses", "/budgets", "/savings",
             "/analysis", "/reports", "/ai/insights", "/auth/profile"]
    for path in pages:
        body = auth_client.get(path).data.decode()
        assert "Log Out" in body, path + " has no Log Out control"
        assert 'action="/auth/logout"' in body, \
            path + " has no form posting to /auth/logout"
        assert 'method="POST"' in body, \
            path + " logout form is not a POST"


def test_logout_form_opts_out_of_javascript_validation(auth_client):
    """forms.js disables and relabels POST submit buttons.

    It used to grab the logout button too, which made it say "Saving..."
    and switch itself off. The data-no-validate attribute opts it out.
    """
    body = auth_client.get("/dashboard").data.decode()
    assert "data-no-validate" in body


def test_logout_uses_post_not_a_link(auth_client):
    """A GET link would let any other site log the user out."""
    body = auth_client.get("/dashboard").data.decode()
    assert 'href="/auth/logout"' not in body, \
        "logout must not be a plain link"


def test_get_logout_shows_a_confirmation_page(auth_client):
    """Reaching the URL by hand must not be a bare 405."""
    response = auth_client.get("/auth/logout")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Are you sure" in body
    assert 'method="POST"' in body
    # A GET must NOT actually log anyone out.
    assert auth_client.get("/dashboard").status_code == 200


def test_post_logout_ends_the_session(auth_client):
    assert auth_client.get("/dashboard").status_code == 200
    auth_client.post("/auth/logout")
    assert auth_client.get("/dashboard").status_code == 302


def test_post_logout_redirects_to_login_with_a_message(auth_client):
    response = auth_client.post("/auth/logout", follow_redirects=True)
    body = response.data.decode()
    assert response.status_code == 200
    assert "You have been logged out" in body
    assert "Log In" in body, "should land on the login page"


def test_protected_pages_redirect_to_login_after_logout(auth_client):
    protected = ["/dashboard", "/expenses", "/budgets", "/savings",
                 "/analysis", "/reports", "/ai/insights", "/auth/profile",
                 "/api/summary"]
    auth_client.post("/auth/logout")
    for path in protected:
        response = auth_client.get(path)
        assert response.status_code == 302, path + " was still reachable"
        assert "/auth/login" in response.headers.get("Location", ""), path


def test_the_session_cookie_no_longer_carries_a_user(auth_client, app):
    """After logout the session must not still remember a user id."""
    auth_client.post("/auth/logout")
    with auth_client.session_transaction() as sess:
        assert "_user_id" not in sess, "the session still remembers a user"


def test_user_can_log_in_again_after_logging_out(auth_client, app):
    auth_client.post("/auth/logout")
    response = auth_client.post("/auth/login",
                                data={"login": "tester",
                                      "password": "secret123"},
                                follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers.get("Location", "")
    assert auth_client.get("/dashboard").status_code == 200


def test_logout_when_already_logged_out_goes_to_login(client):
    """No error page for someone who is not signed in."""
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers.get("Location", "")


def test_logout_data_survives_for_next_login(auth_client, app):
    """Logging out is not deleting anything."""
    from models import Expense
    before = Expense.query.count()
    auth_client.post("/auth/logout")
    assert Expense.query.count() == before


def test_logout_works_when_remember_me_was_checked(client, app, user):
    """"Keep me logged in" must not survive a logout.

    Login writes a long-lived remember_token cookie. Logging out has to
    delete that cookie too, otherwise the next request quietly signs the
    user back in and the button looks like it did nothing.
    """
    client.post("/auth/login", data={"login": user.username,
                                     "password": "secret123",
                                     "remember": "y"})
    assert client.get("/dashboard").status_code == 200

    client.post("/auth/logout")

    cookie_name = app.config.get("REMEMBER_COOKIE_NAME", "remember_token")
    jar = client.get("/auth/login")
    assert "remember_token" not in jar.headers.get("Set-Cookie", "")
    assert cookie_name  # the cookie name we expect to be cleared
    assert client.get("/dashboard").status_code == 302, \
        "the remember me cookie logged the user back in"
    assert client.get("/dashboard", follow_redirects=True) \
        .status_code == 200


def test_logout_clears_the_remember_cookie_header(auth_client, app, user):
    """The logout response itself must tell the browser to drop the cookie."""
    auth_client.post("/auth/login", data={"login": user.username,
                                          "password": "secret123",
                                          "remember": "y"})
    response = auth_client.post("/auth/logout")
    header = response.headers.get("Set-Cookie", "")
    cookie_name = app.config.get("REMEMBER_COOKIE_NAME", "remember_token")
    assert cookie_name in header and "Expires=Thu, 01 Jan 1970" in header, \
        "logout did not expire the remember me cookie: {0!r}".format(header)


# ------------------------------------------------------------------
# LOGIN / SESSION
# ------------------------------------------------------------------
def test_login_with_username(client, app, user):
    response = client.post("/auth/login",
                           data={"login": user.username,
                                 "password": "secret123"})
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 200


def test_login_with_email(client, app, user):
    client.post("/auth/login",
                data={"login": user.email.upper(), "password": "secret123"})
    assert client.get("/dashboard").status_code == 200


def test_login_wrong_password_fails(client, app, user):
    response = client.post("/auth/login",
                           data={"login": user.username, "password": "wrong"})
    assert b"Incorrect" in response.data
    assert client.get("/dashboard").status_code == 302


# ------------------------------------------------------------------
# PROFILE
# ------------------------------------------------------------------
def test_profile_update(auth_client, app, user):
    auth_client.post("/auth/profile", data={
        "action": "details", "full_name": "New Name",
        "email": "new@test.com", "currency": "USD", "savings_goal": "9000"})
    fresh = db.session.get(User, user.id)
    assert fresh.full_name == "New Name"
    assert fresh.savings_goal == 9000


def test_password_change(auth_client, app, user):
    auth_client.post("/auth/profile", data={
        "action": "password", "current_password": "secret123",
        "new_password": "newpass1", "confirm_password": "newpass1"})
    fresh = db.session.get(User, user.id)
    assert fresh.check_password("newpass1")
    assert not fresh.check_password("secret123")


def test_password_change_needs_correct_current(auth_client, app, user):
    response = auth_client.post("/auth/profile", data={
        "action": "password", "current_password": "WRONG",
        "new_password": "newpass1", "confirm_password": "newpass1"})
    assert b"incorrect" in response.data.lower()
    assert db.session.get(User, user.id).check_password("secret123")


# ------------------------------------------------------------------
# DATA ISOLATION  (the most important tests in the project)
# ------------------------------------------------------------------
def test_user_cannot_see_other_users_data(client, app, user, other_user):
    db.session.add(Expense(user_id=user.id, title="Secret",
                           amount=999, expense_date=date.today()))
    db.session.add(IncomeRecord(user_id=user.id, source="Hidden",
                                amount=12345, income_date=date.today()))
    db.session.commit()

    client.post("/auth/login", data={"login": other_user.username,
                                     "password": "secret123"})
    body = client.get("/expenses").data.decode()
    assert "Secret" not in body
    assert "Hidden" not in body

    summary = client.get("/api/summary").get_json()
    assert summary["expenses"] == 0
    assert summary["income"] == 0


def test_cannot_delete_other_users_expense(app, client, user, other_user):
    from models import ExpenseCategory
    cat = ExpenseCategory.query.filter_by(user_id=user.id).first()
    db.session.add(Expense(user_id=user.id, category_id=cat.id, title="Mine",
                           amount=10, expense_date=date.today()))
    db.session.commit()
    mine = Expense.query.filter_by(user_id=user.id).first()

    client.post("/auth/login", data={"login": other_user.username,
                                     "password": "secret123"})
    client.post("/expenses/{0}/delete".format(mine.id))
    assert db.session.get(Expense, mine.id) is not None, \
        "another user deleted this expense!"


def test_deleting_one_user_leaves_others_data(app, user, other_user):
    db.session.add(Expense(user_id=user.id, title="Keep me",
                           amount=50, expense_date=date.today()))
    db.session.commit()

    db.session.delete(db.session.get(User, other_user.id))
    db.session.commit()

    assert Expense.query.filter_by(user_id=user.id).count() == 1, \
        "cascade delete removed the wrong user's data"


def test_login_unknown_user_gives_same_message(client, app, user):
    """Must not reveal whether the username exists.

    Only the error MESSAGE is compared. The form itself echoes the typed
    username back so the user does not have to retype it, and that is
    intentional - it leaks nothing about whether the account exists.
    """
    ghost = client.post("/auth/login",
                        data={"login": "ghost", "password": "secret123"})
    wrong = client.post("/auth/login",
                        data={"login": user.username, "password": "wrong"})
    assert b"Incorrect username/email or password." in ghost.data
    assert b"Incorrect username/email or password." in wrong.data
    assert client.get("/dashboard").status_code == 302


# (The full logout suite lives in the LOGOUT section at the top of this file,
#  next to the other session tests.)


# ------------------------------------------------------------------
# PROTECTED ROUTES
# ------------------------------------------------------------------
PROTECTED = ["/dashboard", "/income", "/expenses", "/budgets", "/savings",
             "/analysis", "/reports", "/ai/insights", "/auth/profile",
             "/api/summary"]


def test_all_pages_require_login(client):
    for path in PROTECTED:
        assert client.get(path).status_code == 302, \
            "{0} was not protected".format(path)
