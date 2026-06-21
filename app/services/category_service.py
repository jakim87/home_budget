from app import db
from app.models import Category

def create_category(data):
    try:
        if db.session.query(Category).filter_by(name=data['name'], is_active=True).first():
            raise ValueError('Kategoria o tej nazwie już istnieje')
            
        new_cat = Category(name=data['name'], type=data['type'])
        db.session.add(new_cat)
        db.session.commit()
        return new_cat
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def soft_delete_category(cat_name):
    try:
        category = db.session.query(Category).filter_by(name=cat_name).first()
        if category:
            category.is_active = False
            db.session.commit()
    except Exception:
        db.session.rollback()