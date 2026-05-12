import pytest
from app import db
from app.models import User, Account
from sqlalchemy.exc import IntegrityError

def test_create_account_success(app):
    # Setup
    user = User(username="testuser", email="test@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    # Action
    account = Account(name="Konto Osobiste", bank_name="mBank", balance=500.0, user_id=user.id)
    db.session.add(account)
    db.session.commit()

    # Assert
    assert account.id is not None
    assert account.name == "Konto Osobiste"
    assert account.bank_name == "mBank"
    assert float(account.balance) == 500.0

def test_create_account_missing_bank_name_raises_error(app):
    # Setup
    user = User(username="testuser2", email="test2@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    # Action & Assert
    # bank_name jest wymagane (Mapped[str] bez Optional), 
    # więc próba commitu bez tej wartości rzuci IntegrityError
    account = Account(name="Błędne Konto", user_id=user.id)
    db.session.add(account)
    
    with pytest.raises(IntegrityError):
        db.session.commit()