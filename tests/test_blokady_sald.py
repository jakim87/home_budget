"""Blokady wierszy przy zmianie salda (audyt 2026-11-08, pkt 6).

Account.balance zmienia się odczytem w Pythonie i zapisem nowej wartości. Bez
SELECT ... FOR UPDATE dwa równoległe żądania na tym samym koncie (podwójny Enter,
dwie karty, nocny process-scheduled w trakcie importu) liczą od tego samego salda
i jedna kwota ginie.

SQLite ignoruje FOR UPDATE, więc wyścigu tu nie odtworzymy. Testy sprawdzają dwie
rzeczy, które da się sprawdzić na każdej bazie: że zapytanie o konto/wiersz prosi
o blokadę (kompilacja pod dialekt PostgreSQL) i że saldo liczy się od wartości
z bazy, a nie od obiektu wczytanego wcześniej do sesji bez blokady.
"""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.dialects import postgresql

from app import db
from app.models import Account, Category, Contractor, Transaction, TransactionStaging
from app.services.budget_service import (
    approve_staging_record, create_transaction, reconcile_account_balance,
)
from app.services.transaction_service import delete_transaction, update_transaction


@contextmanager
def zablokowane_tabele():
    """Zbiera nazwy tabel, których SELECT-y poszły z FOR UPDATE."""
    tabele = []

    def sprawdz(stan):
        if not stan.is_select:
            return
        sql = str(stan.statement.compile(dialect=postgresql.dialect()))
        if 'FOR UPDATE' in sql:
            tabele.extend(m.local_table.name for m in stan.all_mappers)

    sesja = db.session()
    event.listen(sesja, 'do_orm_execute', sprawdz)
    try:
        yield tabele
    finally:
        event.remove(sesja, 'do_orm_execute', sprawdz)


@pytest.fixture
def konta(app, test_user):
    """Konto A (1000) i konto B (0) bez wyciągów, kategoria przelewu i kontrahent 'Moje konto: B'."""
    a = Account(name="Konto A", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user.token)
    b = Account(name="Konto B", bank_name="Bank", balance=Decimal("0.00"), user_token=test_user.token)
    przelew = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add_all([a, b, przelew])
    db.session.commit()
    na_b = Contractor(name="Moje konto: Konto B", user_token=test_user.token,
                      default_category_id=przelew.id, linked_account_id=b.id)
    db.session.add(na_b)
    db.session.commit()
    return test_user.token, a, b, przelew, na_b


def _saldo_z_bazy(account_id):
    return db.session.execute(select(Account.balance).where(Account.id == account_id)).scalar()


def _zmien_saldo_w_bazie(account_id, saldo):
    """Symuluje inne żądanie, które między wczytaniem konta a zapisem zaksięgowało operację."""
    db.session.execute(
        update(Account).where(Account.id == account_id).values(balance=saldo),
        execution_options={'synchronize_session': False})


def test_create_transaction_blokuje_konto(konta):
    token, a, *_ = konta
    with zablokowane_tabele() as tabele:
        create_transaction(token, a.id, Decimal("-10.00"), "Zakup", date(2026, 11, 1))
    assert 'accounts' in tabele


def test_create_transaction_liczy_od_salda_z_bazy(konta):
    """Konto już siedzi w sesji z saldem 1000, ale w bazie inne żądanie zostawiło 900."""
    token, a, *_ = konta
    assert a.balance == Decimal("1000.00")
    _zmien_saldo_w_bazie(a.id, Decimal("900.00"))

    create_transaction(token, a.id, Decimal("-10.00"), "Zakup", date(2026, 11, 1))

    assert _saldo_z_bazy(a.id) == Decimal("890.00")


def test_lustro_przelewu_liczy_saldo_konta_docelowego_od_bazy(konta):
    token, a, b, przelew, na_b = konta
    assert b.balance == Decimal("0.00")
    _zmien_saldo_w_bazie(b.id, Decimal("50.00"))

    create_transaction(token, a.id, Decimal("300.00"), "Na B", date(2026, 11, 1),
                       category_id=przelew.id, contractor_id=na_b.id)

    assert _saldo_z_bazy(b.id) == Decimal("350.00")


def test_update_transaction_blokuje_konto_i_transakcje(konta):
    token, a, *_ = konta
    tx = create_transaction(token, a.id, Decimal("-10.00"), "Zakup", date(2026, 11, 1))
    with zablokowane_tabele() as tabele:
        update_transaction(token, tx.id, {'amount': '-25.00'})
    assert {'accounts', 'transactions'} <= set(tabele)


def test_update_transaction_liczy_od_salda_z_bazy(konta):
    token, a, *_ = konta
    tx = create_transaction(token, a.id, Decimal("-10.00"), "Zakup", date(2026, 11, 1))
    _zmien_saldo_w_bazie(a.id, Decimal("500.00"))

    update_transaction(token, tx.id, {'amount': '-25.00'})

    assert _saldo_z_bazy(a.id) == Decimal("485.00")


def test_delete_transaction_liczy_od_salda_z_bazy(konta):
    token, a, *_ = konta
    tx = create_transaction(token, a.id, Decimal("-10.00"), "Zakup", date(2026, 11, 1))
    _zmien_saldo_w_bazie(a.id, Decimal("500.00"))

    with zablokowane_tabele() as tabele:
        delete_transaction(token, tx.id)

    assert 'accounts' in tabele
    assert _saldo_z_bazy(a.id) == Decimal("510.00")


def test_reconcile_blokuje_konto(konta):
    token, a, *_ = konta
    with zablokowane_tabele() as tabele:
        reconcile_account_balance(token, a.id, Decimal("1200.00"))
    assert 'accounts' in tabele
    assert _saldo_z_bazy(a.id) == Decimal("1200.00")


def test_zatwierdzenie_poczekalni_blokuje_wiersz(konta):
    """Podwójne „Zatwierdź”: drugie żądanie musi poczekać na pierwsze i nie znaleźć wiersza."""
    token, a, *_ = konta
    sklep = Contractor(name="Sklep", user_token=token)
    wydatki = Category(name="Zakupy", type="expense")
    stg = TransactionStaging(date=date(2026, 11, 2), amount=Decimal("-30.00"), title="Zakup",
                             status="pending", user_token=token, account_id=a.id)
    db.session.add_all([sklep, wydatki, stg])
    db.session.commit()

    with zablokowane_tabele() as tabele:
        approve_staging_record(token, stg.id, {'category': 'Zakupy', 'contractor_id': sklep.id})

    assert 'transaction_staging' in tabele
    assert 'accounts' in tabele
    with pytest.raises(ValueError):
        approve_staging_record(token, stg.id, {'category': 'Zakupy', 'contractor_id': sklep.id})
    assert db.session.query(Transaction).count() == 1
