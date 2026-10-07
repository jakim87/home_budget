from app import db
from app.models import Account, Contractor, Category
from app.services.category_service import find_by_name as find_category_by_name


def find_owned(user_token, contractor_id):
    """Kontrahent o danym ID należący do użytkownika, albo None.

    Celowo BEZ filtra is_active — transakcja z historycznym, wyłączonym kontrahentem
    jest dozwolona (patrz budget_service.create_transaction). Jedyne miejsce, w którym
    kontrahent jest rozwiązywany po ID, żeby nie dało się podpiąć cudzego (patrz #127).
    """
    if not contractor_id:
        return None
    return db.session.query(Contractor).filter_by(id=contractor_id, user_token=user_token).first()


def _own_account_contractor(user_token, name):
    """(konto, istniejący kontrahent) dla nazwy „Moje konto: X”; (None, None) dla każdej innej.

    Kontrahent przelewu wewnętrznego jest jeden na konto i niesie linked_account_id —
    parowanie nóg szuka po nim. Drugi o tej samej nazwie, bez powiązania, zbierałby
    przelewy, których nic nigdy nie sparuje (#215).
    """
    prefix = "Moje konto: "
    if not name.startswith(prefix):
        return None, None
    konta = db.session.query(Account).filter_by(
        user_token=user_token, name=name[len(prefix):], is_active=True
    ).all()
    if len(konta) != 1:
        return None, None
    cont = db.session.query(Contractor).filter_by(
        user_token=user_token, linked_account_id=konta[0].id
    ).first() or db.session.query(Contractor).filter_by(
        user_token=user_token, name=name, is_active=True
    ).first()
    return konta[0], cont


def create_contractor(user_token, data):
    try:
        category = find_category_by_name(user_token, data.get('category'))
        konto, istniejacy = _own_account_contractor(user_token, data['name'])
        if istniejacy:
            istniejacy.is_active = True
            istniejacy.linked_account_id = konto.id
            db.session.commit()
            return istniejacy, (db.session.get(Category, istniejacy.default_category_id)
                                if istniejacy.default_category_id else None)
        new_cont = Contractor(
            name=data['name'],
            mapping_rules=data.get('rules'),
            default_category_id=category.id if category else None,
            user_token=user_token,
            linked_account_id=konto.id if konto else None
        )
        db.session.add(new_cont)
        db.session.commit()
        return new_cont, category
    except Exception:
        db.session.rollback()
        raise

def update_contractor(user_token, c_id, data):
    try:
        cont = db.session.query(Contractor).filter_by(id=c_id, user_token=user_token).first()
        if not cont:
            raise ValueError('Nie znaleziono kontrahenta.')
        cont.name = data.get('name', cont.name)
        cont.mapping_rules = data.get('rules', cont.mapping_rules)

        # Kategorię zmieniamy TYLKO gdy klucz jest obecny w żądaniu. Inaczej częściowa
        # edycja (PUT bez pola 'category') cicho kasowałaby domyślną kategorię kontrahenta.
        category = None
        if 'category' in data:
            category = find_category_by_name(user_token, data.get('category'))
            cont.default_category_id = category.id if category else None
        elif cont.default_category_id:
            category = db.session.get(Category, cont.default_category_id)

        db.session.commit()
        return cont, category
    except Exception:
        db.session.rollback()
        raise

def soft_delete_contractor(user_token, c_id):
    try:
        cont = db.session.query(Contractor).filter_by(id=c_id, user_token=user_token).first()
        if not cont:
            raise ValueError('Nie znaleziono kontrahenta lub brak uprawnień.')
        cont.is_active = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
