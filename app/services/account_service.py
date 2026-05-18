from app import db
from app.models import Account

def create_account(user_id, data):
    try:
        new_acc = Account(
            name=data['name'],
            bank_name=data.get('bank_name'),
            account_number=data.get('account_number'),
            balance=0.0,
            user_id=user_id
        )
        db.session.add(new_acc)
        db.session.commit()
        return new_acc
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Błąd tworzenia konta: {str(e)}")

def update_account(user_id, a_id, data):
    try:
        acc = db.session.query(Account).filter_by(id=a_id, user_id=user_id).first()
        if not acc:
            raise ValueError('Nie znaleziono konta.')
        acc.name = data.get('name', acc.name)
        acc.bank_name = data.get('bank_name', acc.bank_name)
        acc.account_number = data.get('account_number', acc.account_number)
        db.session.commit()
        return acc
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def soft_delete_account(user_id, a_id):
    try:
        acc = db.session.query(Account).filter_by(id=a_id, user_id=user_id).first()
        if acc:
            acc.is_active = False
            db.session.commit()
    except Exception:
        db.session.rollback()