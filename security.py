import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import abort, current_app, flash, g, redirect, request, session, url_for
from db import get_db

JAKARTA = timezone(timedelta(hours=7), name="Asia/Jakarta")


def now_local():
    return datetime.now(JAKARTA).replace(tzinfo=None, microsecond=0)


def now_iso():
    return now_local().isoformat(sep=" ")


def get_user_by_id(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def load_user():
    g.user = None
    user_id = session.get("user_id")
    if not user_id:
        return
    last_activity = session.get("last_activity")
    if last_activity:
        try:
            last_dt = datetime.fromisoformat(last_activity)
            if now_local() - last_dt > timedelta(minutes=15):
                session.clear()
                flash("Your session expired after 15 minutes of inactivity. Please log in again.", "warning")
                return
        except ValueError:
            session.clear()
            return
    user = get_user_by_id(user_id)
    if user is None or not user["is_active"]:
        session.clear()
        return
    g.user = user
    if request.endpoint not in ("auth.login", "static"):
        session["last_activity"] = now_iso()


def current_user():
    return getattr(g, "user", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def log_action(action, record_id=None, old_value=None, new_value=None, user_id=None, timestamp=None):
    user = current_user()
    actor_id = user_id if user_id is not None else (user["id"] if user else None)
    db = get_db()
    db.execute(
        """INSERT INTO audit_log (user_id, action, record_id, old_value, new_value, timestamp, ip_address)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            actor_id,
            action,
            record_id,
            json.dumps(old_value, ensure_ascii=False, default=str) if old_value is not None else None,
            json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None,
            timestamp or now_iso(),
            request.remote_addr or "unknown",
        ),
    )


def claim_is_visible(claim, user):
    if not user or not claim:
        return False
    if user["role"] == "Admin":
        return True
    if user["role"] == "Employee":
        return claim["employee_id"] == user["id"]
    if user["role"] == "Manager":
        return claim["department"] == user["department"]
    if user["role"] == "Finance":
        return claim["status"] in ("Approved", "Paid")
    return False


def get_visible_claim_or_404(claim_id, user=None):
    from flask import abort
    user = user or current_user()
    claim = get_db().execute(
        """SELECT c.*, e.full_name AS employee_name, e.username AS employee_username,
                  a.full_name AS approver_name, a.role AS approver_role
           FROM claims c JOIN users e ON e.id = c.employee_id
           LEFT JOIN users a ON a.id = c.approver_id
           WHERE c.id = ?""",
        (claim_id,),
    ).fetchone()
    if claim is None:
        abort(404)
    if claim["is_deleted"] and user["role"] != "Admin":
        abort(404)
    if not claim_is_visible(claim, user):
        abort(403)
    return claim
