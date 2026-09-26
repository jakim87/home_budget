import pytest
from decimal import Decimal
from app import db
from app.models import User, Account
from sqlalchemy.exc import IntegrityError
from app.services.account_service import create_account, update_account, reorder_accounts

VALID_NRB = "61109010140000071219812874"

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


def test_create_account_valid_nrb_accepted(app):
    user = User(username="testuser5", email="test5@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    acc = create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank', 'account_number': VALID_NRB})

    assert acc.account_number == VALID_NRB

def test_create_account_accepts_nrb_with_spaces(app):
    user = User(username="testuser6", email="test6@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    spaced = "61 1090 1014 0000 0712 1981 2874"
    acc = create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank', 'account_number': spaced})

    assert acc.account_number == VALID_NRB

def test_create_account_rejects_bad_checksum(app):
    user = User(username="testuser7", email="test7@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    bad_checksum = VALID_NRB[:5] + str((int(VALID_NRB[5]) + 1) % 10) + VALID_NRB[6:]

    with pytest.raises(ValueError):
        create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank', 'account_number': bad_checksum})

    assert db.session.query(Account).filter_by(user_token=user.token).count() == 0

@pytest.mark.parametrize("bad_length_nrb", [VALID_NRB[:-1], VALID_NRB + "0"])
def test_create_account_rejects_wrong_length(app, bad_length_nrb):
    user = User(username="testuser8", email="test8@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    with pytest.raises(ValueError):
        create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank', 'account_number': bad_length_nrb})

def test_create_account_without_number_is_optional(app):
    user = User(username="testuser9", email="test9@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    acc = create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank'})

    assert acc.account_number is None

def test_update_account_with_valid_nrb_succeeds(app):
    user = User(username="testuser10", email="test10@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()
    acc = create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank'})

    updated = update_account(user.token, acc.id, {'account_number': VALID_NRB})

    assert updated.account_number == VALID_NRB

def test_update_account_with_bad_checksum_is_rejected_and_keeps_old_value(app):
    user = User(username="testuser11", email="test11@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()
    acc = create_account(user.token, {'name': 'Konto', 'bank_name': 'mBank', 'account_number': VALID_NRB})

    bad_checksum = VALID_NRB[:5] + str((int(VALID_NRB[5]) + 1) % 10) + VALID_NRB[6:]
    with pytest.raises(ValueError):
        update_account(user.token, acc.id, {'account_number': bad_checksum})

    db.session.refresh(acc)
    assert acc.account_number == VALID_NRB


# --- Archiwizacja vs trwałe usunięcie konta ---

def test_konto_bez_zadnych_powiazan_usuwane_trwale(logged_in_client, test_user):
    acc = create_account(test_user.token, {'name': 'Pomyłka', 'bank_name': 'X'})
    acc_id = acc.id

    resp = logged_in_client.delete(f'/api/accounts/{acc_id}')

    assert resp.status_code == 200
    assert resp.get_json()['result'] == 'deleted'
    db.session.expire_all()
    assert db.session.get(Account, acc_id) is None


def test_konto_z_transakcjami_archiwizowane_z_zachowaniem_transakcji(logged_in_client, test_user):
    from app.models import Transaction
    from datetime import date
    acc = create_account(test_user.token, {'name': 'Poż. Got.', 'bank_name': 'X'})
    tx = Transaction(date=date(2026, 1, 5), title='Wpłata', amount=Decimal('100.00'),
                     account_id=acc.id, user_token=test_user.token)
    db.session.add(tx)
    db.session.commit()

    resp = logged_in_client.delete(f'/api/accounts/{acc.id}')

    assert resp.status_code == 200
    assert resp.get_json()['result'] == 'archived'
    db.session.expire_all()
    assert db.session.get(Account, acc.id).is_active is False
    assert db.session.get(Transaction, tx.id) is not None


def test_konto_z_harmonogramem_bez_transakcji_archiwizowane(logged_in_client, test_user):
    """Klucz obcy z harmonogramu blokowałby DELETE na PostgreSQL — archiwizujemy."""
    from app.models import RecurringTransaction, Frequency
    from datetime import date
    acc = create_account(test_user.token, {'name': 'Z harmonogramem', 'bank_name': 'X'})
    db.session.add(RecurringTransaction(
        user_token=test_user.token, account_id=acc.id, title='Czynsz', amount=Decimal('-100.00'),
        frequency=Frequency.MONTHLY, day_of_month=1, interval=1,
        start_date=date(2026, 1, 1), next_run_date=date(2026, 10, 1)))
    db.session.commit()

    resp = logged_in_client.delete(f'/api/accounts/{acc.id}')

    assert resp.get_json()['result'] == 'archived'
    db.session.expire_all()
    assert db.session.get(Account, acc.id).is_active is False


def test_lista_powiazan_konta_obejmuje_kazdy_klucz_obcy(app):
    """Kolumna wskazująca na konto, a nieobecna w _POWIAZANIA_KONTA, sprawi, że
    serwer uzna konto za puste i spróbuje je usunąć — PostgreSQL odrzuci to błędem.
    SQLite w testach kluczy obcych nie pilnuje, więc bez tego testu nikt by tego nie zauważył."""
    from app.services.account_service import _POWIAZANIA_KONTA
    klucze_obce = {
        (tabela.name, kolumna.name)
        for tabela in db.Model.metadata.tables.values()
        for kolumna in tabela.columns
        if any(fk.column.table.name == 'accounts' for fk in kolumna.foreign_keys)
    }
    na_liscie = {(kolumna.table.name, kolumna.name) for _, kolumna in _POWIAZANIA_KONTA}
    assert klucze_obce == na_liscie
