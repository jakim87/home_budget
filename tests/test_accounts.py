import pytest
from decimal import Decimal
from app import db
from app.models import User, Account
from sqlalchemy.exc import IntegrityError
from app.services.account_service import create_account, reorder_accounts

def test_create_account_success(app):
    # Setup
    user = User(username="testuser", email="test@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    # Action
    account = Account(name="Konto Osobiste", bank_name="mBank", balance=Decimal("500.00"), user_token=user.token)
    db.session.add(account)
    db.session.commit()

    # Assert
    assert account.id is not None
    assert account.name == "Konto Osobiste"
    assert account.bank_name == "mBank"
    assert account.balance == Decimal("500.00")

def test_create_account_missing_bank_name_raises_error(app):
    # Setup
    user = User(username="testuser2", email="test2@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    # Action & Assert
    account = Account(name="Błędne Konto", user_token=user.token)
    db.session.add(account)

    with pytest.raises(IntegrityError):
        db.session.commit()

def test_new_account_gets_sort_order_at_end(app):
    user = User(username="testuser3", email="test3@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    acc1 = create_account(user.token, {'name': 'Konto A', 'bank_name': 'mBank'})
    acc2 = create_account(user.token, {'name': 'Konto B', 'bank_name': 'mBank'})

    assert acc2.sort_order > acc1.sort_order

def test_reorder_accounts_updates_sort_order(app):
    user = User(username="testuser4", email="test4@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    acc1 = create_account(user.token, {'name': 'Konto A', 'bank_name': 'mBank'})
    acc2 = create_account(user.token, {'name': 'Konto B', 'bank_name': 'mBank'})
    acc3 = create_account(user.token, {'name': 'Konto C', 'bank_name': 'mBank'})

    reorder_accounts(user.token, [acc3.id, acc1.id, acc2.id])

    ordered = db.session.query(Account).filter_by(user_token=user.token).order_by(Account.sort_order).all()
    assert [a.id for a in ordered] == [acc3.id, acc1.id, acc2.id]

def test_reorder_accounts_rejects_foreign_account_id(app):
    owner = User(username="owner", email="owner@test.com", password_hash="hash")
    intruder = User(username="intruder", email="intruder@test.com", password_hash="hash")
    db.session.add_all([owner, intruder])
    db.session.commit()

    own_acc = create_account(owner.token, {'name': 'Moje konto', 'bank_name': 'mBank'})
    foreign_acc = create_account(intruder.token, {'name': 'Cudze konto', 'bank_name': 'mBank'})

    with pytest.raises(ValueError):
        reorder_accounts(owner.token, [own_acc.id, foreign_acc.id])
