from datetime import date
from flask import Blueprint, abort, render_template, request
from db import get_db
from security import current_user, get_visible_claim_or_404, login_required, now_local, roles_required
from services.claim_queries import filtered_claims

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _scope_sql(user):
    if user["role"] == "Employee":
        return "c.employee_id=?", [user["id"]]
    if user["role"] == "Manager":
        return "c.department=?", [user["department"]]
    if user["role"] == "Finance":
        return "c.status IN ('Approved','Paid')", []
    return "1=1", []


@bp.route("/monthly")
@login_required
def monthly():
    month = (request.args.get("month") or now_local().strftime("%Y-%m")).strip()
    try:
        date.fromisoformat(month + "-01")
    except ValueError:
        month = now_local().strftime("%Y-%m")
    user = current_user()
    scope, params = _scope_sql(user)
    db = get_db()
    rows = db.execute(
        f"""SELECT c.department, c.category, COUNT(*) AS claim_count, SUM(c.amount) AS total_amount
             FROM claims c WHERE c.is_deleted=0 AND substr(c.expense_date,1,7)=? AND {scope}
             GROUP BY c.department,c.category ORDER BY c.department,c.category""",
        [month] + params,
    ).fetchall()
    totals = db.execute(
        f"""SELECT COUNT(*) AS claim_count, COALESCE(SUM(c.amount),0) AS total_amount
             FROM claims c WHERE c.is_deleted=0 AND substr(c.expense_date,1,7)=? AND {scope}""",
        [month] + params,
    ).fetchone()
    departments = db.execute(
        f"""SELECT c.department, COUNT(*) AS claim_count, SUM(c.amount) AS total_amount
             FROM claims c WHERE c.is_deleted=0 AND substr(c.expense_date,1,7)=? AND {scope}
             GROUP BY c.department ORDER BY c.department""",
        [month] + params,
    ).fetchall()
    return render_template("reports/monthly.html", month=month, rows=rows, totals=totals, departments=departments, now_text=now_local().strftime("%Y-%m-%d %H:%M"))


@bp.route("/voucher/<int:claim_id>")
@login_required
def voucher(claim_id):
    claim = get_visible_claim_or_404(claim_id)
    return render_template("reports/voucher.html", claim=claim)


@bp.route("/exceptions")
@roles_required("Admin")
def exceptions():
    db = get_db()
    high_value = db.execute(
        """SELECT c.*, e.full_name AS employee_name, a.full_name AS approver_name, a.role AS approver_role
           FROM claims c JOIN users e ON e.id=c.employee_id LEFT JOIN users a ON a.id=c.approver_id
           WHERE c.is_deleted=0 AND c.amount>5000000 ORDER BY c.amount DESC"""
    ).fetchall()
    duplicates = db.execute(
        """SELECT e.full_name AS employee_name, c.amount, c.expense_date, c.receipt_number,
                  COUNT(*) AS duplicate_count, GROUP_CONCAT(c.claim_no, ', ') AS claim_numbers
           FROM claims c JOIN users e ON e.id=c.employee_id
           WHERE c.is_deleted=0 GROUP BY c.employee_id,c.amount,c.expense_date,c.receipt_number
           HAVING COUNT(*)>1 ORDER BY duplicate_count DESC"""
    ).fetchall()
    self_approved = db.execute(
        """SELECT c.*, e.full_name AS employee_name FROM claims c JOIN users e ON e.id=c.employee_id
           WHERE c.is_deleted=0 AND c.approver_id=c.employee_id"""
    ).fetchall()
    late_payments = db.execute(
        """SELECT c.*, e.full_name AS employee_name FROM claims c JOIN users e ON e.id=c.employee_id
           WHERE c.is_deleted=0 AND c.status='Paid' AND julianday(c.payment_date)-julianday(c.expense_date)>30
           ORDER BY julianday(c.payment_date)-julianday(c.expense_date) DESC"""
    ).fetchall()
    route_exceptions = [r for r in high_value if r["status"] in ("Approved", "Paid") and r["approver_role"] != "Admin"]
    return render_template("reports/exceptions.html", high_value=high_value, duplicates=duplicates,
                           self_approved=self_approved, late_payments=late_payments,
                           route_exceptions=route_exceptions)
