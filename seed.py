"""Заповнення БД тестовими даними: python seed.py"""
from datetime import datetime, timedelta

from app import app
from extensions import db
from models import Booking, Category, Event, User


def make_user(username, email, password, role, full_name=""):
    u = User(username=username, email=email, role=role, full_name=full_name)
    u.set_password(password)
    db.session.add(u)
    return u


with app.app_context():
    if User.query.first():
        print("БД вже містить дані - seed пропущено.")
        raise SystemExit

    mod = make_user("moderator", "moderator@example.com", "Moderator123", "moderator", "Головний модератор")
    adm = make_user("organizer", "admin@example.com", "Admin12345", "admin", "Олена Організатор")
    usr = make_user("user", "user@example.com", "User12345", "user", "Іван Користувач")
    usr2 = make_user("user2", "user2@example.com", "User12345", "user", "Марія Учасниця")
    cats = {n: Category(name=n) for n in ["Музика", "IT та технології", "Спорт", "Освіта", "Мистецтво"]}
    db.session.add_all(cats.values())
    db.session.commit()

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    h = lambda days, hours=0: now + timedelta(days=days, hours=hours)

    def ev(title, cat, start, dur_h, price, cap, status="published", loc="Івано-Франківськ", org=adm):
        e = Event(title=title, description=f"Опис заходу «{title}». Приходьте, буде цікаво!", location=loc,
                  category_id=cats[cat].id, organizer_id=org.id, start_time=start,
                  end_time=start + timedelta(hours=dur_h), price=price, capacity=cap, status=status)
        db.session.add(e)
        return e

    e1 = ev("Jazz Night просто неба", "Музика", h(5, 3), 3, 250, 100)
    e2 = ev("Python Meetup", "IT та технології", h(7), 2, 0, 40, loc="Коворкінг 'Хаб'")
    e3 = ev("Ранковий забіг", "Спорт", h(2, -8), 2, 50, 200, loc="Парк Шевченка")
    e4 = ev("Воркшоп з акварелі", "Мистецтво", h(10), 4, 400, 15)
    e5 = ev("Лекція: основи Flask", "Освіта", h(14), 2, 100, 60, org=mod)
    ev("Фестиваль (скасовано)", "Музика", h(6), 5, 500, 300, status="cancelled")
    ev("Минулий хакатон", "IT та технології", h(-10), 8, 0, 80)
    ev("Захід, що вже триває", "Спорт", h(0, -1), 5, 0, 30)
    ev("Чернетка нового заходу", "Освіта", h(20), 2, 150, 25, status="draft")
    db.session.commit()

    for u, e in [(usr, e1), (usr, e2), (usr2, e1), (usr2, e2), (usr2, e3), (usr2, e4)]:
        db.session.add(Booking(user_id=u.id, event_id=e.id))
    past = Event.query.filter_by(title="Минулий хакатон").first()
    db.session.add(Booking(user_id=usr.id, event_id=past.id))
    db.session.commit()
    print("Готово. Акаунти:\n"
          "  moderator@example.com / Moderator123\n"
          "  admin@example.com     / Admin12345\n"
          "  user@example.com      / User12345")
