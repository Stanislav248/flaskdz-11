"""Керування заходами: адмін (організатор) - свої, модератор - усі."""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db
from models import Category, Event, EVENT_CANCELLED, EVENT_DRAFT, EVENT_PUBLISHED
from permissions import roles_required

bp = Blueprint("manage", __name__, url_prefix="/manage")

DT_FORMAT = "%Y-%m-%dT%H:%M"
organizer_only = roles_required("admin", "moderator")


def get_managed_event(event_id):
    event = db.get_or_404(Event, event_id)
    if not current_user.is_moderator and event.organizer_id != current_user.id:
        abort(403)
    return event


def parse_event_form(f, event=None):
    errors = []
    title = f.get("title", "").strip()
    if not title:
        errors.append("Вкажіть назву заходу.")

    def parse_dt(key, label):
        try:
            return datetime.strptime(f.get(key, ""), DT_FORMAT)
        except ValueError:
            errors.append(f"Вкажіть коректну дату: {label}.")
            return None

    start, end = parse_dt("start_time", "початок"), parse_dt("end_time", "завершення")
    if start and end and end <= start:
        errors.append("Завершення має бути пізніше за початок.")

    try:
        price = float(f.get("price", "0").replace(",", ".") or 0)
        if price < 0:
            raise ValueError
    except ValueError:
        errors.append("Ціна має бути числом не менше 0.")
        price = 0
    try:
        capacity = int(f.get("capacity", ""))
        if capacity < 1:
            raise ValueError
    except ValueError:
        errors.append("Кількість місць має бути цілим числом від 1.")
        capacity = None
    if event and capacity is not None and capacity < event.active_bookings_count:
        errors.append(f"Кількість місць не може бути меншою за наявні бронювання ({event.active_bookings_count}).")

    category_id = None
    if f.get("category_id"):
        category = db.session.get(Category, int(f["category_id"])) if f["category_id"].isdigit() else None
        if not category:
            errors.append("Обрано неіснуючу категорію.")
        else:
            category_id = category.id

    data = dict(
        title=title, description=f.get("description", "").strip(), location=f.get("location", "").strip(),
        category_id=category_id, start_time=start, end_time=end, price=price, capacity=capacity,
    )
    return data, errors


def event_to_form(event):
    return dict(
        title=event.title, description=event.description, location=event.location,
        category_id=str(event.category_id or ""), price=f"{event.price:g}", capacity=event.capacity,
        start_time=event.start_time.strftime(DT_FORMAT), end_time=event.end_time.strftime(DT_FORMAT),
    )


@bp.route("/events")
@organizer_only
def my_events():
    query = Event.query
    if not current_user.is_moderator:
        query = query.filter_by(organizer_id=current_user.id)
    events = query.order_by(Event.start_time.desc()).all()
    return render_template("manage/events.html", events=events)


@bp.route("/events/new", methods=["GET", "POST"])
@organizer_only
def create():
    form = request.form if request.method == "POST" else {"price": "0", "capacity": "50"}
    if request.method == "POST":
        data, errors = parse_event_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            publish = request.form.get("action") == "publish"
            event = Event(**data, organizer_id=current_user.id,
                          status=EVENT_PUBLISHED if publish else EVENT_DRAFT)
            db.session.add(event)
            db.session.commit()
            flash("Захід опубліковано." if publish else "Чернетку збережено.", "success")
            return redirect(url_for("manage.my_events"))
    return render_template("manage/event_form.html", form=form, event=None,
                           categories=Category.query.order_by(Category.name).all())


@bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@organizer_only
def edit(event_id):
    event = get_managed_event(event_id)
    form = request.form if request.method == "POST" else event_to_form(event)
    if request.method == "POST":
        data, errors = parse_event_form(request.form, event)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            for key, value in data.items():
                setattr(event, key, value)
            if event.status != EVENT_CANCELLED:
                event.status = EVENT_PUBLISHED if request.form.get("action") == "publish" else EVENT_DRAFT
                if event.status == EVENT_DRAFT and event.active_bookings_count:
                    event.status = EVENT_PUBLISHED
                    flash("Є активні бронювання - захід залишається опублікованим. Щоб відмінити його, скористайтесь «Скасувати».", "warning")
            db.session.commit()
            flash("Захід оновлено.", "success")
            return redirect(url_for("manage.my_events"))
    return render_template("manage/event_form.html", form=form, event=event,
                           categories=Category.query.order_by(Category.name).all())


@bp.route("/events/<int:event_id>/publish", methods=["POST"])
@organizer_only
def publish(event_id):
    event = get_managed_event(event_id)
    if event.status == EVENT_CANCELLED:
        flash("Скасований захід не можна опублікувати.", "danger")
    else:
        event.status = EVENT_PUBLISHED
        db.session.commit()
        flash("Захід опубліковано.", "success")
    return redirect(url_for("manage.my_events"))


@bp.route("/events/<int:event_id>/unpublish", methods=["POST"])
@organizer_only
def unpublish(event_id):
    event = get_managed_event(event_id)
    if event.active_bookings_count:
        flash("Не можна зняти з публікації захід з активними бронюваннями - скасуйте його.", "danger")
    elif event.status == EVENT_PUBLISHED:
        event.status = EVENT_DRAFT
        db.session.commit()
        flash("Захід знято з публікації.", "info")
    return redirect(url_for("manage.my_events"))


@bp.route("/events/<int:event_id>/cancel", methods=["POST"])
@organizer_only
def cancel(event_id):
    event = get_managed_event(event_id)
    event.status = EVENT_CANCELLED
    db.session.commit()
    flash("Захід скасовано. Бронювання учасників позначено як скасовані.", "info")
    return redirect(url_for("manage.my_events"))


@bp.route("/events/<int:event_id>/delete", methods=["POST"])
@organizer_only
def delete(event_id):
    event = get_managed_event(event_id)
    db.session.delete(event)
    db.session.commit()
    flash("Захід видалено.", "info")
    return redirect(url_for("manage.my_events"))


@bp.route("/events/<int:event_id>/bookings")
@organizer_only
def bookings(event_id):
    event = get_managed_event(event_id)
    return render_template("manage/event_bookings.html", event=event)
