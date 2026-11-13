import os
from flask import Flask, abort, redirect, render_template, url_for
from flask_wtf.csrf import CSRFProtect
from config import Config
from db import close_db, init_db
from security import current_user, load_user
from routes.auth import bp as auth_bp
from routes.main import bp as main_bp
from routes.claims import bp as claims_bp
from routes.approvals import bp as approvals_bp
from routes.finance import bp as finance_bp
from routes.admin import bp as admin_bp
from routes.reports import bp as reports_bp
from routes.exports import bp as exports_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    CSRFProtect(app)
    app.teardown_appcontext(close_db)
    app.before_request(load_user)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(claims_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(exports_bp)

    app.jinja_env.filters["idr"] = lambda value: "Rp " + format(int(value or 0), ",").replace(",", ".")

    @app.context_processor
    def inject_template_globals():
        user = current_user()
        return {
            "logged_in_user": user,
            "app_categories": app.config["CATEGORIES"],
            "approval_limit": app.config["APPROVAL_LIMIT"],
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cache-Control", "no-store") if response.headers.get("Content-Type", "").startswith("text/html") else None
        return response

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("errors/500.html"), 500

    with app.app_context():
        init_db()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
