"""Typy kont (ROR/KO/Kredyt/Rach. Maklerski/IKZE) i niezmiennik salda Kredytu.

Kredyt to zobowiązanie — saldo musi być <= 0. Niezmiennik jest egzekwowany
centralnie (listener before_flush w models.py), więc łapie każdą ścieżkę zmiany
salda: dodanie/edycję/usunięcie transakcji, lustro przelewu wewnętrznego,
uzgodnienie salda i migrację historii.
"""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import User, ACCOUNT_TYPE_KREDYT
from app.services.account_service import create_account, update_account
from app.services.budget_service import create_transaction, reconcile_account_balance


@pytest.fixture
def user_token(app):
    user = User(username="acctype_user", email="at@test.com", password_hash="a")
    db.session.add(user)
    db.session.commit()
    return user.token


# --- Walidacja nazwy typu -----------------------------------------------------

def test_create_account_with_valid_type(user_token):
    acc = create_account(user_token, {'name': 'ROR', 'bank_name': 'ING', 'account_type': 'ROR'})
    assert acc.account_type == 'ROR'


def test_create_account_empty_type_is_none(user_token):
    acc = create_account(user_token, {'name': 'Bez typu', 'bank_name': 'ING', 'account_type': ''})
    assert acc.account_type is None


def test_create_account_unknown_type_rejected(user_token):
    with pytest.raises(ValueError, match="Nieznany typ konta"):
        create_account(user_token, {'name': 'X', 'bank_name': 'ING', 'account_type': 'Lokata'})


def test_update_account_type(user_token):
    acc = create_account(user_token, {'name': 'Konto', 'bank_name': 'ING'})
    updated = update_account(user_token, acc.id, {'account_type': 'KO'})
    assert updated.account_type == 'KO'


# --- Niezmiennik Kredyt <= 0 --------------------------------------------------

def _kredyt(user_token, balance='0'):
    acc = create_account(user_token, {'name': 'Hipoteka', 'bank_name': 'Pekao', 'account_type': ACCOUNT_TYPE_KREDYT})
    if balance != '0':
        reconcile_account_balance(user_token, acc.id, Decimal(balance))
    return acc


def test_kredyt_allows_negative_balance(user_token):
    acc = _kredyt(user_token)
    reconcile_account_balance(user_token, acc.id, Decimal('-1000.00'))
    db.session.refresh(acc)
    assert acc.balance == Decimal('-1000.00')


def test_kredyt_allows_exactly_zero(user_token):
    """Dojście do 0 = spłata; musi być dozwolone."""
    acc = _kredyt(user_token, balance='-500.00')
    reconcile_account_balance(user_token, acc.id, Decimal('0.00'))
    db.session.refresh(acc)
    assert acc.balance == Decimal('0.00')


def test_kredyt_rejects_positive_via_reconcile(user_token):
    acc = _kredyt(user_token, balance='-500.00')
    with pytest.raises(ValueError, match="Kredyt"):
        reconcile_account_balance(user_token, acc.id, Decimal('100.00'))
    db.session.rollback()


def test_kredyt_rejects_positive_via_transaction(user_token):
    """Transakcja pchająca kredyt powyżej 0 (nadpłata) = błąd danych — odrzucona."""
    acc = _kredyt(user_token, balance='-100.00')
    with pytest.raises(ValueError, match="Kredyt"):
        create_transaction(user_token, acc.id, Decimal('300.00'), title='Nadpłata',
                           transaction_date=date.today())
    db.session.rollback()


def test_kredyt_repayment_toward_zero_allowed(user_token):
    """Wpłata redukująca dług (ku 0), ale nie przekraczająca — dozwolona."""
    acc = _kredyt(user_token, balance='-500.00')
    create_transaction(user_token, acc.id, Decimal('200.00'), title='Rata',
                      transaction_date=date.today())
    db.session.refresh(acc)
    assert acc.balance == Decimal('-300.00')


def test_non_kredyt_account_allows_positive(user_token):
    acc = create_account(user_token, {'name': 'ROR', 'bank_name': 'ING', 'account_type': 'ROR'})
    reconcile_account_balance(user_token, acc.id, Decimal('5000.00'))
    db.session.refresh(acc)
    assert acc.balance == Decimal('5000.00')


def test_changing_type_to_kredyt_with_positive_balance_rejected(user_token):
    """Nie można oznaczyć jako Kredyt konta, które ma dodatnie saldo."""
    acc = create_account(user_token, {'name': 'ROR', 'bank_name': 'ING', 'account_type': 'ROR'})
    reconcile_account_balance(user_token, acc.id, Decimal('1000.00'))
    with pytest.raises(ValueError, match="Kredyt"):
        update_account(user_token, acc.id, {'account_type': ACCOUNT_TYPE_KREDYT})
    db.session.rollback()


# --- Widoczność zamkniętych kredytów (Faza 2/3) -------------------------------

def test_init_returns_inactive_accounts(logged_in_client, test_user):
    """Konto nieaktywne (dowolnego typu) trafia do inactive_accounts, nie do accounts."""
    acc = create_account(test_user.token, {'name': 'Stary kredyt', 'bank_name': 'Pekao',
                                            'account_type': ACCOUNT_TYPE_KREDYT})
    reconcile_account_balance(test_user.token, acc.id, Decimal('-100.00'))
    reconcile_account_balance(test_user.token, acc.id, Decimal('0.00'))  # spłata
    acc.is_active = False
    db.session.commit()

    resp = logged_in_client.get('/api/init')
    data = resp.get_json()
    assert resp.status_code == 200
    assert all(a['id'] != acc.id for a in data['accounts'])  # poza aktywnym słownikiem
    assert any(l['id'] == acc.id and l['name'] == 'Stary kredyt' for l in data['inactive_accounts'])


def test_init_inactive_accounts_includes_non_kredyt(logged_in_client, test_user):
    """Zamknięte konto NIE-Kredyt (np. KO z upadłego banku) z historią też jest
    w inactive_accounts."""
    acc = create_account(test_user.token, {'name': 'Konto Getin', 'bank_name': 'Getin', 'account_type': 'KO'})
    reconcile_account_balance(test_user.token, acc.id, Decimal('500.00'))  # nadaj historię
    acc.is_active = False
    db.session.commit()

    data = logged_in_client.get('/api/init').get_json()
    assert any(l['id'] == acc.id and l['account_type'] == 'KO' for l in data['inactive_accounts'])


def test_init_inactive_accounts_excludes_empty(logged_in_client, test_user):
    """Nieaktywne konto BEZ transakcji (techniczne/testowe) nie zaśmieca listy."""
    acc = create_account(test_user.token, {'name': 'Puste', 'bank_name': 'X', 'account_type': 'ROR'})
    acc.is_active = False
    db.session.commit()

    data = logged_in_client.get('/api/init').get_json()
    assert all(l['id'] != acc.id for l in data['inactive_accounts'])


def test_closed_loan_transactions_stay_in_init(logged_in_client, test_user):
    """Transakcje zamkniętego kredytu zostają w /api/init (podstawa historii
    Majątku liczonej po stronie klienta) — filtr jest po user_token, nie is_active."""
    acc = create_account(test_user.token, {'name': 'Kredyt X', 'bank_name': 'Pekao',
                                           'account_type': ACCOUNT_TYPE_KREDYT})
    reconcile_account_balance(test_user.token, acc.id, Decimal('-500.00'))
    acc.is_active = False
    db.session.commit()

    data = logged_in_client.get('/api/init').get_json()
    assert any(t['account_id'] == acc.id for t in data['transactions'])
