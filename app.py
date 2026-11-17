import os

from flask import Flask, render_template
from flask_login import current_user, logout_user

from extensions import csrf, db, login_manager


def create_app():
    app = Flask(__name__)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "events.db")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    import models  # noqa: F401
    from blueprints.auth import bp as auth_bp
    from blueprints.events import bp as events_bp
    from blueprints.manage import bp as manage_bp
    from blueprints.moderator import bp as moderator_bp
    from blueprints.profile import bp as profile_bp

    for bp in (auth_bp, events_bp, manage_bp, moderator_bp, profile_bp):
        app.register_blueprint(bp)

    @app.template_filter("dt")
    def fmt_dt(value):
        return value.strftime("%d.%m.%Y %H:%M") if value else ""

    @app.template_filter("money")
    def fmt_money(value):
        return "Безкоштовно" if not value else f"{value:g} грн"

    @app.before_request
    def block_banned_users():
        if current_user.is_authenticated and not current_user.is_active:
            logout_user()

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="Недостатньо прав для цієї дії."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="Сторінку не знайдено."), 404

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
