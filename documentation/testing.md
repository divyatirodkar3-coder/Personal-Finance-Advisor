# Testing Guide

## 1. Test framework

The project uses **pytest**, configured through `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -q --tb=short
filterwarnings =
    ignore::DeprecationWarning
```

All tests live in the `tests/` folder and run against a fresh **in-memory
SQLite database** for every test (see `tests/conftest.py`), so running the
suite never touches or changes your real `instance/finance.db` file.

## 2. What is inside `tests/`

| File | Test functions | What it covers (per its own header comments) |
|------|------------------|-------------------------------------------------|
| `tests/test_auth.py` | 32 | User Authentication Testing — registration, login, logout, sessions, protected routes, password hashing, and data isolation between different user accounts |
| `tests/test_finance.py` | 22 | Income Tracking, Expense Management, and Budget Generation Validation — checks totals and calculations against real numbers pulled back out of the database |
| `tests/test_insights.py` | 20 | AI Recommendation Testing, Dashboard Testing, Financial Report Testing, and Frontend–Backend Communication Testing |
| `tests/test_e2e.py` | 14 | API Integration Testing, End-to-End Workflow Testing, and Performance & Reliability Evaluation |
| `tests/test_health.py` | 10 | Error Handling & Validation, plus a whole-application smoke test that every template renders and every route is reachable without producing a server error |

That is **98 test functions in total** across the five files (counted
directly from the source using `grep -c "^def test_"`).

`tests/conftest.py` defines the shared building blocks used by these tests:

- an `app` fixture that builds a brand-new Flask app with
  `TestingConfig` and an empty in-memory database for each test;
- a `client` fixture (not logged in) and an `auth_client` fixture (already
  logged in as a test user);
- a `user` / `other_user` pair of fixtures, used specifically to prove that
  one account can never see another account's data;
- a `no_live_gemini` fixture that **forces `GEMINI_API_KEY` to be empty for
  every test**, so the suite never depends on an internet connection, never
  calls the real Gemini API, never burns API quota, and cannot randomly slow
  down or fail due to network issues. Tests that specifically want to check
  the "Gemini answered successfully" code path mock
  `ai_service.call_gemini` directly instead of calling the real API;
- a `sample_data` fixture that inserts a realistic month of income and
  expenses (including one category that goes over its budget) for tests
  that need existing data to work with.

## 3. Running the tests

From the project root, with your virtual environment activated and
`pip install -r requirements.txt` already run (this installs `pytest` too):

```bash
pytest
```

Useful variations:

```bash
# Run one file only
pytest tests/test_auth.py

# Run one test function only
pytest tests/test_finance.py::test_total_expenses_matches_records

# Show full output instead of the short traceback style
pytest -v

# Stop at the first failure
pytest -x
```

pytest will print a line of dots (or `F` for a failing test) for each test it
runs, followed by a summary such as `98 passed in 3.21s` if every test
passes, or a detailed traceback for any test that fails.

> This documentation does not claim a specific pass/fail result for this
> copy of the project, since that depends on your local environment,
> installed package versions, and any changes you make. Run the command
> above yourself to see the current result.

## 4. Manual / live-server helper scripts

Two extra scripts exist outside the pytest suite, for checking things pytest
does not cover on its own:

- **`scripts/debug_logout.py`** — a small standalone script (run with
  `python scripts/debug_logout.py`) that builds a test app, creates a user,
  and prints out exactly what happens during logout. It exists specifically
  to make the "remember me" cookie / logout interaction (documented in
  `routes/auth.py`) easy to inspect by eye.
- **`scripts/smoke_live.py`** — starts the **real development server** as a
  subprocess on a real port, makes real HTTP requests against it as an
  actual visitor would, and then shuts it down. This checks the app end to
  end outside of pytest's test client. Run it with:
  ```bash
  python scripts/smoke_live.py            # uses port 5099 by default
  python scripts/smoke_live.py 5050       # or a custom port
  ```

These two scripts are development aids, not part of the automated pytest
suite, and are useful when you want to see behaviour directly rather than
read an assertion result.

## 5. Troubleshooting common errors

### While running `pytest`

| Symptom | Likely cause | Fix |
|----------|---------------|------|
| `ModuleNotFoundError: No module named 'app'` (or similar) when running pytest from another folder | pytest was not run from the project root | Run `pytest` from the same folder that contains `app.py`, `pytest.ini`, and `tests/` |
| A test fails with something related to Gemini / network / API key | Should not normally happen — `no_live_gemini` forces the key empty for every test | Make sure you have not modified `conftest.py`; if a test intentionally mocks `call_gemini`, check that the mock target path matches the current code |
| Tests are slow to start (several seconds per test) | Password hashing defaults to the strong, deliberately slow `scrypt` algorithm | `TestingConfig` already switches to a cheap iteration count (`SECURITY_PASSWORD_HASH = "pbkdf2:sha256:1000"`) for tests only; production/development configs correctly keep the strong default |
| `sqlite3.OperationalError: database is locked` while running tests | Very unlikely, since tests use an in-memory database — more likely another process (like the running dev server) is holding `instance/finance.db` | Stop any other running instance of the app before testing, though this should not normally interfere since tests use `sqlite:///:memory:` |

### While running the app itself (manually testing pages)

| Symptom | Likely cause | Fix |
|----------|---------------|------|
| A page shows a plain "Internal Server Error" instead of the friendly error page | This should not happen — `app.py` defines a catch-all handler for exactly this | Check the terminal running `python app.py` for the logged traceback (`app.logger.exception(...)`); the detail is intentionally kept out of the browser but is always written to the server log |
| You are redirected to the login page unexpectedly | Your session has expired (7-day inactivity limit) or the server was restarted, clearing in-memory state | Log in again |
| Clicking "Log Out" from a bookmark or old link does nothing | Logout only works via **POST**; a plain link (`GET`) intentionally only shows a confirmation page | Use the Log Out button in the navigation bar, not a bookmarked link |
| The AI Advisor always shows "built-in analysis" instead of a Gemini answer | No valid `GEMINI_API_KEY` in `.env`, or the placeholder value is still there | Add a real key and restart the app — see `installation_guide.md`, Step 5 |
| A form submission shows a red error message and reloads the page | This is expected behaviour — server-side validation in `services/validators.py` rejected something (empty field, bad number, bad date, too-long text) | Read the specific message shown; it names exactly which field and rule failed |
| "That category still has N expense(s)" when trying to delete a category | The app deliberately blocks deleting a category that is still in use, to avoid silently losing your expense history | Move or delete those expenses first, then delete the category |
