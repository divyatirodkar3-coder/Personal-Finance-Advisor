# User Guide

This guide walks through the application screen by screen, in the order a
new user would naturally use them. It assumes the app is already running
locally — see [`installation_guide.md`](installation_guide.md) if you have
not set it up yet.

## 1. Creating an account

Open the app in your browser. Since you are not logged in, you will be sent
to the **Log In** page (`/auth/login`). Click **Register** to go to
`/auth/register` and fill in:

- **Username** — 3–80 characters, letters/numbers/dot/underscore only.
- **Email** — must look like a real email address.
- **Password** and **Confirm password** — at least 6 characters, and both
  must match.
- **Full name** *(optional)* — shown in greetings around the app.
- **Savings goal** *(optional)* — a starting monthly savings target; you can
  change this later from your profile or the Savings page.

If anything is invalid or already taken (username/email), the form reloads
with a clear error message and keeps what you typed so you don't have to
retype everything.

When registration succeeds you are logged in automatically, and the app
quietly creates ten starter expense categories for you (Rent, Food,
Transport, Entertainment, Groceries, Utilities, Education, Healthcare,
Savings, Other) so you have something to pick from right away.

## 2. Logging in and out

- **Log in** (`/auth/login`) accepts either your username or your email
  address, plus your password, and an optional "remember me" checkbox that
  keeps you logged in for longer.
- **Log out**: click **Log Out** in the top navigation bar. This is a real
  button (not just a link), because logging out is treated as a deliberate
  action, not something that should happen by accident.

## 3. The Dashboard (`/dashboard`)

This is the home page once you are logged in, and it brings every module
together in one view for the selected month:

- Headline numbers: total income, total expenses, and calculated savings.
- Your **financial health score** out of 100, with a short label
  (Excellent / Good / Needs work / At risk).
- A list of any categories you have overspent in.
- Three charts, drawn from your real data:
  - A **doughnut chart** of spending by category.
  - A **bar chart** comparing planned budget vs. actual spending per
    category.
  - A **trend line** showing income, expenses, and savings over the last
    several months.
- Your most recent income and expense entries.
- The most recent AI insight you generated, if any.
- Arrows to move to the previous or next month.

## 4. Income (`/income`)

- **View**: see every income entry for the selected month, with the total
  and a breakdown by income type (salary, freelance, allowance, business,
  investment, other).
- **Add** (`/income/add`): enter a source (e.g. "Monthly Salary"), pick an
  income type, enter an amount and a date, and optionally add notes.
- **Delete**: remove an entry directly from the list. Only entries that
  belong to your own account can ever be deleted.

## 5. Expenses (`/expenses`)

- **View**: see every expense for the selected month, the total, a
  category-wise breakdown, and a week-by-week spending split.
- **Add** (`/expenses/add`): enter a title, amount, date, payment method
  (cash, UPI, card, bank, other), an optional category, and optional notes.
- **Edit**: change any expense you previously added.
- **Delete**: remove an expense.
- **Categories** (`/expenses/categories`): see all your categories with
  total spending in each, add a new category (with a name and a colour used
  by the dashboard chart), and delete a category — the app will refuse to
  delete a category that still has expenses attached, and tells you exactly
  how many, so your history is never deleted by accident.

## 6. Budgets (`/budgets`)

- **View**: for the selected month, see every budgeted category with planned
  amount, amount spent, amount remaining, percentage used, and a status
  colour (on track / warning near the limit / over budget).
- **Add** (`/budgets/add`): choose either "category" budget (pick one of
  your categories and a limit) or "overall" budget (a single limit for the
  whole month, not tied to any category).
- **Suggestions**: the page also shows budget suggestions calculated from
  what you actually spent, aiming to keep total spending at about 70% of
  your income while reserving 20% for savings. Click **Apply** on a
  suggestion to save it as a real budget instantly.
- **Delete**: remove a budget you no longer want to track.

## 7. Savings (`/savings`)

- Your savings figure is **never typed in** — it is always calculated as
  income minus expenses for the selected month.
- Set a **target** for the month (or update your default monthly goal from
  your profile), and the page shows how close you are, along with a status
  that accounts for how much of the month has actually passed.
- A history table shows past months, and an all-time summary shows how many
  months you tracked and in how many of them you hit your goal.
- A **Refresh** action recalculates the savings record for every month that
  has any data, useful after you have gone back and added or edited old
  entries.

## 8. Analysis (`/analysis`)

A focused view of the same spending-analysis engine used on the dashboard:
the health score with its point breakdown, categories that are over budget
or close to their limit, your top spending categories, your average daily
spend, and a comparison against last month, plus plain-English observations
generated directly from these numbers.

## 9. Reports (`/reports`)

- The **Reports** list (`/reports`) shows which months already have a saved
  report, and which months have data available to generate one.
- Open **a month** (`/reports/<month>`) to view a full report built live
  from your current data: income, expenses, savings, savings rate, budget
  totals, category breakdown, overspending, the health score, and weekly
  spending.
- **Generate**: freeze the report for that month into a permanent saved copy,
  so it keeps showing the same numbers even if you later edit that month's
  transactions.
- **Delete**: remove a saved report snapshot (this never deletes your actual
  income/expense records — only the frozen copy).

## 10. AI Advisor (`/ai/insights`)

- The page shows whether Gemini is currently configured
  (`GEMINI_API_KEY` set in your `.env` file) and which model will be used.
- Choose from seven insight types — Spending Analysis, Overspending
  Detection, Savings Recommendations, Financial Health Evaluation, Cost
  Optimisation, Emergency Fund Guidance, and Personalised Insights — and
  click **Generate** to get advice based on your real numbers for the
  selected month.
- You can also generate a full **AI Budget Plan** and choose to have it
  automatically saved as real budgets for categories the AI recognises from
  your account.
- If Gemini is not configured, or the request fails for any reason, the app
  automatically shows a rule-based version of the same advice instead, and
  says so clearly with a warning message — it never leaves the page empty
  or broken.
- Every insight you generate is kept in a history list so you can look back
  at previous advice without generating it again.

## 11. Profile (`/auth/profile`)

- Update your full name, email address, currency code, and default monthly
  savings goal.
- Change your password (you must correctly enter your current password
  first).
- See simple counts of how many income records, expenses, and categories
  are on your account.

## 12. Understanding the month picker

Most pages (Dashboard, Income, Expenses, Budgets, Savings, Analysis, AI
Advisor) work on a **selected month**, shown and changed with previous/next
arrows or a `?month=YYYY-MM` value in the address bar. If you type an
invalid month, the app shows a clear error message instead of crashing, and
falls back to the current month.
