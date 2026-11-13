from datetime import timedelta
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from db import get_db
from security import current_user, get_visible_claim_or_404, log_action, login_required, now_iso, now_local, roles_required
from services.claim_queries import filtered_claims
from services.validation import validate_claim_form
from services.workflow import submit_claim

bp = Blueprint("claims", __name__, url_prefix="/claims")


@bp.route("")
@login_required
def index():
    rows = filtered_claims(request.args)
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 10
    total = len(rows)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    page_rows = rows[(page - 1) * per_page: page * per_page]
    departments = [r["department"] for r in get_db().execute("SELECT DISTINCT department FROM claims ORDER BY department")]
    return render_template("claims/index.html", claims=page_rows, page=page, pages=pages,
                           total=total, departments=departments)


def _duplicate_for(employee_id, amount, expense_date, receipt_number, exclude_id=None):
    sql = """SELECT c.id, c.claim_no, c.status FROM claims c
             WHERE c.is_deleted=0 AND c.employee_id=? AND c.amount=? AND c.expense_date=? AND c.receipt_number=?"""
    params = [employee_id, amount, expense_date, receipt_number]
    if exclude_id:
        sql += " AND c.id<>?"
        params.append(exclude_id)
    return get_db().execute(sql, params).fetchall()


@bp.route("/new", methods=["GET", "POST"])
@roles_required("Employee")
def create():
    errors = {}
    duplicate_warning = None
    if request.method == "POST":
        errors, data = validate_claim_form(request.form)
        duplicates = []
        if not errors:
            duplicates = _duplicate_for(current_user()["id"], data["amount"], data["expense_date"], data["receipt_number"])
            if duplicates and request.form.get("confirm_duplicate") != "yes":
                duplicate_warning = duplicates
        if not errors and not duplicate_warning:
            db = get_db()
            now = now_iso()
            cur = db.execute(
                """INSERT INTO claims (employee_id, department, category, description, amount, expense_date,
                   receipt_number, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?)""",
                (current_user()["id"], current_user()["department"], data["category"], data["description"],
                 data["amount"], data["expense_date"], data["receipt_number"], now, now),
            )
            claim_id = cur.lastrowid
            claim_no = f"EXP-{now_local().year}-{claim_id:04d}"
            db.execute("UPDATE claims SET claim_no=? WHERE id=?", (claim_no, claim_id))
            log_action("CREATE", claim_id, None, {"claim_no": claim_no, "status": "Draft", "amount": data["amount"]})
            db.commit()
            flash(f"Claim {claim_no} was created as a Draft.", "success")
            return redirect(url_for("claims.detail", claim_id=claim_id))
    return render_template("claims/form.html", title="Create expense claim", errors=errors,
                           form_data=request.form if request.method == "POST" else {}, duplicate_warning=duplicate_warning,
                           today=now_local().date().isoformat(), min_date=(now_local().date() - timedelta(days=90)).isoformat())


@bp.route("/<int:claim_id>")
@login_required
def detail(claim_id):
    claim = get_visible_claim_or_404(claim_id)
    history = get_db().execute(
        """SELECT a.*, u.full_name AS actor_name, u.role AS actor_role
           FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
           WHERE a.record_id=? AND a.action IN ('CREATE','UPDATE','SUBMIT','APPROVE','REJECT','PAY','DELETE')
           ORDER BY a.timestamp ASC, a.id ASC""",
        (claim_id,),
    ).fetchall()
    user = current_user()
    can_edit = user["role"] == "Employee" and claim["employee_id"] == user["id"] and claim["status"] in ("Draft", "Rejected")
    can_submit = can_edit
    can_delete = user["role"] == "Admin" and not claim["is_deleted"]
    return render_template("claims/detail.html", claim=claim, history=history,
                           can_edit=can_edit, can_submit=can_submit, can_delete=can_delete)


@bp.route("/<int:claim_id>/edit", methods=["GET", "POST"])
@roles_required("Employee")
def edit(claim_id):
    claim = get_visible_claim_or_404(claim_id)
    if claim["employee_id"] != current_user()["id"] or claim["status"] not in ("Draft", "Rejected"):
        abort(403)
    errors = {}
    duplicate_warning = None
    if request.method == "POST":
        errors, data = validate_claim_form(request.form)
        duplicates = []
        if not errors:
            duplicates = _duplicate_for(current_user()["id"], data["amount"], data["expense_date"], data["receipt_number"], claim_id)
            if duplicates and request.form.get("confirm_duplicate") != "yes":
                duplicate_warning = duplicates
        if not errors and not duplicate_warning:
            db = get_db()
            old = {k: claim[k] for k in ("category", "description", "amount", "expense_date", "receipt_number", "status")}
            db.execute(
                """UPDATE claims SET category=?, description=?, amount=?, expense_date=?, receipt_number=?,
                   status='Draft', approver_id=NULL, approval_comment=NULL, submitted_at=NULL, approved_at=NULL,
                   rejected_at=NULL, updated_at=? WHERE id=?""",
                (data["category"], data["description"], data["amount"], data["expense_date"],
                 data["receipt_number"], now_iso(), claim_id),
            )
            new = {"category": data["category"], "description": data["description"],
                   "amount": data["amount"], "expense_date": data["expense_date"],
                   "receipt_number": data["receipt_number"], "status": "Draft"}
            log_action("UPDATE", claim_id, old, new)
            db.commit()
            flash("Claim updated. It is now a Draft and can be submitted again.", "success")
            return redirect(url_for("claims.detail", claim_id=claim_id))
    form_data = request.form if request.method == "POST" else dict(claim)
    return render_template("claims/form.html", title=f"Edit {claim['claim_no']}", errors=errors,
                           form_data=form_data, duplicate_warning=duplicate_warning,
                           today=now_local().date().isoformat(), min_date=(now_local().date() - timedelta(days=90)).isoformat())


@bp.route("/<int:claim_id>/submit", methods=["POST"])
@roles_required("Employee")
def submit(claim_id):
    claim = get_visible_claim_or_404(claim_id)
    submit_claim(claim, current_user())
    flash(f"Claim {claim['claim_no']} was submitted for review.", "success")
    return redirect(url_for("claims.detail", claim_id=claim_id))


@bp.route("/<int:claim_id>/delete", methods=["POST"])
@roles_required("Admin")
def soft_delete(claim_id):
    db = get_db()
    claim = db.execute("SELECT * FROM claims WHERE id=? AND is_deleted=0", (claim_id,)).fetchone()
    if claim is None:
        abort(404)
    old = {"is_deleted": False, "status": claim["status"], "claim_no": claim["claim_no"]}
    db.execute("UPDATE claims SET is_deleted=1, updated_at=? WHERE id=?", (now_iso(), claim_id))
    log_action("DELETE", claim_id, old, {"is_deleted": True})
    db.commit()
    flash(f"{claim['claim_no']} was archived (soft deleted). Its history remains in the database.", "success")
    return redirect(url_for("claims.index"))
