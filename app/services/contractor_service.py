from app import db
from app.models import Contractor, Category
from app.services.category_service import find_by_name as find_category_by_name

def create_contractor(user_token, data):
    try:
        category = find_category_by_name(user_token, data.get('category'))
        new_cont = Contractor(
            name=data['name'],
            mapping_rules=data.get('rules'),
            default_category_id=category.id if category else None,
            user_token=user_token
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
