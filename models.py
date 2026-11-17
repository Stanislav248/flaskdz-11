from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager

ROLE_USER = "user"
ROLE_ADMIN = "admin"          # організатор заходів
ROLE_MODERATOR = "moderator"  # повний контроль над платформою
ROLES = (ROLE_USER, ROLE_ADMIN, ROLE_MODERATOR)
ROLE_LABELS = {ROLE_USER: "Користувач", ROLE_ADMIN: "Адмін (організатор)", ROLE_MODERATOR: "Модератор"}

EVENT_DRAFT = "draft"
EVENT_PUBLISHED = "published"
EVENT_CANCELLED = "cancelled"

STATE_LABELS = {
    "draft": "Чернетка",
    "upcoming": "Очікується",
    "ongoing": "Триває",
    "finished": "Завершено",
    "cancelled": "Скасовано",
}

BOOKING_LABELS = {"active": "Активне", "cancelled": "Скасоване", "completed": "Завершене"}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER)
    full_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(30), default="")
    bio = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_moderator(self):
        return self.role == ROLE_MODERATOR

    @property
    def is_organizer(self):
        return self.role in (ROLE_ADMIN, ROLE_MODERATOR)

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    location = db.Column(db.String(200), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    capacity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default=EVENT_DRAFT)
    created_at = db.Column(db.DateTime, default=datetime.now)

    category = db.relationship("Category", backref="events")
    organizer = db.relationship("User", backref="events")
    bookings = db.relationship("Booking", backref="event", cascade="all, delete-orphan")

    @property
    def state(self):
        """draft / cancelled / finished / ongoing / upcoming"""
        now = datetime.now()
        if self.status == EVENT_DRAFT:
            return "draft"
        if self.status == EVENT_CANCELLED:
            return "cancelled"
        if self.end_time <= now:
            return "finished"
        if self.start_time <= now:
            return "ongoing"
        return "upcoming"

    @property
    def state_label(self):
        return STATE_LABELS[self.state]

    @property
    def active_bookings_count(self):
        return sum(1 for b in self.bookings if b.status == "active")

    @property
    def seats_left(self):
        return max(self.capacity - self.active_bookings_count, 0)


class Booking(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "event_id", name="uq_user_event"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # active / cancelled
    created_at = db.Column(db.DateTime, default=datetime.now)
    cancelled_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="bookings")

    @property
    def display_status(self):
        """active / cancelled / completed - для історії бронювань."""
        if self.status == "cancelled" or self.event.status == EVENT_CANCELLED:
            return "cancelled"
        if self.event.end_time <= datetime.now():
            return "completed"
        return "active"

    @property
    def display_label(self):
        return BOOKING_LABELS[self.display_status]
