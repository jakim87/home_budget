from app import db
from app.models import Transaction, Account
from datetime import date
from typing import Optional
from decimal import Decimal

def create_transaction(
    user_id: int,
    account_id: int,
    amount: float,
    title: str,
    transaction_date: date,
    category_id: Optional[int] = None,
    contractor: Optional[str] = None
) -> Transaction:
    """
    Tworzy nową transakcję i automatycznie aktualizuje saldo powiązanego konta.
    """
    account = db.session.get(Account, account_id)
    if not account:
        raise ValueError(f"Konto o ID {account_id} nie istnieje.")

    new_transaction = Transaction(
        user_id=user_id,
        account_id=account_id,
        amount=amount,
        title=title,
        date=transaction_date,
        category_id=category_id,
        contractor=contractor
    )

    # Aktualizacja salda konta (obsługa Decimal dla precyzji finansowej)
    account.balance = Decimal(str(account.balance)) + Decimal(str(amount))
    
    db.session.add(new_transaction)
    db.session.commit()
    
    return new_transaction