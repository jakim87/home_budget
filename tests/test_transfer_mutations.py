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
from app.services.import_history_service import record_statement_import
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


# --- Dane dla ostrzeżenia w UI ----------------------------------------------

def test_init_exposes_linked_transaction_id_for_transfer_legs(logged_in_client, transfer):
    """/api/init wystawia linked_transaction_id — front używa go, by ostrzec przy
    usuwaniu, że znikną obie nogi przelewu, i wskazać które."""
    _, _, _, src, mirror = transfer
    data = logged_in_client.get('/api/init').get_json()
    by_id = {t['id']: t for t in data['transactions']}
    assert by_id[src.id]['linked_transaction_id'] == mirror.id
    assert by_id[mirror.id]['linked_transaction_id'] == src.id


# --- Zmiana kontrahenta (konta docelowego) -----------------------------------
#
# Regresja #167: update_transaction synchronizowało drugą nogę wyłącznie przy zmianie
# kwoty. Zmiana kontrahenta na inne "Moje konto: X" zostawiała lustro na starym koncie
# — saldo starego konta zawyżone, nowego zaniżone, a para wskazywała niezgodne konta.

@pytest.fixture
def konto_c(app, test_user):
    """Trzecie konto + kontrahent na nie wskazujący (cel zmiany)."""
    acc_c = Account(name="Konto C", bank_name="Bank", balance=Decimal("0.00"),
                    user_token=test_user.token)
    db.session.add(acc_c)
    db.session.commit()
    cat = db.session.query(Category).filter_by(name="Przelew wewnętrzny").first()
    if not cat:
        cat = Category(name="Przelew wewnętrzny", type="transfer")
        db.session.add(cat)
        db.session.commit()
    cont_c = Contractor(name="Moje konto: Konto C", user_token=test_user.token,
                        default_category_id=cat.id, linked_account_id=acc_c.id)
    db.session.add(cont_c)
    db.session.commit()
    return acc_c, cont_c


def test_zmiana_kontrahenta_przenosi_lustro_na_nowe_konto(transfer, konto_c):
    """Zmiana konta docelowego przenosi lustro razem z saldem."""
    token, acc_a, acc_b, src, _ = transfer
    acc_c, cont_c = konto_c

    update_transaction(token, src.id, {'contractor_id': cont_c.id})

    db.session.expire_all()
    assert db.session.query(Transaction).filter_by(account_id=acc_b.id).count() == 0
    nowe_lustro = db.session.query(Transaction).filter_by(account_id=acc_c.id).one()
    assert nowe_lustro.amount == Decimal("300.00")
    assert db.session.get(Transaction, src.id).linked_transaction_id == nowe_lustro.id
    assert nowe_lustro.linked_transaction_id == src.id
    assert db.session.get(Account, acc_a.id).balance == Decimal("700.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("0.00")
    assert db.session.get(Account, acc_c.id).balance == Decimal("300.00")


def test_zmiana_na_konto_z_wlasnymi_wyciagami_nie_tworzy_lustra(transfer, konto_c):
    """Nowe konto docelowe dostaje własne wyciągi → lustra nie ma, noga czeka na drugą stronę."""
    token, acc_a, acc_b, src, _ = transfer
    acc_c, cont_c = konto_c
    record_statement_import(
        user_token=token, filename="c.csv", bank="ing", file_format="csv",
        account_id=acc_c.id, period_start=date(2024, 5, 1), period_end=date(2024, 5, 31),
        transaction_count=1, skipped_count=0, batch_id="batch-c",
    )

    update_transaction(token, src.id, {'contractor_id': cont_c.id})

    db.session.expire_all()
    assert db.session.query(Transaction).filter_by(account_id=acc_b.id).count() == 0
    assert db.session.query(Transaction).filter_by(account_id=acc_c.id).count() == 0
    assert db.session.get(Transaction, src.id).linked_transaction_id is None
    assert db.session.get(Account, acc_b.id).balance == Decimal("0.00")
    assert db.session.get(Account, acc_c.id).balance == Decimal("0.00")


def test_zmiana_na_zwyklego_kontrahenta_usuwa_lustro(transfer):
    """Przelew przestaje być przelewem → druga noga znika, saldo konta docelowego wraca."""
    token, acc_a, acc_b, src, _ = transfer
    zakupy = Category(name="Zakupy", type="expense")
    sklep = Contractor(name="Sklep", user_token=token)
    db.session.add_all([zakupy, sklep])
    db.session.commit()

    update_transaction(token, src.id, {'contractor_id': sklep.id, 'category': 'Zakupy'})

    db.session.expire_all()
    assert db.session.query(Transaction).filter_by(account_id=acc_b.id).count() == 0
    assert db.session.get(Transaction, src.id).linked_transaction_id is None
    assert db.session.get(Account, acc_a.id).balance == Decimal("700.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("0.00")


def test_realna_druga_noga_z_wyciagu_nie_jest_kasowana(app, test_user, konto_c):
    """Druga noga pochodząca z wyciągu to prawdziwa operacja bankowa — edycja
    kontrahenta wolno ją najwyżej odpiąć, nigdy usunąć. Zostaje wtedy jako wpływ
    bez pary, do poprawienia przez użytkownika."""
    token = test_user.token
    acc_a = Account(name="Konto A", bank_name="Bank", balance=Decimal("1000.00"), user_token=token)
    acc_b = Account(name="Konto B", bank_name="Bank", balance=Decimal("0.00"), user_token=token)
    cat = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add_all([acc_a, acc_b, cat])
    db.session.commit()
    cont_b = Contractor(name="Moje konto: Konto B", user_token=token,
                        default_category_id=cat.id, linked_account_id=acc_b.id)
    cont_a = Contractor(name="Moje konto: Konto A", user_token=token,
                        default_category_id=cat.id, linked_account_id=acc_a.id)
    db.session.add_all([cont_b, cont_a])
    db.session.commit()
    for acc_id, nazwa in ((acc_a.id, "a.csv"), (acc_b.id, "b.csv")):
        record_statement_import(
            user_token=token, filename=nazwa, bank="ing", file_format="csv",
            account_id=acc_id, period_start=date(2024, 5, 1), period_end=date(2024, 5, 31),
            transaction_count=1, skipped_count=0, batch_id=f"batch-{nazwa}",
        )

    src = create_transaction(token, acc_a.id, Decimal("-300.00"), "Przelew A->B", date(2024, 5, 1),
                             category_id=cat.id, contractor_id=cont_b.id,
                             preserve_sign=True, origin='import')
    realna = create_transaction(token, acc_b.id, Decimal("300.00"), "Przelew A->B", date(2024, 5, 1),
                                category_id=cat.id, contractor_id=cont_a.id,
                                preserve_sign=True, origin='import')
    assert src.linked_transaction_id == realna.id
    realna_id = realna.id
    acc_c, cont_c = konto_c

    update_transaction(token, src.id, {'contractor_id': cont_c.id})

    db.session.expire_all()
    zachowana = db.session.get(Transaction, realna_id)
    assert zachowana is not None, "realna transakcja z wyciągu nie może zostać skasowana"
    assert zachowana.amount == Decimal("300.00")
    assert zachowana.linked_transaction_id is None
    assert db.session.get(Account, acc_b.id).balance == Decimal("300.00")
