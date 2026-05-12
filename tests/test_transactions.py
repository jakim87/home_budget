import pytest
from app import db
from app.models import User, Account, Transaction
from app.services.budget_service import create_transaction
from datetime import date

def test_adding_transaction_updates_account_balance(app):
    # 1. Przygotowanie danych (Setup)
    user = User(username="testuser", email="test@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    account = Account(name="Portfel", bank_name="Gotówka", balance=1000.00, user_id=user.id)
    db.session.add(account)
    db.session.commit()

    # 2. Akcja (Action)
    create_transaction(
        user_id=user.id,
        account_id=account.id,
        amount=-200.00,
        title="Zakupy",
        transaction_date=date.today()
    )

    # 3. Weryfikacja (Assert)
    # Odświeżamy obiekt konta z bazy, aby mieć pewność, że zmiany się zapisały
    db.session.refresh(account)
    assert float(account.balance) == 800.00