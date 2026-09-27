"""
tests/test_health.py - Templates, routes and overall application health
Spec category: "Error Handling & Validation" plus a whole-app smoke test.

These tests do not check business rules. They prove the app is wired up
correctly: every template parses, every route is reachable, and nothing
in the URL map produces a 500.
"""

import re

import pytest


# ==================================================================
# TEMPLATE PARSING
# ==================================================================
def test_every_template_parses(app):
    """Catch a broken {% tag %} or unclosed Jinja block before a user does."""
    env = app.jinja_env
    names = env.list_templates()
    assert len(names) >= 15, "templates are missing"

    broken = []
    for name in names:
        try:
            source = env.loader.get_source(env, name)[0]
            env.parse(source)
        except Exception as exc:              # noqa: BLE001 - we want the name
            broken.append("{0}: {1}".format(name, exc))

    assert broken == [], "template syntax errors:\n" + "\n".join(broken)


def test_base_template_defines_the_blocks(app):
    env = app.jinja_env
    source = env.loader.get_source(env, "base.html")[0]
    for block in ("{% block content %}", "{% endblock %}"):
        assert block in source, "base.html is missing " + block


def test_login_page_has_no_unrendered_jinja(auth_client):
    """A stray {{ }} in a page would be visible to every user."""
    for path in ("/auth/login", "/auth/register"):
        body = auth_client.get(path).data.decode()
        assert "{{" not in body, path + " has an unrendered expression"
        assert "{%" not in body, path + " has an unrendered tag"


# ==================================================================
# ROUTE MAP
# ==================================================================
def test_url_map_has_the_expected_blueprints(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    for name in ("auth.login", "auth.register", "auth.logout",
                 "dashboard.index", "api.summary", "api.trend",
                 "ai.insights"):
        assert name in endpoints, "missing endpoint " + name


def test_no_duplicate_endpoint_names(app):
    seen = [rule.endpoint for rule in app.url_map.iter_rules()]
    duplicates = {e for e in seen if seen.count(e) > 1}
    assert duplicates == set(), "duplicate endpoints: " + str(duplicates)


def _build_path(rule, month):
    """Fill a rule's <converter:arg> parts so it can actually be requested."""
    def replace(match):
        name = match.group(2)
        if name in ("month", "year_month"):
            return month
        return "1"          # int or path ids

    return re.sub(r"<(?:([^:>]+):)?([^>]+)>", replace, rule.rule)


@pytest.mark.parametrize("logged_in", [False, True])
def test_no_route_ever_returns_a_server_error(app, client, auth_client,
                                             month, logged_in):
    """Walk the whole URL map. Anything reaching 500 is a real bug."""
    browser = auth_client if logged_in else client
    failures = []

    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods or rule.endpoint == "static":
            continue

        path = _build_path(rule, month)
        try:
            response = browser.get(path)
        except Exception as exc:              # noqa: BLE001
            failures.append("{0} raised {1}: {2}".format(
                path, type(exc).__name__, exc))
            continue

        if response.status_code >= 500:
            failures.append("{0} -> {1}".format(path, response.status_code))

    assert failures == [], "server errors:\n" + "\n".join(failures)


# ==================================================================
# ERROR HANDLING
# ==================================================================
def test_unknown_page_shows_a_friendly_404(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    body = response.data.decode()
    assert "404" in body
    assert "{{" not in body and "{%" not in body


def test_404_page_looks_like_the_real_page_not_a_traceback(client):
    """A stack trace must never reach the browser."""
    body = client.get("/nope").data.decode()
    # Note: "SQLAlchemy" on its own appears in the footer tech-stack line,
    # so only genuine exception signatures are checked here.
    for leak in ("Traceback", 'File "', "werkzeug.debug", "jinja2.exceptions",
                 "sqlalchemy.exc", "werkzeug.exceptions"):
        assert leak not in body, "the 404 page leaks " + leak


@pytest.mark.parametrize("code", [400, 403, 404, 500])
def test_error_templates_exist_and_are_valid(app, code):
    """Each error page must exist, parse, and mention its own status code.

    These extend base.html, which needs url_for() and current_user, so we
    check the source rather than rendering them in isolation. The 404 page
    is additionally rendered for real in the test above.
    """
    env = app.jinja_env
    name = next((n for n in env.list_templates()
                 if n.endswith("{0}.html".format(code))), None)
    assert name is not None, "no template for the {0} page".format(code)

    source = env.loader.get_source(env, name)[0]
    env.parse(source)                       # raises if the Jinja is broken
    assert str(code) in source, name + " does not mention " + str(code)


def test_security_headers_are_sent(client):
    response = client.get("/auth/login")
    headers = {k.lower() for k in response.headers.keys()}
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
