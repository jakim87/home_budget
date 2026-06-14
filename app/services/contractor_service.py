from app import db
from app.models import Contractor, Category

def create_contractor(user_token, data):
    try:
        category = db.session.query(Category).filter_by(name=data.get('category')).first() if data.get('category') else None
        new_cont = Contractor(
            name=data['name'],
            mapping_rules=data.get('rules'),
            default_category_id=category.id if category else None,
            user_token=user_token
        )
        db.session.add(new_cont)
        db.session.commit()
        return new_cont, category
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def update_contractor(user_token, c_id, data):
    try:
        cont = db.session.query(Contractor).filter_by(id=c_id, user_token=user_token).first()
        if not cont:
            raise ValueError('Nie znaleziono kontrahenta.')
        cont.name = data.get('name', cont.name)
        cont.mapping_rules = data.get('rules', cont.mapping_rules)

        cat_name = data.get('category')
        category = db.session.query(Category).filter_by(name=cat_name).first() if cat_name else None
        cont.default_category_id = category.id if category else None

        db.session.commit()
        return cont, category
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def soft_delete_contractor(user_token, c_id):
    try:
        cont = db.session.query(Contractor).filter_by(id=c_id, user_token=user_token).first()
        if cont:
            cont.is_active = False
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))
