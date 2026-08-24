import logging

from app import db
from app.models import User
from app.services.category_service import create_starter_categories
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)


def register_user(data):
    try:
        if db.session.query(User).filter_by(username=data['username']).first():
            raise ValueError("Użytkownik o tej nazwie już istnieje.")
        if db.session.query(User).filter_by(email=data['email']).first():
            raise ValueError("Konto z tym adresem email już istnieje.")

        hashed_pwd = generate_password_hash(data['password'])
        new_user = User(username=data['username'], email=data['email'], password_hash=hashed_pwd)

        db.session.add(new_user)
        # flush nadaje token UUID (default przy insercie) — potrzebny jako wlasciciel
        # kategorii startowych. Jeden commit ponizej domyka konto i jego kategorie
        # atomowo: nie da sie zalozyc uzytkownika bez kategorii ani odwrotnie.
        db.session.flush()
        create_starter_categories(new_user.token, commit=False)

        db.session.commit()
        logger.info("Zarejestrowano uzytkownika %s (token=%s)", new_user.username, new_user.token)
        return new_user
    except Exception:
        db.session.rollback()
        raise

def authenticate_user(username_or_email, password):
    user = db.session.query(User).filter(
        (User.username == username_or_email) | (User.email == username_or_email)
    ).first()
    if user and check_password_hash(user.password_hash, password):
        return user
    return None