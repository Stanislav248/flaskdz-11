from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Booking, Category, Event, ROLES, User, ROLE_LABELS
from permissions import roles_required

bp = Blueprint("moderator", __name__, url_prefix="/moderator")
moderator_only = roles_required("moderator")


@bp.route("/users")
@moderator_only
def users():
    stats = {
        "users": User.query.count(),
        "events": Event.query.count(),
        "bookings": Booking.query.filter_by(status="active").count(),
    }
    return render_template("moderator/users.html", users=User.query.order_by(User.id).all(),
                           roles=ROLES, role_labels=ROLE_LABELS, stats=stats)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@moderator_only
def set_role(user_id):
    user = db.get_or_404(User, user_id)
    role = request.form.get("role")
    if role not in ROLES:
        flash("Невідома роль.", "danger")
    elif user.id == current_user.id:
        flash("Не можна змінити власну роль.", "danger")
    else:
        user.role = role
        db.session.commit()
        flash(f"Роль користувача {user.username} змінено на «{ROLE_LABELS[role]}».", "success")
    return redirect(url_for("moderator.users"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@moderator_only
def toggle_active(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Не можна заблокувати власний акаунт.", "danger")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"Акаунт {user.username} {'розблоковано' if user.is_active else 'заблоковано'}.", "info")
    return redirect(url_for("moderator.users"))


@bp.route("/categories", methods=["GET", "POST"])
@moderator_only
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Вкажіть назву категорії.", "danger")
        else:
            db.session.add(Category(name=name))
            try:
                db.session.commit()
                flash("Категорію додано.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("Така категорія вже існує.", "danger")
        return redirect(url_for("moderator.categories"))
    return render_template("moderator/categories.html", categories=Category.query.order_by(Category.name).all())


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@moderator_only
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    if category.events:
        flash("Категорія використовується в заходах - видалення неможливе.", "danger")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Категорію видалено.", "info")
    return redirect(url_for("moderator.categories"))
