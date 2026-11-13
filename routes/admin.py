from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash
from db import get_db
from security import current_user, log_action, now_iso, roles_required

bp = Blueprint("admin", __name__, url_prefix="/admin")
VALID_ROLES = ("Employee", "Manager", "Finance", "Admin")


@bp.route("/users")
@roles_required("Admin")
def users():
    rows = get_db().execute("SELECT * FROM users ORDER BY role, department, full_name").fetchall()
    return render_template("admin/users.html", users=rows)


@bp.route("/users/new", methods=["GET", "POST"])
@roles_required("Admin")
def create_user():
    errors = {}
    if request.method == "POST":
        data = {k: (request.form.get(k) or "").strip() for k in ("username", "full_name", "email", "role", "department", "password")}
        if not data["username"] or len(data["username"]) < 3:
            errors["username"] = "Username must contain at least 3 characters."
        if not data["full_name"]:
            errors["full_name"] = "Full name is required."
        if "@" not in data["email"]:
            errors["email"] = "Enter a valid email address."
        if data["role"] not in VALID_ROLES:
            errors["role"] = "Choose a valid role."
        if not data["department"]:
            errors["department"] = "Department is required."
        if len(data["password"]) < 8:
            errors["password"] = "Password must contain at least 8 characters."
        if not errors:
            db = get_db()
            try:
                cur = db.execute(
                    """INSERT INTO users (username, full_name, email, password_hash, role, department, is_active, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                    (data["username"].lower(), data["full_name"], data["email"].lower(),
                     generate_password_hash(data["password"]), data["role"], data["department"], now_iso()),
                )
                log_action("USER_CREATE", cur.lastrowid, None,
                           {"username": data["username"], "role": data["role"], "department": data["department"]})
                db.commit()
                flash("User account created.", "success")
                return redirect(url_for("admin.users"))
            except Exception:
                db.rollback()
                errors["username"] = "That username or email is already in use."
    return render_template("admin/user_form.html", title="Create user", user_data=request.form, errors=errors)


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@roles_required("Admin")
def edit_user(user_id):
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if target is None:
        abort(404)
    errors = {}
    if request.method == "POST":
        data = {k: (request.form.get(k) or "").strip() for k in ("full_name", "email", "role", "department", "password")}
        is_active = 1 if request.form.get("is_active") == "1" else 0
        if not data["full_name"]:
            errors["full_name"] = "Full name is required."
        if "@" not in data["email"]:
            errors["email"] = "Enter a valid email address."
        if data["role"] not in VALID_ROLES:
            errors["role"] = "Choose a valid role."
        if not data["department"]:
            errors["department"] = "Department is required."
        if data["password"] and len(data["password"]) < 8:
            errors["password"] = "New password must contain at least 8 characters."
        if user_id == current_user()["id"] and is_active == 0:
            errors["is_active"] = "You cannot deactivate your own administrator account."
        if user_id == current_user()["id"] and data["role"] != "Admin":
            errors["role"] = "You cannot remove your own Admin access."
        if not errors:
            old = {"full_name": target["full_name"], "email": target["email"], "role": target["role"],
                   "department": target["department"], "is_active": bool(target["is_active"]),
                   "locked": bool(target["locked_at"])}
            params = [data["full_name"], data["email"].lower(), data["role"], data["department"], is_active]
            sql = "UPDATE users SET full_name=?, email=?, role=?, department=?, is_active=?"
            if data["password"]:
                sql += ", password_hash=?"
                params.append(generate_password_hash(data["password"]))
            if request.form.get("unlock_account") == "1":
                sql += ", failed_attempts=0, locked_at=NULL"
            sql += " WHERE id=?"
            params.append(user_id)
            try:
                db.execute(sql, params)
                new = {"full_name": data["full_name"], "email": data["email"], "role": data["role"],
                       "department": data["department"], "is_active": bool(is_active),
                       "unlocked": request.form.get("unlock_account") == "1"}
                log_action("USER_UPDATE", user_id, old, new)
                db.commit()
                flash("User account updated.", "success")
                return redirect(url_for("admin.users"))
            except Exception:
                db.rollback()
                errors["email"] = "That email address is already in use."
    data = request.form if request.method == "POST" else dict(target)
    return render_template("admin/user_form.html", title=f"Edit {target['username']}", user_data=data,
                           errors=errors, target=target)


@bp.route("/audit-log")
@roles_required("Admin")
def audit_log():
    db = get_db()
    conditions = []
    params = []
    action = (request.args.get("action") or "").strip()
    username = (request.args.get("username") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if action:
        conditions.append("a.action=?")
        params.append(action)
    if username:
        conditions.append("u.username LIKE ?")
        params.append(f"%{username}%")
    if date_from:
        conditions.append("date(a.timestamp)>=date(?)")
        params.append(date_from)
    if date_to:
        conditions.append("date(a.timestamp)<=date(?)")
        params.append(date_to)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = db.execute(
        f"""SELECT a.*, u.username, u.full_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
            {where} ORDER BY a.timestamp DESC, a.id DESC LIMIT 500""", params,
    ).fetchall()
    actions = [r["action"] for r in db.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")]
    return render_template("admin/audit_log.html", logs=rows, actions=actions)
