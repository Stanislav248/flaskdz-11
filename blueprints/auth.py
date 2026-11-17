import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import User

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("events.event_list"))
    form = request.form
    if request.method == "POST":
        username = form.get("username", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        errors = []
        if len(username) < 3:
            errors.append("Ім'я користувача має містити мінімум 3 символи.")
        if not EMAIL_RE.match(email):
            errors.append("Введіть коректний email.")
        if len(password) < 8:
            errors.append("Пароль має містити мінімум 8 символів.")
        if password != form.get("password2", ""):
            errors.append("Паролі не збігаються.")
        if User.query.filter_by(username=username).first():
            errors.append("Таке ім'я користувача вже зайняте.")
        if User.query.filter_by(email=email).first():
            errors.append("Цей email уже зареєстрований.")
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            user = User(username=username, email=email, role="user")  # роль завжди user
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Реєстрація успішна. Ласкаво просимо!", "success")
            return redirect(url_for("events.event_list"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("events.event_list"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(request.form.get("password", "")):
            flash("Невірний email або пароль.", "danger")
        elif not user.is_active:
            flash("Акаунт заблоковано модератором.", "danger")
        else:
            login_user(user, remember=bool(request.form.get("remember")))
            flash("Ви увійшли в систему.", "success")
            return redirect(safe_next(request.args.get("next")) or url_for("events.event_list"))
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Ви вийшли із системи.", "info")
    return redirect(url_for("auth.login"))
