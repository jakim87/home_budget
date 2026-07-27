"""Modyfikacja (usunięcie / edycja kwoty) nogi przelewu wewnętrznego.

Przelew wewnętrzny to DWIE powiązane transakcje (linked_transaction_id). Operacje
na jednej nodze muszą propagować się na drugą, inaczej Net Worth rozjeżdża się o
kwotę przelewu (outflow znika/zmienia się, inflow zostaje bez zmian = pieniądze
z powietrza). Regresja wykryta w przeglądzie 2026-07-27 (rekomendacje #1, #2).
"""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, Transaction
from app.services.budget_service import create_transaction
from app.services.transaction_service import archive_and_delete_transaction, update_transaction


@pytest.fixture
def transfer(app, test_user):
    """Konta A(1000)/B(0) + wykonany przelew wewnętrzny 300 A→B z wygenerowanym
    lustrem. Po przelewie: A=700, B=300, suma=1000."""
    acc_a = Account(name="Konto A", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user.token)
    acc_b = Account(name="Konto B", bank_name="Bank", balance=Decimal("0.00"), user_token=test_user.token)
    cat = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add_all([acc_a, acc_b, cat])
    db.session.commit()
    cont = Contractor(name="Moje konto: Konto B", user_token=test_user.token,
                      default_category_id=cat.id, linked_account_id=acc_b.id)
    db.session.add(cont)
    db.session.commit()

    src = create_transaction(test_user.token, acc_a.id, Decimal("300.00"), "Przelew A->B",
                             date(2024, 5, 1), category_id=cat.id, contractor_id=cont.id)
    mirror = db.session.query(Transaction).filter_by(account_id=acc_b.id).one()
    return test_user.token, acc_a, acc_b, src, mirror


def _total(acc_a, acc_b):
    return db.session.get(Account, acc_a.id).balance + db.session.get(Account, acc_b.id).balance


def test_transfer_setup_is_balanced(transfer):
    _, acc_a, acc_b, src, mirror = transfer
    assert db.session.get(Account, acc_a.id).balance == Decimal("700.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("300.00")
    assert src.amount == Decimal("-300.00")
    assert mirror.amount == Decimal("300.00")
    assert src.linked_transaction_id == mirror.id
    assert mirror.linked_transaction_id == src.id


# --- Usuwanie ----------------------------------------------------------------

def test_deleting_source_leg_also_deletes_mirror_and_preserves_net_worth(transfer):
    token, acc_a, acc_b, src, mirror = transfer
    archive_and_delete_transaction(token, src.id)

    assert db.session.query(Transaction).count() == 0  # obie nogi usunięte
    assert _total(acc_a, acc_b) == Decimal("1000.00")  # Net Worth zachowany
    assert db.session.get(Account, acc_a.id).balance == Decimal("1000.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("0.00")


def test_deleting_mirror_leg_also_deletes_source_and_preserves_net_worth(transfer):
    token, acc_a, acc_b, src, mirror = transfer
    archive_and_delete_transaction(token, mirror.id)

    assert db.session.query(Transaction).count() == 0
    assert _total(acc_a, acc_b) == Decimal("1000.00")


# --- Edycja kwoty ------------------------------------------------------------

def test_editing_source_leg_amount_syncs_mirror_and_preserves_net_worth(transfer):
    token, acc_a, acc_b, src, mirror = transfer
    update_transaction(token, src.id, {'amount': '500'})

    db.session.refresh(src)
    db.session.refresh(mirror)
    assert src.amount == Decimal("-500.00")   # znak wypływu zachowany mimo dodatniego wejścia
    assert mirror.amount == Decimal("500.00")  # lustro zsynchronizowane
    assert _total(acc_a, acc_b) == Decimal("1000.00")  # Net Worth zachowany
    assert db.session.get(Account, acc_a.id).balance == Decimal("500.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("500.00")


def test_editing_mirror_leg_amount_syncs_source_and_preserves_net_worth(transfer):
    token, acc_a, acc_b, src, mirror = transfer
    update_transaction(token, mirror.id, {'amount': '250'})

    db.session.refresh(src)
    db.session.refresh(mirror)
    assert mirror.amount == Decimal("250.00")  # wpływ dodatni
    assert src.amount == Decimal("-250.00")    # źródło zsynchronizowane, znak wypływu
    assert _total(acc_a, acc_b) == Decimal("1000.00")
