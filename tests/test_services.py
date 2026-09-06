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


def _saldo_na_dzien(account, dzien):
    """Saldo, jakie system pokazuje na koniec podanego dnia — liczone tak samo
    jak w aplikacji: bieżące saldo minus wszystko zaksięgowane po tym dniu."""
    po = db.session.query(Transaction).filter(
        Transaction.account_id == account.id, Transaction.date > dzien
    ).all()
    return Decimal(account.balance) - sum((t.amount for t in po), Decimal("0"))


def _konto_z_uzgodnieniem_sierpniowym(user_token):
    """Konto, na którym 950 zł wpłynęło 1 lipca, a uzgodnienie z 31 sierpnia
    podniosło stan do 1000 zł (korekta +50). Punkt wyjścia dla testów łańcucha."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("0.00"), user_token=user_token)
    db.session.add(account)
    db.session.commit()
    create_transaction(
        user_token=user_token, account_id=account.id, amount=Decimal("950.00"),
        title="Wpływ", transaction_date=date(2025, 7, 1),
    )
    sierpniowe = reconcile_account_balance(
        user_token, account.id, Decimal("1000.00"), transaction_date=date(2025, 8, 31)
    )
    assert sierpniowe.amount == Decimal("50.00")
    return account, sierpniowe


def test_reconcile_wstecz_koryguje_nastepne_uzgodnienie(app, test_user_token):
    """Uzgodnienie przed istniejącym nie kasuje go, tylko zdejmuje z jego korekty
    tę samą różnicę — obie daty pokazują potem kwoty wpisane przez użytkownika,
    a saldo bieżące zostaje bez zmian."""
    with app.app_context():
        account, sierpniowe = _konto_z_uzgodnieniem_sierpniowym(test_user_token)

        # Na 31 lipca system pokazuje 950; użytkownik twierdzi, że było 850.
        lipcowe = reconcile_account_balance(
            test_user_token, account.id, Decimal("850.00"), transaction_date=date(2025, 7, 31)
        )

        assert lipcowe.amount == Decimal("-100.00")
        # Korekta sierpniowa rośnie o tę samą różnicę (50 − (−100) = 150).
        assert sierpniowe.amount == Decimal("150.00")
        # Saldo bieżące nietknięte — zmiana dotyczyła przeszłości, nie stanu dziś.
        assert Decimal(account.balance) == Decimal("1000.00")
        # Oba pomiary nadal prawdziwe.
        assert _saldo_na_dzien(account, date(2025, 7, 31)) == Decimal("850.00")
        assert _saldo_na_dzien(account, date(2025, 8, 31)) == Decimal("1000.00")


def test_reconcile_wstecz_usuwa_nastepne_gdy_zeruje_jego_korekte(app, test_user_token):
    """Gdy poprawka zjada całą korektę następnego uzgodnienia, zostaje po nim
    transakcja na 0.00 — czyli śmieć w historii. Kasujemy ją."""
    with app.app_context():
        account, sierpniowe = _konto_z_uzgodnieniem_sierpniowym(test_user_token)
        id_sierpniowego = sierpniowe.id

        # Brakujące 50 zł pochodziło sprzed lipca — korekta sierpniowa staje się zbędna.
        reconcile_account_balance(
            test_user_token, account.id, Decimal("1000.00"), transaction_date=date(2025, 7, 31)
        )

        assert db.session.get(Transaction, id_sierpniowego) is None
        assert Decimal(account.balance) == Decimal("1000.00")
        assert _saldo_na_dzien(account, date(2025, 7, 31)) == Decimal("1000.00")
        assert _saldo_na_dzien(account, date(2025, 8, 31)) == Decimal("1000.00")


def test_reconcile_wstecz_rusza_tylko_najblizsze_uzgodnienie(app, test_user_token):
    """Dalsze uzgodnienia liczą korektę względem poprawionego sąsiada, więc
    poprawka propaguje się sama — nie wolno ich ruszać drugi raz."""
    with app.app_context():
        account, sierpniowe = _konto_z_uzgodnieniem_sierpniowym(test_user_token)
        wrzesniowe = reconcile_account_balance(
            test_user_token, account.id, Decimal("1200.00"), transaction_date=date(2025, 9, 30)
        )
        kwota_wrzesniowa = wrzesniowe.amount

        reconcile_account_balance(
            test_user_token, account.id, Decimal("850.00"), transaction_date=date(2025, 7, 31)
        )

        assert sierpniowe.amount == Decimal("150.00")   # najbliższe — skorygowane
        assert wrzesniowe.amount == kwota_wrzesniowa    # dalsze — nietknięte
        assert _saldo_na_dzien(account, date(2025, 9, 30)) == Decimal("1200.00")


def test_reconcile_na_dzis_nie_rusza_wczesniejszych_uzgodnien(app, test_user_token):
    """Uzgodnienie „na teraz" nie ma po sobie żadnego następnego — historia
    zostaje nietknięta."""
    with app.app_context():
        account, sierpniowe = _konto_z_uzgodnieniem_sierpniowym(test_user_token)

        reconcile_account_balance(test_user_token, account.id, Decimal("1300.00"))

        assert sierpniowe.amount == Decimal("50.00")
        assert Decimal(account.balance) == Decimal("1300.00")
