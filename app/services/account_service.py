from app import db
from app.models import Account
from decimal import Decimal

def create_account(user_token, data):
    try:
        raw_num = data.get('account_number') or ''
        is_default = data.get('is_default', False)
        new_acc = Account(
            name=data['name'],
            bank_name=data.get('bank_name'),
            account_number=raw_num.replace(' ', '') or None,
            balance=Decimal('0'),
            user_token=user_token,
            owner=data.get('owner') or None,
            co_owner=data.get('co_owner') or None,
        )
        db.session.add(new_acc)
        db.session.flush()
        if is_default:
            db.session.query(Account).filter(
                Account.user_token == user_token,
                Account.id != new_acc.id
            ).update({'is_default': False})
            new_acc.is_default = True
        db.session.commit()
        return new_acc
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Błąd tworzenia konta: {str(e)}")

def update_account(user_token, a_id, data):
    try:
        acc = db.session.query(Account).filter_by(id=a_id, user_token=user_token).first()
        if not acc:
            raise ValueError('Nie znaleziono konta.')
        acc.name = data.get('name', acc.name)
        acc.bank_name = data.get('bank_name', acc.bank_name)
        raw_num = data.get('account_number')
        if raw_num is not None:
            acc.account_number = raw_num.replace(' ', '') or None
        if 'owner' in data:
            acc.owner = data['owner'] or None
        if 'co_owner' in data:
            acc.co_owner = data['co_owner'] or None
        if data.get('is_default'):
            db.session.query(Account).filter(
                Account.user_token == user_token,
                Account.id != acc.id
            ).update({'is_default': False})
            acc.is_default = True
        db.session.commit()
        return acc
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def soft_delete_account(user_token, a_id):
    try:
        acc = db.session.query(Account).filter_by(id=a_id, user_token=user_token).first()
        if acc:
            acc.is_active = False
            db.session.commit()
    except Exception:
        db.session.rollback()
