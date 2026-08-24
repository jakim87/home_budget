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


def find_owned(user_token, category_id):
    """Aktywna kategoria o danym ID widoczna dla użytkownika (własna lub globalna), albo None.

    Jedyne miejsce, w którym kategoria jest rozwiązywana po ID — używane wszędzie tam,
    gdzie category_id przychodzi z żądania jako liczba (transakcje, harmonogramy),
    żeby nie dało się podpiąć cudzej prywatnej kategorii (patrz #127).
    """
    if category_id is None:
        return None
    return (
        db.session.query(Category)
        .filter_by(id=category_id, is_active=True)
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


# Zestaw kategorii zakladanych nowemu uzytkownikowi. Celowo krotki: skasowanie
# zbednej kategorii to jedno klikniecie, a wymyslenie brakujacej wymaga najpierw
# zrozumienia, ze w ogole mozna. Nazwy spojne z konwencja uzywana w aplikacji.
#
# "Przelew wewnetrzny" (typ transfer) jest OBOWIAZKOWY — bez kategorii tego typu
# mechanizm przelewow miedzy kontami wlasnymi w ogole sie nie uruchamia
# (patrz budget_service._handle_internal_transfer).
STARTER_CATEGORIES = [
    ('Zakupy spożywcze', 'expense'),
    ('Paliwo', 'expense'),
    ('Rachunki', 'expense'),
    ('Zdrowie', 'expense'),
    ('Rozrywka', 'expense'),
    ('Subskrypcje', 'expense'),
    ('Inne', 'expense'),
    ('Wynagrodzenie', 'income'),
    ('Inne przychody', 'income'),
    ('Przelew wewnętrzny', 'transfer'),
]


def create_starter_categories(user_token, commit=True):
    """Zaklada nowemu uzytkownikowi komplet kategorii startowych.

    Bez tego swiezo zarejestrowana osoba widzi pusta aplikacje i nie moze dodac
    ani jednej transakcji (transakcja wymaga kategorii, a jedyna globalna to
    techniczne "Uzgadnianie salda").

    Kategorie sa PRYWATNE (user_token wypelniony), nie globalne — dzieki temu
    kazdy moze skasowac te, ktorych nie uzywa, nie ruszajac cudzych.

    commit=False pozwala wolajacemu (rejestracja) domknac utworzenie uzytkownika
    i jego kategorii jednym commitem.
    """
    utworzone = [
        Category(name=name, type=cat_type, user_token=user_token)
        for name, cat_type in STARTER_CATEGORIES
    ]
    db.session.add_all(utworzone)
    if commit:
        db.session.commit()
    return utworzone


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
