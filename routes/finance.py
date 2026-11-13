import re
from datetime import date
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from db import get_db
from security import current_user, log_action, now_iso, now_local, roles_required

bp = Blueprint("finance", __name__, url_prefix="/finance")
PAYMENT_REF_RE = re.compile(r"^[A-Za-z0-9-]{5,30}$")


@bp.route("/payments")
@roles_required("Finance")
def payments():
    db = get_db()
    pending = db.execute(
        """SELECT c.*, u.full_name AS employee_name, a.full_name AS approver_name FROM claims c
           JOIN users u ON u.id=c.employee_id LEFT JOIN users a ON a.id=c.approver_id
           WHERE c.is_deleted=0 AND c.status='Approved' ORDER BY c.approved_at"""
    ).fetchall()
    paid = db.execute(
        """SELECT c.*, u.full_name AS employee_name, a.full_name AS approver_name FROM claims c
           JOIN users u ON u.id=c.employee_id LEFT JOIN users a ON a.id=c.approver_id
           WHERE c.is_deleted=0 AND c.status='Paid' ORDER BY c.payment_date DESC LIMIT 15"""
    ).fetchall()
    return render_template("finance/payments.html", pending=pending, paid=paid, today=now_local().date().isoformat())


@bp.route("/payments/<int:claim_id>/pay", methods=["POST"])
@roles_required("Finance")
def pay(claim_id):
    db = get_db()
    claim = db.execute("SELECT * FROM claims WHERE id=? AND is_deleted=0", (claim_id,)).fetchone()
    if claim is None:
        abort(404)
    if claim["status"] != "Approved":
        abort(403)
    if claim["approver_id"] == current_user()["id"]:
        abort(403)
    payment_date = (request.form.get("payment_date") or "").strip()
    reference = (request.form.get("payment_reference") or "").strip()
    errors = []
    try:
        parsed_date = date.fromisoformat(payment_date)
        if parsed_date > now_local().date():
            errors.append("Payment date cannot be in the future.")
    except ValueError:
        errors.append("Enter a valid payment date.")
    if not PAYMENT_REF_RE.fullmatch(reference):
        errors.append("Payment reference must be 5–30 characters (letters, numbers, or hyphens).")
    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("finance.payments"))
    old = {"status": claim["status"], "payment_date": claim["payment_date"], "payment_reference": claim["payment_reference"]}
    now = now_iso()
    db.execute(
        "UPDATE claims SET status='Paid', payment_date=?, payment_reference=?, paid_at=?, updated_at=? WHERE id=?",
        (payment_date, reference, now, now, claim_id),
    )
    log_action("PAY", claim_id, old, {"status": "Paid", "payment_date": payment_date, "payment_reference": reference})
    db.commit()
    flash(f"Payment recorded for {claim['claim_no']}.", "success")
    return redirect(url_for("finance.payments"))
