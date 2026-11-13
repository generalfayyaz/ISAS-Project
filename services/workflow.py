from datetime import date
from flask import abort, current_app
from db import get_db
from security import now_iso, log_action


def can_decide(claim, user):
    if claim["status"] != "Submitted":
        return False
    if claim["employee_id"] == user["id"]:
        return False
    if claim["amount"] > current_app.config["APPROVAL_LIMIT"]:
        return user["role"] == "Admin"
    return user["role"] == "Manager" and claim["department"] == user["department"]


def decide_claim(claim, user, decision, comment):
    if decision not in ("Approved", "Rejected"):
        abort(400)
    if not can_decide(claim, user):
        abort(403)
    comment = (comment or "").strip()
    if len(comment) < 10:
        return False, "Please enter an approval or rejection comment of at least 10 characters."
    db = get_db()
    now = now_iso()
    old = {"status": claim["status"], "approver_id": claim["approver_id"], "approval_comment": claim["approval_comment"]}
    db.execute(
        """UPDATE claims SET status = ?, approver_id = ?, approval_comment = ?,
           approved_at = ?, rejected_at = ?, updated_at = ? WHERE id = ?""",
        (decision, user["id"], comment, now if decision == "Approved" else None,
         now if decision == "Rejected" else None, now, claim["id"]),
    )
    log_action("APPROVE" if decision == "Approved" else "REJECT", claim["id"], old,
               {"status": decision, "approver_id": user["id"], "approval_comment": comment})
    db.commit()
    return True, f"Claim {claim['claim_no']} was {decision.lower()}."


def submit_claim(claim, user):
    if claim["employee_id"] != user["id"] or claim["status"] not in ("Draft", "Rejected"):
        abort(403)
    db = get_db()
    now = now_iso()
    old = {"status": claim["status"]}
    db.execute(
        """UPDATE claims SET status = 'Submitted', approver_id = NULL, approval_comment = NULL,
           submitted_at = ?, approved_at = NULL, rejected_at = NULL, updated_at = ? WHERE id = ?""",
        (now, now, claim["id"]),
    )
    log_action("SUBMIT", claim["id"], old, {"status": "Submitted"})
    db.commit()
