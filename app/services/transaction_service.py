from app import db
from app.models import Transaction, TransactionArchive, Category, TransactionSplit, Account
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json

def archive_and_delete_transaction(user_token, tx_id):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_token=user_token).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje lub brak uprawnień.')

        account = db.session.get(Account, tx.account_id)
        if account:
            balance = Decimal(str(account.balance)) if not isinstance(account.balance, Decimal) else account.balance
            amount = Decimal(str(tx.amount)) if not isinstance(tx.amount, Decimal) else tx.amount
            account.balance = balance - amount

        # Pełny ślad audytowy — łącznie z podziałami, które kaskadowo znikają razem z transakcją.
        splits_payload = [
            {'amount': str(s.amount), 'desc': s.desc, 'category_id': s.category_id}
            for s in tx.splits
        ]

        archive_tx = TransactionArchive(
            original_id=tx.id,
            title=tx.title,
            amount=tx.amount,
            date=tx.date,
            account_id=tx.account_id,
            category_id=tx.category_id,
            contractor_id=tx.contractor_id,
            user_token=tx.user_token,
            comment=tx.comment,
            contractor_raw=tx.contractor,
            splits_json=json.dumps(splits_payload) if splits_payload else None
        )
        db.session.add(archive_tx)
        db.session.delete(tx)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def update_transaction(user_token, tx_id, data):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_token=user_token).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje.')

        if 'title' in data or 'desc' in data:
            tx.title = data.get('title') or data.get('desc', tx.title)
        if 'amount' in data:
            # Zmiana kwoty musi skorygować saldo konta o różnicę, inaczej saldo
            # trwale rozjeżdża się z sumą transakcji.
            new_amount = Decimal(str(data['amount']))
            old_amount = tx.amount if isinstance(tx.amount, Decimal) else Decimal(str(tx.amount))
            account = db.session.get(Account, tx.account_id)
            if account:
                balance = account.balance if isinstance(account.balance, Decimal) else Decimal(str(account.balance))
                account.balance = balance + (new_amount - old_amount)
            tx.amount = new_amount
        if 'date' in data:
            tx.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'category' in data:
            cat = db.session.query(Category).filter_by(name=data['category'], is_active=True).first()
            tx.category_id = cat.id if cat else tx.category_id
        if 'contractor_id' in data:
            cid = data.get('contractor_id')
            tx.contractor_id = int(cid) if cid else None
        if 'comment' in data:
            tx.comment = data.get('comment') or None

        if 'splits' in data:
            tx.splits.clear()
            for split_data in data['splits']:
                cat = db.session.query(Category).filter_by(name=split_data.get('category'), is_active=True).first()
                tx.splits.append(TransactionSplit(
                    amount=Decimal(str(split_data.get('amount', 0))),
                    desc=split_data.get('desc', ''),
                    category_id=cat.id if cat else None
                ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))
