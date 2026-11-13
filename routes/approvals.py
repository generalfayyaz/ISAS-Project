from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app
from db import get_db
from security import current_user, get_visible_claim_or_404, login_required, roles_required
from services.workflow import can_decide, decide_claim

bp = Blueprint("approvals", __name__, url_prefix="/approvals")


@bp.route("")
@roles_required("Manager", "Admin")
def inbox():
    user = current_user()
    db = get_db()
    if user["role"] == "Manager":
        rows = db.execute(
            """SELECT c.*, u.full_name AS employee_name FROM claims c JOIN users u ON u.id=c.employee_id
               WHERE c.is_deleted=0 AND c.status='Submitted' AND c.department=? AND c.amount<=?
               ORDER BY c.submitted_at ASC""",
            (user["department"], current_app.config["APPROVAL_LIMIT"]),
        ).fetchall()
        heading = "Department approval inbox"
    else:
        rows = db.execute(
            """SELECT c.*, u.full_name AS employee_name FROM claims c JOIN users u ON u.id=c.employee_id
               WHERE c.is_deleted=0 AND c.status='Submitted' AND c.amount>?
               ORDER BY c.submitted_at ASC""",
            (current_app.config["APPROVAL_LIMIT"],),
        ).fetchall()
        heading = "Director approval inbox"
    return render_template("approvals/inbox.html", claims=rows, heading=heading)


@bp.route("/<int:claim_id>/decision", methods=["POST"])
@roles_required("Manager", "Admin")
def decision(claim_id):
    claim = get_visible_claim_or_404(claim_id)
    choice = request.form.get("decision")
    comment = request.form.get("comment", "")
    ok, message = decide_claim(claim, current_user(), choice, comment)
    if not ok:
        flash(message, "danger")
        return redirect(url_for("claims.detail", claim_id=claim_id))
    flash(message, "success")
    return redirect(url_for("approvals.inbox"))
