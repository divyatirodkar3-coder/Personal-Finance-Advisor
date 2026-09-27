/*
 * static/js/dashboard.js - draws the three dashboard charts.
 *
 * WHAT IS HAPPENING HERE
 * ----------------------
 * The HTML page shows three empty <canvas> boxes. This file asks our
 * JSON API for the real numbers and draws them with Chart.js.
 *
 * All the maths happens on the server (Python + SQL). JavaScript only
 * displays what it is told, so the charts can never invent data.
 */

const MONTH = document.body.dataset.month;
const CURRENCY = document.body.dataset.currency || "";

/* Fetch JSON from our own API and return the parsed object. */
async function getJSON(path) {
    const url = path + (path.includes("?") ? "&" : "?") + "month=" + MONTH;
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) {
        throw new Error("Could not load " + path);
    }
    return await response.json();
}

/* Show/hide a message when a chart has nothing to draw. */
function setEmpty(id, isEmpty) {
    const note = document.getElementById(id);
    const canvas = document.getElementById(id.replace("Empty", "Chart"));
    if (note && canvas) {
        note.style.display = isEmpty ? "block" : "none";
        canvas.style.display = isEmpty ? "none" : "block";
    }
}

const money = (value) => CURRENCY + " " + Number(value).toFixed(2);

/* ---------- 1. CATEGORY-WISE EXPENSE ANALYTICS (doughnut) ---------- */
async function drawCategoryChart() {
    const data = await getJSON("/api/expenses/by-category");
    const empty = !data.labels.length;
    setEmpty("categoryEmpty", empty);
    if (empty) return;

    new Chart(document.getElementById("categoryChart"), {
        type: "doughnut",
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: data.colors,
                borderWidth: 2,
                borderColor: "#ffffff",
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "right" },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                            return ctx.label + ": " + money(ctx.parsed) + " (" + pct + "%)";
                        },
                    },
                },
            },
        },
    });
}

/* ---------- 2. BUDGET PERFORMANCE (bar) ---------- */
async function drawBudgetChart() {
    const data = await getJSON("/api/budget-progress");
    const empty = !data.labels.length;
    setEmpty("budgetEmpty", empty);
    if (empty) return;

    /* Colour each bar red where the budget was exceeded. */
    const colours = data.status.map((status) => {
        if (status === "over") return "#dc2626";
        if (status === "warn") return "#d97706";
        return "#2563eb";
    });

    new Chart(document.getElementById("budgetChart"), {
        type: "bar",
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: "Budget",
                    data: data.planned,
                    backgroundColor: "rgba(37,99,235,.18)",
                    borderColor: "#2563eb",
                    borderWidth: 1,
                },
                {
                    label: "Spent",
                    data: data.spent,
                    backgroundColor: colours,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: { y: { beginAtZero: true } },
        },
    });
}

/* ---------- 3. SIX-MONTH TREND (line) ---------- */
async function drawTrendChart() {
    const data = await getJSON("/api/trend?months=6");
    new Chart(document.getElementById("trendChart"), {
        type: "line",
        data: {
            labels: data.months,
            datasets: [
                {
                    label: "Income",
                    data: data.income,
                    borderColor: "#16a34a",
                    backgroundColor: "rgba(22,163,74,.12)",
                    tension: .3,
                    fill: true,
                },
                {
                    label: "Expenses",
                    data: data.expenses,
                    borderColor: "#dc2626",
                    backgroundColor: "rgba(220,38,38,.12)",
                    tension: .3,
                    fill: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: { y: { beginAtZero: true } },
        },
    });
}

/* ---------- start them all, one failure must not break the page ---------- */
async function start() {
    const jobs = [
        ["category", drawCategoryChart],
        ["budget", drawBudgetChart],
        ["trend", drawTrendChart],
    ];
    for (const [name, job] of jobs) {
        try {
            await job();
        } catch (err) {
            console.error("Chart failed: " + name, err);
        }
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
} else {
    start();
}
