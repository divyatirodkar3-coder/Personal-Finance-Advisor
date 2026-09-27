"""
routes/reports.py - Monthly Financial Reports.

A report can be VIEWED at any time (built live from the database) and
GENERATED to freeze a permanent copy in the monthly_reports table.
"""

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from services import finance_service as fin
from services import report_service as rsvc
from services.validators import parse_month

report_bp = Blueprint("reports", __name__, url_prefix="/reports")


@report_bp.route("")
@login_required
def index():
    """Report history: which months already have a saved report."""
    saved = rsvc.saved_reports(current_user.id)
    available = rsvc.months_with_data(current_user.id)

    return render_template(
        "reports/list.html",
        saved=saved,
        available=available,
        has_data=bool(available),
    )


@report_bp.route("/<month>")
@login_required
def monthly(month):
    """A full monthly report. Builds it fresh every time you open it."""
    month, error = parse_month(month, "Month")
    if error:
        flash(error, "danger")
        return redirect(url_for("reports.index"))

    report = rsvc.build_report(current_user.id, month)

    # The stored copy, if one has been generated for this month.
    stored = None
    for row in rsvc.saved_reports(current_user.id):
        if row.month == month:
            stored = row
            break

    return render_template(
        "reports/monthly.html",
        r=report,
        stored=stored,
        prev_month=fin.previous_month(month),
        next_month=fin.next_month(month),
    )


@report_bp.post("/<month>/generate")
@login_required
def generate(month):
    """Freeze the report into the monthly_reports table."""
    month, error = parse_month(month, "Month")
    if error:
        flash(error, "danger")
        return redirect(url_for("reports.index"))

    rsvc.save_report(current_user.id, month)
    flash("Report for {0} saved.".format(month), "success")
    return redirect(url_for("reports.monthly", month=month))


@report_bp.post("/<month>/delete")
@login_required
def delete(month):
    month, error = parse_month(month, "Month")
    if error:
        flash(error, "danger")
        return redirect(url_for("reports.index"))

    if rsvc.delete_report(current_user.id, month):
        flash("Saved report for {0} deleted. The data itself is untouched."
              .format(month), "success")
    else:
        flash("No saved report found for {0}.".format(month), "danger")
    return redirect(url_for("reports.index"))


@report_bp.post("/generate-all")
@login_required
def generate_all():
    """Create a report for every month that has data."""
    months = rsvc.sync_all(current_user.id)
    flash("Reports generated for {0} month(s).".format(len(months)), "success")
    return redirect(url_for("reports.index"))
