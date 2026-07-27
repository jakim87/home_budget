from app import db
from app.models import Transaction, TransactionArchive, Category, TransactionSplit, Account
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json

def _archive_and_remove_leg(leg: Transaction) -> None:
    """Cofa wpływ jednej transakcji na saldo konta, zapisuje ślad audytowy i usuwa
    ją z sesji. NIE commituje — wołający domyka wszystko jednym commitem."""
    account = db.session.get(Account, leg.account_id)
    if account:
        balance = account.balance if isinstance(account.balance, Decimal) else Decimal(str(account.balance))
        amount = leg.amount if isinstance(leg.amount, Decimal) else Decimal(str(leg.amount))
        account.balance = balance - amount

    # Pełny ślad audytowy — łącznie z podziałami, które kaskadowo znikają razem z transakcją.
    splits_payload = [
        {'amount': str(s.amount), 'desc': s.desc, 'category_id': s.category_id}
        for s in leg.splits
    ]
    db.session.add(TransactionArchive(
        original_id=leg.id,
        title=leg.title,
        amount=leg.amount,
        date=leg.date,
        account_id=leg.account_id,
        category_id=leg.category_id,
        contractor_id=leg.contractor_id,
        user_token=leg.user_token,
        comment=leg.comment,
        contractor_raw=leg.contractor,
        splits_json=json.dumps(splits_payload) if splits_payload else None
    ))
    db.session.delete(leg)


def archive_and_delete_transaction(user_token, tx_id):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_token=user_token).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje lub brak uprawnień.')

        # Przelew wewnętrzny to DWIE powiązane nogi. Usunięcie jednej bez drugiej
        # rozjeżdża Net Worth (outflow znika, inflow zostaje). Usuwamy obie nogi
        # atomowo — jeden przelew = jedna logiczna operacja.
        legs = [tx]
        if tx.linked_transaction_id:
            mirror = db.session.query(Transaction).filter_by(
                id=tx.linked_transaction_id, user_token=user_token
            ).first()
            if mirror:
                legs.append(mirror)

        # Rozwiąż wzajemne powiązanie przed usunięciem, żeby FK (ondelete=SET NULL)
        # nie próbował aktualizować wiersza już usuwanego w tym samym flushu.
        for leg in legs:
            leg.linked_transaction_id = None
        db.session.flush()

        for leg in legs:
            _archive_and_remove_leg(leg)
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

            mirror = None
            if tx.linked_transaction_id:
                mirror = db.session.query(Transaction).filter_by(
                    id=tx.linked_transaction_id, user_token=user_token
                ).first()

            if mirror:
                # Noga przelewu wewnętrznego: zachowaj KIERUNEK znaku każdej nogi
                # (edytowana zachowuje swój, lustro dostaje przeciwny) i skoryguj
                # oba salda, inaczej rozjazd Net Worth o różnicę kwoty.
                magnitude = abs(new_amount)
                tx_new = -magnitude if old_amount < 0 else magnitude
                mirror_old = mirror.amount if isinstance(mirror.amount, Decimal) else Decimal(str(mirror.amount))
                mirror_new = -tx_new

                if account:
                    balance = account.balance if isinstance(account.balance, Decimal) else Decimal(str(account.balance))
                    account.balance = balance + (tx_new - old_amount)
                mirror_account = db.session.get(Account, mirror.account_id)
                if mirror_account:
                    m_bal = mirror_account.balance if isinstance(mirror_account.balance, Decimal) else Decimal(str(mirror_account.balance))
                    mirror_account.balance = m_bal + (mirror_new - mirror_old)
                tx.amount = tx_new
                mirror.amount = mirror_new
            else:
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
