from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints.auth import EMAIL_RE
from extensions import db
from models import Booking, User

bp = Blueprint("profile", __name__, url_prefix="/profile")

FILTERS = {"all": "Усі", "active": "Активні", "completed": "Завершені", "cancelled": "Скасовані"}


@bp.route("/")
@login_required
def view():
    status = request.args.get("status", "all")
    if status not in FILTERS:
        status = "all"
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    counts = {key: 0 for key in FILTERS}
    for b in bookings:
        counts["all"] += 1
        counts[b.display_status] += 1
    if status != "all":
        bookings = [b for b in bookings if b.display_status == status]
    return render_template("profile/view.html", bookings=bookings, status=status, filters=FILTERS, counts=counts)


@bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    form = request.form if request.method == "POST" else {
        "username": current_user.username, "email": current_user.email,
        "full_name": current_user.full_name, "phone": current_user.phone, "bio": current_user.bio,
    }
    if request.method == "POST":
        username = form.get("username", "").strip()
        email = form.get("email", "").strip().lower()
        errors = []
        if len(username) < 3:
            errors.append("Ім'я користувача має містити мінімум 3 символи.")
        if not EMAIL_RE.match(email):
            errors.append("Введіть коректний email.")
        if User.query.filter(User.username == username, User.id != current_user.id).first():
            errors.append("Таке ім'я користувача вже зайняте.")
        if User.query.filter(User.email == email, User.id != current_user.id).first():
            errors.append("Цей email уже використовується.")

        new_password = form.get("new_password", "")
        if new_password:
            if not current_user.check_password(form.get("current_password", "")):
                errors.append("Поточний пароль введено невірно.")
            if len(new_password) < 8:
                errors.append("Новий пароль має містити мінімум 8 символів.")
            if new_password != form.get("new_password2", ""):
                errors.append("Нові паролі не збігаються.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            current_user.username = username
            current_user.email = email
            current_user.full_name = form.get("full_name", "").strip()
            current_user.phone = form.get("phone", "").strip()
            current_user.bio = form.get("bio", "").strip()
            if new_password:
                current_user.set_password(new_password)
            db.session.commit()
            flash("Профіль оновлено.", "success")
            return redirect(url_for("profile.view"))
    return render_template("profile/edit.html", form=form)
