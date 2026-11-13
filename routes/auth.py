from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from db import get_db
from security import current_user, log_action, now_iso

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            log_action("FAILED_LOGIN", None, None, {"username": username}, user_id=None)
            db.commit()
            flash("The username or password is incorrect.", "danger")
        elif not user["is_active"]:
            log_action("FAILED_LOGIN", user_id=user["id"], new_value={"reason": "inactive account"})
            db.commit()
            flash("This account is inactive. Contact an administrator.", "danger")
        elif user["locked_at"]:
            log_action("FAILED_LOGIN", user_id=user["id"], new_value={"reason": "locked account"})
            db.commit()
            flash("This account is locked after five failed login attempts. Contact an administrator.", "danger")
        elif not check_password_hash(user["password_hash"], password):
            attempts = user["failed_attempts"] + 1
            locked_at = now_iso() if attempts >= 5 else None
            db.execute("UPDATE users SET failed_attempts = ?, locked_at = ? WHERE id = ?",
                       (attempts, locked_at, user["id"]))
            log_action("FAILED_LOGIN", user_id=user["id"],
                       old_value={"failed_attempts": user["failed_attempts"]},
                       new_value={"failed_attempts": attempts, "locked": bool(locked_at)})
            db.commit()
            if locked_at:
                flash("Account locked after five failed login attempts. Ask an administrator to unlock it.", "danger")
            else:
                flash(f"The username or password is incorrect. Attempt {attempts} of 5.", "danger")
        else:
            db.execute("UPDATE users SET failed_attempts = 0, locked_at = NULL WHERE id = ?", (user["id"],))
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["last_activity"] = now_iso()
            log_action("LOGIN", user_id=user["id"], new_value={"username": user["username"]})
            db.commit()
            target = request.args.get("next", "")
            if not target.startswith("/") or target.startswith("//"):
                target = url_for("main.dashboard")
            return redirect(target)
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    if user_id:
        log_action("LOGOUT", user_id=user_id, new_value={"result": "success"})
        get_db().commit()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
