from sqlalchemy.orm import joinedload, selectinload

from app import db
from app.models import Account, Contractor, Transaction, TransactionSplit
from app.services.category_service import list_active as list_active_categories


def build_init_payload(user_token: str) -> dict:
    """Komplet danych startowych frontu: transakcje, słowniki i konta użytkownika.

    Front trzyma cały stan w pamięci i przelicza go po swojej stronie, więc to
    jedyne zapytanie odczytowe w aplikacji — stąd eager loading relacji transakcji
    (bez niego lista kilku tysięcy pozycji robi N+1).
    """
    categories = list_active_categories(user_token)
    category_names = {c.id: c.name for c in categories}

    contractors = (
        db.session.query(Contractor)
        .filter_by(user_token=user_token, is_active=True)
        .order_by(Contractor.name)
        .all()
    )

    accounts = (
        db.session.query(Account)
        .filter_by(user_token=user_token, is_active=True)
        .order_by(Account.sort_order, Account.name)
        .all()
    )

    # Konta nieaktywne (zamknięte/archiwalne) MAJĄCE powiązane transakcje —
    # spłacone kredyty, zamknięte rachunki z upadłych banków itp. Puste konta
    # nieaktywne (techniczne/testowe bez historii) pomijamy — lista ma pokazywać
    # konta, z którymi wiążą się transakcje. Historia Majątku i tak liczy się
    # z transakcji, więc te konta pozostają w wykresie.
    accounts_with_tx = {
        aid for (aid,) in db.session.query(Transaction.account_id)
        .filter(Transaction.user_token == user_token).distinct().all()
    }
    inactive_accounts = (
        db.session.query(Account)
        .filter_by(user_token=user_token, is_active=False)
        .order_by(Account.name)
        .all()
    )

    transactions = (
        db.session.query(Transaction)
        .options(
            joinedload(Transaction.category),
            joinedload(Transaction.contractor_details),
            selectinload(Transaction.splits).joinedload(TransactionSplit.category),
        )
        .filter(Transaction.user_token == user_token)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .all()
    )

    return {
        'transactions': [_transaction_dict(tx) for tx in transactions],
        'categories': [
            {'id': c.id, 'name': c.name, 'type': c.type, 'is_system_category': c.is_system_category}
            for c in categories
        ],
        'contractors': [
            {
                'id': c.id, 'name': c.name, 'rules': c.mapping_rules,
                'default_category_id': c.default_category_id,
                'default_category_name': category_names.get(c.default_category_id, ''),
            }
            for c in contractors
        ],
        'accounts': [_account_dict(a) for a in accounts],
        'inactive_accounts': [
            _account_dict(a, full=False) for a in inactive_accounts if a.id in accounts_with_tx
        ],
    }


def _account_dict(a: Account, full: bool = True) -> dict:
    data = {
        'id': a.id, 'name': a.name, 'bank_name': a.bank_name,
        'account_number': a.account_number, 'balance': float(a.balance),
        'account_type': a.account_type,
    }
    if full:
        data.update({
            'is_default': a.is_default,
            'owner': a.owner,
            'co_owner': a.co_owner,
            'created_at': a.created_at.strftime('%Y-%m-%d') if a.created_at else None,
        })
    return data


def _transaction_dict(tx: Transaction) -> dict:
    return {
        'id': tx.id,
        'desc': tx.title,
        'amount': float(tx.amount),
        'date': tx.date.strftime('%Y-%m-%d') if tx.date else '',
        'category': tx.category.name if tx.category else 'Inne',
        'contractor_id': tx.contractor_id,
        'contractor_name': tx.contractor_details.name if tx.contractor_details else tx.contractor,
        'account_id': tx.account_id,
        'splits': [
            {
                'id': s.id,
                'amount': float(s.amount),
                'desc': s.desc or '',
                'category': s.category.name if s.category else 'Inne',
            }
            for s in tx.splits
        ],
        'comment': tx.comment or '',
        # Druga noga przelewu wewnętrznego (lustro) — front używa jej, by ostrzec
        # przy usuwaniu, że znikną OBIE transakcje, i wskazać które.
        'linked_transaction_id': tx.linked_transaction_id,
        # Przelew wewnętrzny bez powiązanej drugiej nogi — czeka na wyciąg
        # drugiego konta ("do zmapowania"). Front pokazuje przy nim znacznik.
        'transfer_unmatched': bool(
            tx.category and tx.category.type == 'transfer' and tx.linked_transaction_id is None
        ),
    }
