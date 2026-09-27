"""
scripts/debug_logout.py - Reproduce the logout problem and show the truth.

Run:  python scripts/debug_logout.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                                  # noqa: E402
from config import TestingConfig                            # noqa: E402
from extensions import db                                   # noqa: E402
from models import User                                      # noqa: E402
from services.defaults import seed_default_categories        # noqa: E402


def show(label, value):
    print("  {0:<34} {1}".format(label, value))


def main():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        user = User(username="probe", email="probe@test.com",
                    full_name="Probe")
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        seed_default_categories(user.id)

    client = app.test_client()

    print("\nSTEP 1 - log in")
    response = client.post("/auth/login",
                           data={"login": "probe", "password": "secret123"})
    show("POST /auth/login status", response.status_code)
    show("session has _user_id", "_user_id" in dict(client.session_transaction().__enter__()))

    print("\nSTEP 2 - is the Log Out control in the page?")
    dashboard = client.get("/dashboard")
    body = dashboard.data.decode()
    show("GET /dashboard status", dashboard.status_code)
    show("literal 'Log Out' present", "Log Out" in body)
    show("case-insensitive 'logout' present", "logout" in body.lower())

    match = re.search(r"<form[^>]*action=[\"']/auth/logout[\"'][^>]*>.*?</form>",
                      body, re.S)
    show("logout <form> tag found", bool(match))
    if match:
        snippet = " ".join(match.group(0).split())
        print("      markup: " + snippet[:150])

    button = re.search(r"<button[^>]*>\s*Log Out\s*</button>", body)
    show("Log Out <button> found", bool(button))

    print("\nSTEP 3 - the URL map entry for logout")
    for rule in app.url_map.iter_rules():
        if "logout" in rule.rule:
            show("rule", rule.rule)
            show("methods", sorted(rule.methods - {"HEAD", "OPTIONS"}))
            show("endpoint", rule.endpoint)

    print("\nSTEP 4 - a browser-style GET to /auth/logout")
    get = client.get("/auth/logout")
    show("GET /auth/logout status", get.status_code)
    if get.status_code == 405:
        show("Allow header", get.headers.get("Allow", "(none)"))

    print("\nSTEP 5 - the real POST logout")
    post = client.post("/auth/logout", follow_redirects=False)
    show("POST /auth/logout status", post.status_code)
    show("redirects to", post.headers.get("Location", "(none)"))

    print("\nSTEP 6 - is the session really gone?")
    protected = client.get("/dashboard")
    show("GET /dashboard after logout", protected.status_code)
    show("Location", protected.headers.get("Location", "(none)"))

    print("\nSTEP 7 - can the same user log in again?")
    again = client.post("/auth/login",
                        data={"login": "probe", "password": "secret123"},
                        follow_redirects=False)
    show("POST /auth/login status", again.status_code)
    show("redirects to", again.headers.get("Location", "(none)"))
    show("GET /dashboard now", client.get("/dashboard").status_code)

    with app.app_context():
        db.drop_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
