"""
services/ai_service.py - Google Gemini AI integration.

THIS MODULE COVERS ALL EIGHT AI REQUIREMENTS
--------------------------------------------
    1. Personalized Budget Generation      generate_budget_plan()
    2. AI Spending Analysis                analyze_spending()
    3. Savings Recommendations            savings_recommendations()
    4. Financial Health Evaluation         evaluate_health()
    5. Overspending Detection              detect_overspending()
    6. Cost Optimization Suggestions      cost_optimization()
    7. Emergency Fund Guidance             emergency_fund_guidance()
    8. Personalized Financial Insights    personalized_insights()

THE MOST IMPORTANT RULE IN THIS FILE
------------------------------------
Gemini is NEVER allowed to break the app. Every function follows the
same shape:

    try to call Gemini  ->  use the answer
    if anything fails   ->  use the built-in rule-based answer

That covers a missing key, a bad key, no internet, rate limits, an
empty reply, or an unexpected error. The user always gets useful
advice, and the page shows an honest badge saying which mode ran.
"""

import re

from flask import current_app

from extensions import db
from models import AIInsight, User, ExpenseCategory
from services import finance_service as fin
from services import analysis_service as asvc
from services import budget_service as bsvc
from services import savings_service as ssvc

# How long we are willing to wait for Gemini before giving up.
# These are applied to the CLIENT (HttpOptions), not to the individual
# request. Passing a "timeout" inside the per-request config is invalid
# in google-genai 2.x and raises a ValidationError.
GEMINI_TIMEOUT_MS = 30000

# The SDK retries a failed request 5 times by default, with growing
# delays. When a free-tier quota is exhausted that means a user could
# wait several minutes after one button click, which looks like a hang.
# Two quick attempts keep the app responsive and fall back fast.
GEMINI_RETRY_ATTEMPTS = 2
GEMINI_RETRY_INITIAL_DELAY = 1.0
GEMINI_RETRY_MAX_DELAY = 3.0

# A line in the AI reply that looks like "Food: 4500"
BUDGET_LINE = re.compile(
    r"^\s*[-*]?\s*([A-Za-z][A-Za-z &]{1,28}?)\s*[:=]\s*"
    r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*$",
    re.MULTILINE,
)


def api_key():
    """Read the key from Flask config, which loaded it from .env."""
    key = (current_app.config.get("GEMINI_API_KEY") or "").strip()
    # Treat the placeholder value as "not configured" so we never try
    # to call the API with a fake key.
    if not key or key.lower().startswith("your_"):
        return None
    if "replace" in key.lower() or key.lower() == "here":
        return None
    return key


def is_configured():
    """True when a real-looking API key is available."""
    return api_key() is not None


def model_name():
    return current_app.config.get("GEMINI_MODEL", "gemini-flash-latest")


def call_gemini(prompt, purpose):
    """Send a prompt to Gemini.

    Returns (text, ok). When ok is False the caller MUST use its
    rule-based fallback instead. This function never raises.
    """
    key = api_key()
    if not key:
        return ("AI is not switched on yet. Add a real GEMINI_API_KEY to "
                "the .env file to enable this feature."), False

    try:
        # Imported here rather than at the top of the file, so the
        # whole app still starts if the package is ever missing.
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=GEMINI_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(
                    attempts=GEMINI_RETRY_ATTEMPTS,
                    initial_delay=GEMINI_RETRY_INITIAL_DELAY,
                    max_delay=GEMINI_RETRY_MAX_DELAY,
                ),
            ),
        )

        # NOTE: no per-request config is passed here. In google-genai 2.x
        # "timeout" is not a valid GenerateContentConfig field, so sending
        # one raises a ValidationError. Timing belongs on the Client.
        response = client.models.generate_content(
            model=model_name(),
            contents=prompt,
        )
        text = (getattr(response, "text", None) or "").strip()

        if not text:
            return "Gemini returned an empty response.", False

        return text, True

    except Exception as exc:
        # Deliberately broad. A network error, a 429, an invalid key
        # and a library problem must all degrade the same way.
        return (f"Gemini could not be reached ({type(exc).__name__}). "
                f"Showing built-in analysis instead."), False


# ------------------------------------------------------------------
# BUILDING THE PROMPT FROM REAL DATABASE NUMBERS
# ------------------------------------------------------------------
def build_context(user_id, month):
    """Gather the real numbers and format them for the prompt.

    This is the important idea: we never ask Gemini to simply advise
    the user. We give it their ACTUAL figures from the database and
    ask it to interpret them, so the advice is grounded in real data
    instead of being invented.
    """
    user = db.session.get(User, user_id)
    income = fin.total_income(user_id, month)
    expenses = fin.total_expenses(user_id, month)
    saved = fin.total_savings(user_id, month)
    breakdown = fin.category_breakdown(user_id, month)
    budgets = bsvc.category_progress(user_id, month)
    health = asvc.health_score(user_id, month)

    budget_lines = []
    for row in budgets:
        budget_lines.append(
            "  - {0}: budget {1:.2f}, spent {2:.2f} ({3:.1f}%, {4})".format(
                row["name"], row["planned"], row["spent"],
                row["percent"], row["status"]))
    if not budget_lines:
        budget_lines.append("  (no budgets set yet)")

    category_lines = []
    for name, value in sorted(breakdown.items(), key=lambda i: i[1],
                              reverse=True):
        category_lines.append("  - {0}: {1:.2f}".format(name, value))
    if not category_lines:
        category_lines.append("  (no expenses recorded)")

    lines = [
        "FINANCIAL DATA FOR {0} - MONTH {1}".format(
            user.full_name or user.username, month),
        "",
        "TOTAL INCOME   : {0:.2f}".format(income),
        "TOTAL EXPENSES : {0:.2f}".format(expenses),
        "SAVINGS        : {0:.2f}".format(saved),
        "MONTHLY SAVING GOAL (from profile) : {0:.2f}".format(
            ssvc.profile_goal(user_id)),
        "AVERAGE DAILY SPEND : {0:.2f}".format(
            asvc.avg_daily_spend(user_id, month)),
        "FINANCIAL HEALTH SCORE : {0}/100 ({1})".format(
            health["score"], health["label"]),
        "",
        "SPENDING BY CATEGORY:",
    ]
    lines.extend(category_lines)
    lines.append("")
    lines.append("BUDGETS:")
    lines.extend(budget_lines)
    return "\n".join(lines)


def _wrap(task, context, extra_rules=""):
    """Standard prompt wrapper. Keeps every AI call consistent."""
    parts = [
        "You are a careful personal finance advisor helping a real user.",
        "",
        task,
        "",
        "Here are their ACTUAL numbers for the month. Base every "
        "statement on these figures - never invent a number that is not "
        "shown here or that you cannot calculate from them.",
        "",
        context,
    ]
    if extra_rules:
        parts.append(extra_rules)
    parts.extend([
        "",
        "Rules:",
        "- Be specific and use the actual amounts shown above.",
        "- Keep it under 250 words, with short headings or bullets.",
        "- Plain text only. Do not use markdown tables.",
        "- Speak directly to the user in a friendly but honest tone.",
    ])
    return "\n".join(parts)


# ------------------------------------------------------------------
# SAVING AND READING PAST INSIGHTS
# ------------------------------------------------------------------
def save_insight(user_id, insight_type, title, content, month, is_fallback):
    """Store an insight in the ai_insights table so it can be shown again."""
    row = AIInsight(user_id=user_id, insight_type=insight_type,
                    title=title, content=content,
                    is_fallback=is_fallback, month=month)
    db.session.add(row)
    db.session.commit()
    return row


def past_insights(user_id, limit=20):
    """Previously generated advice, newest first."""
    return (AIInsight.query
            .filter_by(user_id=user_id)
            .order_by(AIInsight.created_at.desc())
            .limit(limit).all())


def _run(user_id, month, insight_type, title, task, fallback_builder,
         extra_rules=""):
    """Shared flow: build the prompt, call Gemini, fall back if needed.

    Every advice-only AI feature goes through here, which guarantees
    the fallback behaviour is identical everywhere.
    """
    context = build_context(user_id, month)
    prompt = _wrap(task, context, extra_rules)

    try:
        text, ok = call_gemini(prompt, title.lower())
    except Exception:
        # call_gemini already swallows errors, but if anything
        # unexpected still happens the app must not crash.
        text, ok = "AI service error.", False

    if ok:
        fallback = False
    else:
        text = fallback_builder(user_id, month)
        fallback = True

    save_insight(user_id, insight_type, title, text, month, fallback)
    return {"text": text, "is_fallback": fallback, "title": title}


# ------------------------------------------------------------------
# THE EIGHT AI FEATURES
# ------------------------------------------------------------------
# (2) AI SPENDING ANALYSIS -----------------------------------------
def analyze_spending(user_id, month):
    task = ("Analyse where this person's money went this month. Point out "
            "the largest category, anything that looks unusual, and the "
            "single most useful change they could make.")

    def fallback(uid, mon):
        expenses = fin.total_expenses(uid, mon)
        if expenses <= 0:
            return "No expenses recorded for this month yet."
        out = ["SPENDING ANALYSIS - " + mon, "",
               "Total spending: {0:.2f}".format(expenses), "",
               "Largest categories:"]
        for name, value in asvc.top_categories(uid, mon, limit=3):
            share = (value / expenses) * 100
            out.append("  - {0}: {1:.2f} ({2:.0f}%)".format(
                name, value, share))
        out.append("")
        out.append("Average spend per day: {0:.2f}".format(
            asvc.avg_daily_spend(uid, mon)))
        out.append("The biggest category is the best place to start, "
                   "because a small cut there frees the most money.")
        return "\n".join(out)

    return _run(user_id, month, "analysis", "Spending Analysis", task, fallback)


# (5) OVERSPENDING DETECTION ---------------------------------------
def detect_overspending(user_id, month):
    task = ("Identify every budget this person has gone over. For each one "
            "state the category, how much over they are, and the single "
            "most realistic action to get back within budget.")

    def fallback(uid, mon):
        over = asvc.overspending(uid, mon)
        if not over:
            return ("No budget was exceeded in {0}. Keep it up - every "
                    "category stayed within its limit.".format(mon))
        out = ["OVERSPENDING - " + mon, ""]
        for row in over:
            out.append("  - {0}: over by {1:.2f} (spent {2:.2f} of "
                       "{3:.2f}, {4:.0f}% of budget)".format(
                           row["name"], -row["remaining"], row["spent"],
                           row["planned"], row["percent"]))
        whole = asvc.overall_overspend(uid, mon)
        if whole:
            out.append("")
            out.append("Overall spending is {0:.2f} over the whole-month "
                       "budget.".format(whole))
        return "\n".join(out)

    return _run(user_id, month, "overspending", "Overspending Detection",
                task, fallback)


# (3) SAVINGS RECOMMENDATIONS --------------------------------------
def savings_recommendations(user_id, month):
    task = ("Tell this person how to improve their savings. Compare what "
            "they saved against their goal, and give concrete ways to save "
            "more next month based on their actual spending.")

    def fallback(uid, mon):
        income = fin.total_income(uid, mon)
        if income <= 0:
            return "Add your income for this month to get savings advice."
        saved = fin.total_savings(uid, mon)
        goal = ssvc.profile_goal(uid)
        rate = (saved / income) * 100
        out = ["SAVINGS RECOMMENDATIONS", "",
               "  Income    : {0:.2f}".format(income),
               "  Saved     : {0:.2f} ({1:.0f}%)".format(saved, rate),
               "  Your goal : {0:.2f}".format(goal), ""]
        if rate >= 20:
            out.append("You already save 20% or more. Consider putting the "
                       "surplus into an emergency fund.")
        else:
            target = income * 0.20
            out.append("Aiming for 20% would mean saving {0:.2f} - that is "
                       "{1:.2f} more than you saved.".format(
                           target, max(target - saved, 0)))
        top = asvc.top_categories(uid, mon, limit=1)
        if top:
            out.append("Cutting 10% off {0} ({1:.2f}) would free up about "
                       "{2:.2f} a month.".format(
                           top[0][0], top[0][1], round(top[0][1] * 0.10, 2)))
        return "\n".join(out)

    return _run(user_id, month, "savings", "Savings Recommendations",
                task, fallback)


# (4) FINANCIAL HEALTH EVALUATION -----------------------------------
def evaluate_health(user_id, month):
    task = ("Explain this person's financial health this month. Say whether "
            "it is strong or weak and why, using the score and the figures "
            "given.")

    def fallback(uid, mon):
        health = asvc.health_score(uid, mon)
        out = ["FINANCIAL HEALTH - {0}/100 ({1})".format(
            health["score"], health["label"]), ""]
        for reason in health["reasons"]:
            out.append("  {0}: {1}/{2}".format(
                reason["label"], reason["points"], reason["max"]))
            out.append("      " + reason["note"])
        weakest = min(health["reasons"],
                      key=lambda r: r["points"] / r["max"])
        out.append("")
        out.append("Biggest opportunity: " + weakest["label"].lower() + ".")
        return "\n".join(out)

    return _run(user_id, month, "health", "Financial Health Evaluation",
                task, fallback)


# (6) COST OPTIMIZATION SUGGESTIONS ---------------------------------
COST_TIPS = {
    "Food": "Plan meals for the week and shop from a list.",
    "Groceries": "Compare prices on your top five items and skip one "
                 "impulse buy per trip.",
    "Transport": "Check whether a monthly pass beats daily tickets.",
    "Entertainment": "Set a fixed monthly cap here - easiest to trim.",
    "Utilities": "Check for a cheaper tariff or a different provider.",
    "Healthcare": "Ask about generic medicines where suitable.",
    "Education": "Look for free or shared online resources.",
}


def cost_optimization(user_id, month):
    task = ("Suggest practical ways this person can reduce costs, based on "
            "the categories they actually spend on. Focus on categories "
            "where a small change frees real money.")

    def fallback(uid, mon):
        if fin.total_expenses(uid, mon) <= 0:
            return "No expenses recorded yet, so there is nothing to cut."
        out = ["COST OPTIMIZATION SUGGESTIONS", ""]
        total = 0.0
        for name, value in asvc.top_categories(uid, mon, limit=6):
            tip = COST_TIPS.get(name)
            if not tip:
                continue
            cut = round(value * 0.15, 2)
            total += cut
            out.append("  - {0} ({1:.2f} this month)".format(name, value))
            out.append("      {0} 15% saving is about {1:.2f}.".format(
                tip, cut))
        if total:
            out.append("")
            out.append("Together these could save roughly {0:.2f} a "
                       "month.".format(total))
        else:
            out.append("  No common categories found yet. Keep recording "
                       "expenses to get specific tips.")
        return "\n".join(out)

    return _run(user_id, month, "cost_optimization",
                "Cost Optimization Suggestions", task, fallback)


# (7) EMERGENCY FUND GUIDANCE --------------------------------------
def emergency_fund_guidance(user_id, month):
    task = ("Explain emergency fund basics and calculate a sensible target "
            "for this person based on their own income and expenses.")

    def fallback(uid, mon):
        income = fin.total_income(uid, mon)
        expenses = fin.total_expenses(uid, mon)
        saved = max(fin.total_savings(uid, mon), 0)
        if income <= 0:
            return ("EMERGENCY FUND\n\nAdd your income first so a target "
                    "can be calculated.")
        small = round(expenses * 3, 2)
        strong = round(expenses * 6, 2)
        out = ["EMERGENCY FUND", "",
               "  Monthly expenses : {0:.2f}".format(expenses),
               "  Minimum fund    : {0:.2f} (3 months)".format(small),
               "  Strong fund     : {0:.2f} (6 months)".format(strong),
               ""]
        if saved <= 0:
            out.append("You have not saved anything yet, so start with any "
                       "amount you can manage consistently, even small.")
        elif saved >= strong:
            out.append("You have already built a strong emergency fund. Keep "
                       "it somewhere separate from daily spending.")
        else:
            out.append("You have {0:.2f} saved. Reaching the minimum needs "
                       "{1:.2f} more.".format(saved, max(small - saved, 0)))
        out.append("")
        out.append("Keep the fund in an account you can reach quickly, and "
                   "do not spend it on planned purchases.")
        return "\n".join(out)

    return _run(user_id, month, "emergency_fund", "Emergency Fund Guidance",
                task, fallback)


# (8) PERSONALIZED FINANCIAL INSIGHTS -------------------------------
def personalized_insights(user_id, month):
    task = ("Give this person three or four personalised observations about "
            "their month: what went well, what needs attention, and the "
            "single best thing to change next month.")

    def fallback(uid, mon):
        return "\n".join(asvc.insights(uid, mon))

    return _run(user_id, month, "insights", "Personalized Financial Insights",
                task, fallback)


# (1) PERSONALIZED BUDGET GENERATION --------------------------------
# This one also WRITES to the database, so it is handled separately.
BUDGET_FORMAT_RULES = "\n".join([
    "",
    "IMPORTANT OUTPUT FORMAT",
    "After your explanation, end with a short section where every line",
    "looks exactly like this, using the exact category names above:",
    "",
    "  Food: 4500",
    "  Rent: 12000",
    "  Transport: 1500",
    "",
    "Rules for that section:",
    "- Use ONLY category names that appear in the spending list.",
    "- One category per line, in the form  CategoryName: amount",
    "- The amount must be a plain number with no symbols or commas.",
    "- Do not repeat a category.",
    "- Leave out any category you cannot give a sensible amount for.",
])


def apply_plan(user_id, month, text):
    """Read lines like "Food: 4500" from the reply and save real budgets.

    This is deliberately strict. A line is only used if the name matches
    one of THIS user's own categories, so a confused or imaginative AI
    reply can never create nonsense rows in the database.
    """
    categories = {c.name.strip().lower(): c
                  for c in ExpenseCategory.query.filter_by(
                      user_id=user_id).all()}

    applied = 0
    for match in BUDGET_LINE.finditer(text):
        name = match.group(1).strip().lower()
        category = categories.get(name)
        if category is None:
            continue
        try:
            amount = float(match.group(2).replace(",", ""))
        except ValueError:
            continue
        if amount <= 0:
            continue
        bsvc.set_budget(user_id, month, round(amount, 2),
                        category_id=category.id, source="ai")
        applied += 1
    return applied


def _budget_fallback(user_id, month):
    """Rule-based budget plan, used when Gemini is unavailable."""
    income = fin.total_income(user_id, month)
    if income <= 0:
        return ("AI is not available and there is no income recorded for "
                "this month, so no budget can be suggested yet.")

    out = ["SUGGESTED BUDGET PLAN (built-in analysis)", "",
           "Based on {0:.2f} income: spend about 70% ({1:.2f}) and save "
           "about 20% ({2:.2f}).".format(
               income, income * 0.70, income * 0.20), ""]
    for item in bsvc.suggest_allocation(user_id, month):
        out.append("  {0}: {1:.2f}".format(item["name"], item["suggested"]))
        out.append("      " + item["reason"])
    out.append("")
    out.append("Add a real GEMINI_API_KEY to .env to get a written plan "
               "with personal comments from Gemini.")
    return "\n".join(out)


def generate_budget_plan(user_id, month, apply=False):
    """Ask Gemini for a budget plan, optionally saving it to the database.

    Returns a dict with the advice text, whether Gemini actually ran,
    and how many budgets were applied.
    """
    task = ("Create a realistic monthly budget plan for this person. "
            "Recommend a limit for each category, aiming for total "
            "spending of about 70% of their income so the rest can be "
            "saved.")

    context = build_context(user_id, month)
    prompt = _wrap(task, context, BUDGET_FORMAT_RULES)

    try:
        text, ok = call_gemini(prompt, "budget generation")
    except Exception:
        text, ok = "AI service error.", False

    applied = 0
    if apply and ok:
        applied = apply_plan(user_id, month, text)
        if applied == 0:
            text += ("\n\n(No categories could be read from that plan, so "
                     "nothing was saved. Please set budgets manually.)")

    if ok:
        save_insight(user_id, "budget", "AI Budget Plan", text, month, False)
    else:
        text = _budget_fallback(user_id, month)
        save_insight(user_id, "budget", "AI Budget Plan", text, month, True)

    return {"text": text, "is_fallback": not ok, "applied": applied}


AI_FEATURES = [
    ("analysis", "Spending Analysis", "Where did my money go?"),
    ("overspending", "Overspending Detection", "What did I exceed?"),
    ("savings", "Savings Recommendations", "How do I save more?"),
    ("health", "Financial Health Evaluation", "How healthy are my finances?"),
    ("cost_optimization", "Cost Optimization", "Where can I cut costs?"),
    ("emergency_fund", "Emergency Fund Guidance", "How much should I keep aside?"),
    ("insights", "Personalized Insights", "Give me a summary."),
]


def run_feature(user_id, month, key):
    """Route a feature key from the UI to the right function."""
    table = {
        "analysis": analyze_spending,
        "overspending": detect_overspending,
        "savings": savings_recommendations,
        "health": evaluate_health,
        "cost_optimization": cost_optimization,
        "emergency_fund": emergency_fund_guidance,
        "insights": personalized_insights,
    }
    func = table.get(key)
    if func is None:
        return None
    return func(user_id, month)
