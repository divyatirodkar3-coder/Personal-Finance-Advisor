# Personal Finance Advisor Bot

A web application, built with **Flask (Python)**, that helps a person track their
income and expenses, plan monthly budgets, watch their savings progress, and get
AI-generated financial advice powered by **Google Gemini**.

It was built as a college engineering project and is meant to be run locally on
your own computer.

---

## What it does

- **User accounts** — register, log in, log out, and edit your profile (name,
  email, currency, monthly savings goal, password change).
- **Income tracking** — record money received (salary, freelance, allowance,
  business, investment, other) and see totals per month.
- **Expense tracking** — record spending against your own custom categories
  (with a starter set of categories created automatically), edit/delete entries,
  and see a category-wise and week-wise breakdown.
- **Budget planning** — set a spending limit per category (or one overall
  monthly limit), and see planned vs. actually spent, with a rule-based
  suggestion engine that proposes sensible limits from your real spending.
- **Savings tracking** — savings are always calculated as *income − expenses*
  (never typed in), compared against a savings target, with a status that
  takes into account how far through the month you are.
- **Spending analysis** — a 0–100 "financial health score" (savings health +
  budget discipline + spending level), overspending detection, top spending
  categories, average daily spend, and month-to-month comparison.
- **Monthly reports** — a full report for any month, which can be viewed live
  or "frozen" (saved permanently) so it stays the same even if you edit that
  month's data later.
- **AI Advisor** — seven Gemini-powered insights (spending analysis,
  overspending detection, savings recommendations, financial health
  evaluation, cost optimisation, emergency fund guidance, personalised
  insights) plus an AI budget-plan generator. If Gemini isn't configured or
  isn't reachable, the app automatically falls back to a built-in, rule-based
  version of the same advice so the page never breaks.
- **Dashboard** — one page pulling everything together, with three charts
  (category breakdown, budget performance, income/expense/savings trend)
  drawn by Chart.js from a small internal JSON API.

## Tech stack

| Layer            | Technology                                            |
|-------------------|--------------------------------------------------------|
| Backend framework | Flask 3.x (Python)                                     |
| Database          | SQLite, accessed through Flask-SQLAlchemy / SQLAlchemy 2.x |
| Authentication    | Flask-Login, password hashing via Werkzeug (scrypt)     |
| AI                | Google Gemini via the `google-genai` Python SDK          |
| Frontend          | Jinja2 templates, plain CSS, vanilla JavaScript, Chart.js (CDN) |
| Configuration     | `python-dotenv` (`.env` file)                            |
| Testing           | pytest                                                  |

## Project structure

```
Personal_Finance_Advisor_Bot/
├── app.py                 # Flask app factory, routes for /, /health, error pages
├── config.py               # Settings (reads .env), Development/Testing configs
├── extensions.py            # Shared db and login_manager objects
├── requirements.txt         # Python dependencies
├── pytest.ini               # pytest configuration
├── run_public.ps1           # (Windows) run the app + expose it via ngrok
├── .env.example             # Template for the required environment variables
├── models/                  # SQLAlchemy database tables
├── routes/                  # Flask blueprints (one file per feature area)
├── services/                 # Business logic used by the routes
├── templates/                # Jinja2 HTML templates
├── static/                   # CSS and JavaScript
├── scripts/                  # Small manual/debug helper scripts
├── tests/                    # pytest test suite
└── instance/                 # SQLite database file created at runtime (ignored by git)
```

See `documentation/system_architecture.md` for the full explanation of how
these pieces fit together.

## Getting started (short version)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your environment file
copy .env.example .env         # Windows
cp .env.example .env           # macOS / Linux
# then open .env and fill in SECRET_KEY (and GEMINI_API_KEY if you want live AI)

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

For the full step-by-step guide (including what each `.env` value means and
how to enable the AI features), see
[`documentation/installation_guide.md`](documentation/installation_guide.md).

## Documentation

Detailed documentation lives in the [`documentation/`](documentation/) folder:

- [`project_overview.md`](documentation/project_overview.md) — what the
  project does, its features, and its technology in more detail.
- [`system_architecture.md`](documentation/system_architecture.md) — how the
  code is organised, the database design, and the security measures in place.
- [`installation_guide.md`](documentation/installation_guide.md) — full setup
  and configuration instructions.
- [`user_guide.md`](documentation/user_guide.md) — a walkthrough of every page
  in the app, written for someone using it for the first time.
- [`testing.md`](documentation/testing.md) — how to run the automated test
  suite, what it covers, and troubleshooting for common errors.

## Notes

- The database is a single SQLite file created automatically the first time
  you run the app (`instance/finance.db`). It is not included in version
  control.
- The `GEMINI_API_KEY` is optional. Without it, the AI Advisor page still
  works, but every insight is generated by the app's own built-in rules
  instead of Gemini, and is clearly labelled as such.
- No `.env` file, API key, or other secret is included anywhere in this
  project or its documentation — you provide your own in a local `.env` file.
