from datetime import date
from flask import Blueprint, render_template
from db import get_db
from security import login_required, current_user

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", **dashboard_context())


@bp.route("/dashboard")
@login_required
def dashboard_alias():
    return render_template("dashboard.html", **dashboard_context())


def dashboard_context():
    user = current_user()
    db = get_db()
    where = "c.is_deleted = 0"
    params = []
    if user["role"] == "Employee":
        where += " AND c.employee_id = ?"
        params.append(user["id"])
    elif user["role"] == "Manager":
        where += " AND c.department = ?"
        params.append(user["department"])
    elif user["role"] == "Finance":
        where += " AND c.status IN ('Approved','Paid')"
    rows = db.execute(
        f"SELECT status, COUNT(*) AS count, COALESCE(SUM(amount),0) AS total FROM claims c WHERE {where} GROUP BY status",
        params,
    ).fetchall()
    status_stats = {r["status"]: {"count": r["count"], "total": r["total"]} for r in rows}
    for status in ("Draft", "Submitted", "Approved", "Rejected", "Paid"):
        status_stats.setdefault(status, {"count": 0, "total": 0})
    monthly_rows = db.execute(
        f"""SELECT substr(expense_date,1,7) AS month, SUM(amount) AS total
             FROM claims c WHERE {where} AND expense_date >= date('now','-5 months')
             GROUP BY substr(expense_date,1,7) ORDER BY month""", params,
    ).fetchall()
    category_rows = db.execute(
        f"""SELECT category, SUM(amount) AS total, COUNT(*) AS count
             FROM claims c WHERE {where} GROUP BY category ORDER BY total DESC LIMIT 5""", params,
    ).fetchall()
    recent = db.execute(
        f"""SELECT c.*, u.full_name AS employee_name FROM claims c
             JOIN users u ON u.id = c.employee_id WHERE {where}
             ORDER BY c.created_at DESC LIMIT 6""", params,
    ).fetchall()
    if user["role"] == "Manager":
        pending = db.execute(
            """SELECT COUNT(*) FROM claims WHERE is_deleted=0 AND status='Submitted'
               AND department=? AND amount<=5000000 AND employee_id<>?""",
            (user["department"], user["id"]),
        ).fetchone()[0]
    elif user["role"] == "Admin":
        pending = db.execute(
            "SELECT COUNT(*) FROM claims WHERE is_deleted=0 AND status='Submitted' AND amount>5000000 AND employee_id<>?",
            (user["id"],),
        ).fetchone()[0]
    elif user["role"] == "Finance":
        pending = db.execute("SELECT COUNT(*) FROM claims WHERE is_deleted=0 AND status='Approved'").fetchone()[0]
    else:
        pending = db.execute("SELECT COUNT(*) FROM claims WHERE is_deleted=0 AND employee_id=? AND status='Rejected'", (user["id"],)).fetchone()[0]
    return {
        "status_stats": status_stats,
        "monthly_labels": [r["month"] for r in monthly_rows],
        "monthly_values": [r["total"] for r in monthly_rows],
        "top_categories": category_rows,
        "recent_claims": recent,
        "pending_count": pending,
        "total_claims": sum(v["count"] for v in status_stats.values()),
        "total_amount": sum(v["total"] for v in status_stats.values()),
    }
