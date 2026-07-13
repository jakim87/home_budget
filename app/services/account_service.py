from app import db
from app.models import Account
from decimal import Decimal
from sqlalchemy import func

def create_account(user_token, data):
    try:
        raw_num = data.get('account_number') or ''
        is_default = data.get('is_default', False)
        max_order = db.session.query(func.max(Account.sort_order)).filter_by(user_token=user_token).scalar()
        new_acc = Account(
            name=data['name'],
            bank_name=data.get('bank_name'),
            account_number=raw_num.replace(' ', '') or None,
            balance=Decimal('0'),
            user_token=user_token,
            owner=data.get('owner') or None,
            co_owner=data.get('co_owner') or None,
            sort_order=(max_order or 0) + 1,
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
        if not acc:
            raise ValueError('Nie znaleziono konta lub brak uprawnień.')
        acc.is_active = False
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def reorder_accounts(user_token, ordered_ids):
    """Zapisuje kolejność wyświetlania kont wg listy ID podanej przez użytkownika (tylko UI, bez wpływu na logikę)."""
    try:
        accounts = db.session.query(Account).filter(
            Account.user_token == user_token,
            Account.id.in_(ordered_ids)
        ).all()
        accounts_by_id = {a.id: a for a in accounts}
        if len(accounts_by_id) != len(ordered_ids):
            raise ValueError('Jedno lub więcej kont nie istnieje lub nie należy do użytkownika.')
        for position, acc_id in enumerate(ordered_ids):
            accounts_by_id[acc_id].sort_order = position
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))
