import pytest
from datetime import date
from app import db
from sqlalchemy.exc import IntegrityError
# Zakładamy, że Account i User zostały zdefiniowane już wcześniej, jak wynika z test_accounts.py
from app.models import User, Account, Category, Transaction

def test_create_category(app):
    # Action
    category = Category(name="Jedzenie", type="expense")
    db.session.add(category)
    db.session.commit()

    # Assert
    assert category.id is not None
    assert category.name == "Jedzenie"
    assert category.type == "expense"

def test_create_transaction(app):
    # Setup - potrzebujemy konta i kategorii by utworzyć transakcję
    user = User(username="tx_user", email="tx@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()
    
    account = Account(name="Konto Bieżące", bank_name="ING", balance=1500.0, user_id=user.id)
    category = Category(name="Wypłata", type="income")
    db.session.add_all([account, category])
    db.session.commit()

    # Action
    tx = Transaction(
        date=date(2023, 10, 1),
        title="Premia",
        amount=500.0,
        category_id=category.id,
        account_id=account.id,
        user_id=user.id
    )
    db.session.add(tx)
    db.session.commit()

    # Assert
    assert tx.id is not None
    assert tx.amount == 500.0