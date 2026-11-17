"""Бізнес-логіка бронювання."""
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Booking, EVENT_CANCELLED, EVENT_DRAFT


class BookingError(Exception):
    pass


def booking_block_reason(user, event):
    """Повертає текст причини, чому бронювання неможливе, або None, якщо можна."""
    now = datetime.now()

    if event.organizer_id == user.id:
        return "Організатор не може бронювати власний захід."
    if event.status == EVENT_DRAFT:
        return "Захід ще не опубліковано."
    if event.status == EVENT_CANCELLED:
        return "Захід скасовано - бронювання неможливе."
    if event.end_time <= now:
        return "Захід уже завершився - бронювання неможливе."
    if event.start_time <= now:
        return "Захід уже розпочався - бронювання неможливе."

    existing = Booking.query.filter_by(user_id=user.id, event_id=event.id).first()
    if existing:
        if existing.status == "cancelled":
            return "Ви вже бронювали цей захід раніше (бронювання скасовано). Повторне бронювання неможливе."
        return "Ви вже забронювали цей захід."
    if event.seats_left <= 0:
        return "Вільних місць не залишилось."
    return None


def book_event(user, event):
    reason = booking_block_reason(user, event)
    if reason:
        raise BookingError(reason)
    booking = Booking(user_id=user.id, event_id=event.id)
    db.session.add(booking)
    try:
        db.session.commit()
    except IntegrityError:  # захист від подвійного кліку / гонки запитів
        db.session.rollback()
        raise BookingError("Ви вже забронювали цей захід.")
    return booking


def cancel_booking(booking):
    if booking.status != "active":
        raise BookingError("Це бронювання вже скасоване.")
    if booking.event.state != "upcoming":
        raise BookingError("Скасувати бронювання можна лише до початку активного заходу.")
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now()
    db.session.commit()
