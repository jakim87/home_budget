from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import User, Account, Category, Transaction
from app.services.budget_service import create_transaction, reconcile_account_balance
from app import db

def test_reconcile_balance_with_positive_difference(app):
    """
    Testuje, czy uzgadnianie salda poprawnie tworzy transakcję dodatnią,
    gdy nowe saldo jest wyższe od bieżącego.
    """
    with app.app_context():
        # 1. Arrange
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("1000.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        # 2. Act
        new_balance = Decimal("1150.50")
        reconciliation_tx = reconcile_account_balance(user.token, account.id, new_balance)

        # 3. Assert
        assert reconciliation_tx is not None
        assert reconciliation_tx.amount == Decimal("150.50")
        assert reconciliation_tx.title == "Uzgadnianie salda"

        updated_account = db.session.get(Account, account.id)
        assert updated_account.balance == new_balance

        category = db.session.get(Category, reconciliation_tx.category_id)
        assert category.name == "Uzgadnianie salda"
        assert category.is_system_category is True

def test_reconcile_balance_with_negative_difference(app):
    """
    Testuje, czy uzgadnianie salda poprawnie tworzy transakcję ujemną,
    gdy nowe saldo jest niższe od bieżącego.
    """
    with app.app_context():
        # 1. Arrange
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("1000.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        # 2. Act
        new_balance = Decimal("950.25")
        reconciliation_tx = reconcile_account_balance(user.token, account.id, new_balance)

        # 3. Assert
        assert reconciliation_tx is not None
        assert reconciliation_tx.amount == Decimal("-49.75")

        updated_account = db.session.get(Account, account.id)
        assert updated_account.balance == new_balance

def test_reconcile_balance_with_no_difference(app):
    """
    Testuje, czy funkcja nie tworzy transakcji, gdy saldo jest zgodne.
    """
    with app.app_context():
        # 1. Arrange
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("1000.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        # 2. Act
        new_balance = Decimal("1000.00")
        reconciliation_tx = reconcile_account_balance(user.token, account.id, new_balance)

        # 3. Assert
        assert reconciliation_tx is None

        updated_account = db.session.get(Account, account.id)
        assert updated_account.balance == Decimal("1000.00")

def test_reconcile_creates_system_category_if_not_exists(app):
    """
    Testuje, czy kategoria systemowa jest tworzona, jeśli nie istnieje w bazie.
    """
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("100.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        reconcile_account_balance(user.token, account.id, Decimal("120.00"))

        category = db.session.query(Category).filter_by(name="Uzgadnianie salda").one()
        assert category is not None
        assert category.is_system_category is True


def _user_z_kontem(saldo="1000.00"):
    """Świeży użytkownik z jednym kontem o zadanym saldzie."""
    user = User(username="testuser", email="test@test.com", password_hash="hash")
    account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal(saldo), user=user)
    db.session.add_all([user, account])
    db.session.commit()
    return user, account


def test_reconcile_wstecz_ignoruje_pozniejsze_transakcje(app):
    """Rdzeń uzgodnienia wstecz: różnicę liczymy wobec salda NA TEN DZIEŃ, nie
    wobec bieżącego. Bez tego korekta wchłonęłaby każdą późniejszą operację."""
    with app.app_context():
        user, account = _user_z_kontem("1000.00")
        # Po 31 lipca wpływa 200 zł -> saldo bieżące 1200, ale na 31 lipca było 1000.
        create_transaction(
            user_token=user.token, account_id=account.id, amount=Decimal("200.00"),
            title="Wpłata sierpniowa", transaction_date=date(2025, 8, 10),
        )
        assert db.session.get(Account, account.id).balance == Decimal("1200.00")

        # Użytkownik twierdzi, że na koniec lipca miał 1050 -> brakuje 50, nie 150.
        tx = reconcile_account_balance(
            user.token, account.id, Decimal("1050.00"), transaction_date=date(2025, 7, 31)
        )

        assert tx.amount == Decimal("50.00")
        assert tx.date == date(2025, 7, 31)
        # Korekta przesuwa też saldo bieżące — skoro w lipcu było o 50 więcej,
        # to dziś również jest o 50 więcej.
        assert db.session.get(Account, account.id).balance == Decimal("1250.00")


def test_reconcile_wstecz_liczy_saldo_na_koniec_dnia(app):
    """Operacja z tego samego dnia co uzgodnienie wchodzi do salda odniesienia —
    uzgadniamy stan na KONIEC dnia, tak jak podaje go wyciąg bankowy."""
    with app.app_context():
        user, account = _user_z_kontem("1000.00")
        create_transaction(
            user_token=user.token, account_id=account.id, amount=Decimal("-30.00"),
            title="Zakupy tego samego dnia", transaction_date=date(2025, 7, 31),
        )

        # Saldo na koniec 31 lipca = 970. Wpisanie 970 nie wymaga korekty.
        assert reconcile_account_balance(
            user.token, account.id, Decimal("970.00"), transaction_date=date(2025, 7, 31)
        ) is None
        assert db.session.get(Account, account.id).balance == Decimal("970.00")


def test_reconcile_odrzuca_date_z_przyszlosci(app):
    """Nie da się uzgodnić salda, którego jeszcze nie było."""
    with app.app_context():
        user, account = _user_z_kontem("1000.00")
        with pytest.raises(ValueError, match="przyszłości"):
            reconcile_account_balance(
                user.token, account.id, Decimal("1500.00"),
                transaction_date=date.today() + timedelta(days=1),
            )
        assert db.session.get(Account, account.id).balance == Decimal("1000.00")


def test_api_reconcile_przekazuje_date_do_serwisu(logged_in_client, test_user_token):
    """Trasa HTTP musi faktycznie przekazać datę — bez tego formularz wyglądałby
    poprawnie, a korekta i tak lądowałaby z dzisiejszą datą i złą kwotą."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user_token)
    db.session.add(account)
    db.session.commit()
    create_transaction(
        user_token=test_user_token, account_id=account.id, amount=Decimal("200.00"),
        title="Późniejszy wpływ", transaction_date=date(2025, 8, 10),
    )

    resp = logged_in_client.post(
        f'/api/accounts/{account.id}/reconcile',
        json={'new_balance': '1050.00', 'date': '2025-07-31'},
    )

    assert resp.status_code == 200
    tx = db.session.query(Transaction).filter_by(title="Uzgadnianie salda").one()
    assert tx.date == date(2025, 7, 31)
    assert tx.amount == Decimal("50.00")


def test_api_reconcile_odrzuca_bledny_format_daty(logged_in_client, test_user_token):
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user_token)
    db.session.add(account)
    db.session.commit()

    resp = logged_in_client.post(
        f'/api/accounts/{account.id}/reconcile',
        json={'new_balance': '1050.00', 'date': '31.07.2025'},
    )

    assert resp.status_code == 400
    assert db.session.query(Transaction).count() == 0
