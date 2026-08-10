from sqlalchemy import or_
from app import db
from app.models import Category


def visible_to(user_token):
    """Filtr kategorii widocznych dla użytkownika: własne + globalne (user_token IS NULL).

    Globalne to kategorie systemowe i historyczne (sprzed rozdzielenia na właścicieli) —
    każdy je widzi, nikt nie może ich usunąć.
    """
    return or_(Category.user_token == user_token, Category.user_token.is_(None))


def find_by_name(user_token, name):
    """Aktywna kategoria o danej nazwie widoczna dla użytkownika, albo None.

    Jedyne miejsce, w którym kategoria jest rozwiązywana po nazwie — serwisy i
    blueprinty wołają to zamiast własnych zapytań, żeby zakres widoczności był
    definiowany raz.
    """
    if not name:
        return None
    return (
        db.session.query(Category)
        .filter_by(name=name, is_active=True)
        .filter(visible_to(user_token))
        .first()
    )


def list_active(user_token):
    """Kategorie widoczne dla użytkownika, posortowane po nazwie."""
    return (
        db.session.query(Category)
        .filter_by(is_active=True)
        .filter(visible_to(user_token))
        .order_by(Category.name)
        .all()
    )


def create_category(user_token, data):
    try:
        if find_by_name(user_token, data['name']):
            raise ValueError('Kategoria o tej nazwie już istnieje')

        new_cat = Category(name=data['name'], type=data['type'], user_token=user_token)
        db.session.add(new_cat)
        db.session.commit()
        return new_cat
    except Exception:
        db.session.rollback()
        raise

def soft_delete_category(user_token, cat_name):
    try:
        # Tylko własne kategorie — globalnych (systemowych) nie usuwamy, bo widzą je
        # wszyscy użytkownicy.
        category = db.session.query(Category).filter_by(
            name=cat_name, is_active=True, user_token=user_token
        ).first()
        if not category:
            raise ValueError('Nie znaleziono własnej aktywnej kategorii o tej nazwie.')
        category.is_active = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
