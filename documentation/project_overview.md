# Project Overview

## 1. What problem does this project solve?

Most people who want to track their personal finances either use a paper
notebook or a generic spreadsheet, neither of which tells them anything
beyond raw numbers. The **Personal Finance Advisor Bot** is a small web
application that lets one person:

1. Record what money comes in and what money goes out.
2. Organise spending into categories they define themselves.
3. Set monthly spending limits (budgets) and see, in real time, whether they
   are on track or over budget.
4. See a calculated savings figure (never typed in — always
   income − expenses) against a savings goal.
5. Get a plain-English explanation of their financial situation, either from
   a rule-based engine built into the app, or from Google's Gemini AI when a
   key is configured.

The application is designed around **four realistic user scenarios**, visible
directly in the code (`services/finance_service.py` and
`services/defaults.py`):

- a salaried professional,
- a college student living on an allowance,
- a freelancer with income from multiple clients,
- a household/family managing shared income.

This shows up concretely as the six income types offered on the "Add Income"
form (`salary`, `freelance`, `allowance`, `business`, `investment`, `other`)
and the ten starter expense categories every new account receives
automatically (Rent, Food, Transport, Entertainment, Groceries, Utilities,
Education, Healthcare, Savings, Other).

## 2. Core features (as implemented)

### 2.1 User accounts (`routes/auth.py`, `models/user.py`)
- Registration with username, email, password, optional full name and
  optional starting savings goal.
- Server-side validation: username length/characters, valid email format,
  minimum 6-character password, password confirmation match, and duplicate
  username/email checks.
- Passwords are never stored in plain text — `User.set_password()` uses
  Werkzeug's `generate_password_hash`, and `User.check_password()` uses
  `check_password_hash` to verify a login attempt.
- Login accepts either a username or an email address in the same field.
- Logout is deliberately a **POST-only** action (a small "are you sure?" page
  is shown for a plain GET) so that visiting a URL or an embedded image can
  never silently log a user out.
- A profile page lets the user update their name/email/currency/savings goal
  and change their password.

### 2.2 Income tracking (`routes/income.py`)
- Add, list (by month), and delete income records.
- Each record has a source, an income type, an amount, a date, and optional
  notes.
- Every query is filtered by the logged-in user's ID, so one account can
  never see another account's records.

### 2.3 Expense tracking and categories (`routes/expenses.py`)
- Add, edit, delete, and list expenses (title, amount, date, payment method,
  optional category, optional notes).
- Manage categories: create a new category with a name and a colour (used by
  the dashboard chart), and delete a category — but only if it has no
  expenses attached, to avoid silently deleting financial history.
- A weekly spending breakdown is calculated on top of the daily records
  (`finance_service.weekly_spending`).

### 2.4 Budget planning (`routes/budgets.py`, `services/budget_service.py`)
- Set either a **category budget** (a limit for one category in one month)
  or an **overall monthly budget** (a single limit with no category
  attached).
- For every budgeted category the app shows planned amount, amount actually
  spent, amount remaining, percentage used, and a status of `on_track`,
  `warn` (≥ 80% used), or `over` (spending has passed the limit).
- A **rule-based suggestion engine** (`suggest_allocation`) proposes a budget
  for every category based on what was *actually* spent, capping total
  suggested spending at 70% of income and reserving 20% for savings. A
  suggestion can be applied with one click to create a real budget.

### 2.5 Savings tracking (`routes/savings.py`, `services/savings_service.py`)
- The savings amount itself is **calculated**, never entered by hand:
  `saved = total income − total expenses` for the month.
- The user can only set a **target** for each month (or rely on the default
  goal stored on their profile).
- The status (`achieved`, `on_track`, `behind`, or `no_target`) is
  time-aware: it compares progress against how far through the month has
  actually passed, so being at 50% of the goal on day 15 is treated
  differently from being at 50% on day 30.
- A history of savings per month and an all-time summary (months tracked,
  months where the goal was achieved, achievement rate) are shown.

### 2.6 Spending analysis (`routes/analysis.py`, `services/analysis_service.py`)
- A **financial health score out of 100**, broken into three transparent
  parts so it can be explained rather than being a "black box":
  - Savings health — up to 40 points, based on savings rate vs. a 20% ideal.
  - Budget discipline — up to 30 points, based on the share of budgeted
    categories that are within their limit.
  - Spending level — up to 30 points, based on expenses as a share of
    income (70% or less is treated as healthy).
- Overspending detection (categories over budget) and a "near limit" list
  (categories between 80–100% of their budget).
- Top spending categories, average daily spend (day-count aware for the
  current, unfinished month), and a month-over-month expense comparison.
- Plain-language, rule-based insight sentences built directly from the
  numbers above (`analysis_service.insights`).

### 2.7 Monthly reports (`routes/reports.py`, `services/report_service.py`)
- A report can be **viewed live** at any time — it is rebuilt fresh from the
  current data every time the page is opened.
- A report can also be **generated/frozen** into the `monthly_reports` table,
  so that it keeps showing the numbers as they were on the day it was saved,
  even if the underlying income/expense records are changed later.
- Reports can be deleted (this only removes the saved snapshot, never the
  underlying income/expense data).

### 2.8 AI Advisor (`routes/ai.py`, `services/ai_service.py`)
This is the most elaborate module in the project. It integrates with
**Google Gemini** through the `google-genai` Python SDK and implements eight
AI-related capabilities:

1. Personalised Budget Generation (`generate_budget_plan`)
2. AI Spending Analysis (`analyze_spending`)
3. Savings Recommendations (`savings_recommendations`)
4. Financial Health Evaluation (`evaluate_health`)
5. Overspending Detection (`detect_overspending`)
6. Cost Optimisation Suggestions (`cost_optimization`)
7. Emergency Fund Guidance (`emergency_fund_guidance`)
8. Personalised Financial Insights (`personalized_insights`)

Every one of these functions follows the same pattern: build a prompt out of
the user's **real** numbers from the database (`build_context`), send it to
Gemini, and if that call fails for *any* reason (no key, invalid key, no
internet, rate limit, empty reply, unexpected error), fall back to a
built-in, rule-based version of the same advice. The page always tells the
user honestly which mode produced the answer (`is_fallback`). Generated
insights are stored in the `AIInsight` table so they can be reviewed later
without calling Gemini again. The AI budget plan can optionally be **applied**
— the app parses lines like `Food: 4500` out of the AI's reply and only
accepts them if the category name matches one that already belongs to that
user, so a confused AI answer can never invent categories or affect another
account.

### 2.9 Dashboard and charts (`routes/dashboard.py`, `routes/api.py`,
`static/js/dashboard.js`)
- The dashboard page combines income, expenses, savings, health score,
  overspending, recent transactions, and the latest AI insight in one view.
- A small internal JSON API (`/api/summary`, `/api/expenses/by-category`,
  `/api/budget-progress`, `/api/trend`, `/api/recent`) feeds three Chart.js
  charts: a category doughnut chart, a budget performance bar chart, and an
  income/expenses/savings trend line chart over the last few months. All
  numbers displayed are computed on the server; JavaScript only draws what
  it is given.

## 3. Technology stack

| Purpose                | Library / Tool                         | Notes |
|--------------------------|----------------------------------------|-------|
| Web framework            | Flask ≥ 3.0                              | App-factory pattern (`create_app`) |
| ORM / database access    | Flask-SQLAlchemy ≥ 3.1, SQLAlchemy ≥ 2.0 | SQLite file database |
| Authentication           | Flask-Login ≥ 0.6                        | Session-based login |
| Password hashing         | Werkzeug ≥ 3.0                            | scrypt (dev/prod), reduced-cost pbkdf2 in tests only |
| Configuration            | python-dotenv ≥ 1.0                       | Loads `.env` |
| AI                       | google-genai ≥ 2.0                        | Google Gemini text generation |
| Frontend templates       | Jinja2 (bundled with Flask)                | `templates/` |
| Charts                   | Chart.js 4.4.1                             | Loaded from a CDN in `base.html` |
| Testing                  | pytest ≥ 8.0                               | 98 test functions across 5 files |

## 4. What this project intentionally does *not* include

To avoid overstating the project, the following are **not** present in the
code, and this documentation does not claim they exist:

- No user roles or an admin panel — every account has the same capabilities.
- No bank or payment-gateway integration; all data is entered manually.
- No production deployment configuration (no Dockerfile, no WSGI server
  config, no cloud hosting setup). `run_public.ps1` only wraps the local
  development server with an `ngrok` tunnel for temporary demos on Windows.
- No CSRF-protection library (such as Flask-WTF) is included; the project
  relies on the ownership checks described in
  `documentation/system_architecture.md` and on keeping destructive actions
  behind POST requests.
- No CI/CD pipeline or automated linting configuration was found in the
  project files.
