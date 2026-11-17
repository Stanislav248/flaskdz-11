from datetime import date, datetime, time, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from extensions import db
from models import Booking, Category, Event, EVENT_CANCELLED, EVENT_PUBLISHED
from services import BookingError, book_event, booking_block_reason, cancel_booking

bp = Blueprint("events", __name__)

PER_PAGE = 9
SORTS = {
    "date": "Спочатку найближчі",
    "popularity": "За популярністю",
    "price_asc": "Ціна: від найменшої",
    "price_desc": "Ціна: від найбільшої",
}


def _to_float(v):
    try:
        return float(v.replace(",", ".")) if v else None
    except ValueError:
        return None


def _to_int(v):
    try:
        return int(v) if v else None
    except ValueError:
        return None


def _to_date(v):
    try:
        return datetime.strptime(v, "%Y-%m-%d").date() if v else None
    except ValueError:
        return None


@bp.route("/")
@bp.route("/events")
def event_list():
    args = {k: v.strip() for k, v in request.args.items() if k != "page" and v.strip()}
    now = datetime.now()

    # у загальному списку - лише опубліковані (і скасовані, щоб було видно статус)
    query = Event.query.filter(Event.status.in_([EVENT_PUBLISHED, EVENT_CANCELLED]))

    if args.get("q"):
        like = f"%{args['q']}%"
        query = query.filter(or_(Event.title.ilike(like), Event.description.ilike(like), Event.location.ilike(like)))
    if _to_int(args.get("category")):
        query = query.filter(Event.category_id == _to_int(args["category"]))

    d_from, d_to = _to_date(args.get("date_from")), _to_date(args.get("date_to"))
    if d_from:
        query = query.filter(Event.start_time >= datetime.combine(d_from, time.min))
    if d_to:
        query = query.filter(Event.start_time < datetime.combine(d_to + timedelta(days=1), time.min))

    p_min, p_max = _to_float(args.get("price_min")), _to_float(args.get("price_max"))
    if p_min is not None:
        query = query.filter(Event.price >= p_min)
    if p_max is not None:
        query = query.filter(Event.price <= p_max)

    if not args.get("show_past"):
        query = query.filter(Event.end_time > now)

    sort = args.get("sort", "date")
    if sort == "popularity":
        pop = (
            db.session.query(Booking.event_id, func.count(Booking.id).label("cnt"))
            .filter(Booking.status == "active")
            .group_by(Booking.event_id)
            .subquery()
        )
        query = query.outerjoin(pop, pop.c.event_id == Event.id).order_by(
            func.coalesce(pop.c.cnt, 0).desc(), Event.start_time
        )
    elif sort == "price_asc":
        query = query.order_by(Event.price.asc(), Event.start_time)
    elif sort == "price_desc":
        query = query.order_by(Event.price.desc(), Event.start_time)
    else:
        query = query.order_by(Event.start_time)

    page = max(_to_int(request.args.get("page")) or 1, 1)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "events/list.html", pagination=pagination, categories=categories, args=args, sorts=SORTS
    )


@bp.route("/events/<int:event_id>")
def event_detail(event_id):
    event = db.get_or_404(Event, event_id)
    can_see_draft = current_user.is_authenticated and (
        current_user.is_moderator or event.organizer_id == current_user.id
    )
    if event.status == "draft" and not can_see_draft:
        abort(404)

    booking, block_reason = None, None
    if current_user.is_authenticated:
        booking = Booking.query.filter_by(user_id=current_user.id, event_id=event.id).first()
        block_reason = booking_block_reason(current_user, event)
    return render_template("events/detail.html", event=event, booking=booking, block_reason=block_reason)


@bp.route("/events/<int:event_id>/book", methods=["POST"])
@login_required
def book(event_id):
    event = db.get_or_404(Event, event_id)
    try:
        book_event(current_user, event)
        flash("Захід успішно заброньовано!", "success")
    except BookingError as e:
        flash(str(e), "danger")
    return redirect(url_for("events.event_detail", event_id=event.id))


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.user_id != current_user.id:
        abort(403)
    try:
        cancel_booking(booking)
        flash("Бронювання скасовано.", "info")
    except BookingError as e:
        flash(str(e), "danger")
    return redirect(request.form.get("next") or url_for("profile.view"))
