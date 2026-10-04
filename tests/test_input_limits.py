"""Granice danych wejściowych: zakres kwot, długości pól, podziały transakcji.

Kolumny mają limity (Numeric(10, 2), String(n)), których SQLite nie egzekwuje —
na PostgreSQL przekroczenie kończyło się DataError i odpowiedzią 500. Te testy
pilnują, żeby walidacja odrzucała takie dane wcześniej, z 400 (przegląd 2026-10-04).
"""
from datetime import date
from decimal import Decimal

import pytest
from marshmallow import ValidationError

from app import db
from app.models import Account, Category, Contractor, Transaction, TransactionStaging
from app.schemas import (PlannedTransactionSchema, RecurringTransactionSchema,
                         SplitSchema, TransactionSchema)

ZA_DUZO = '100000000.00'


@pytest.fixture
def tx(app, test_user_token):
    konto = Account(name='Konto', bank_name='Bank', balance=Decimal('-100.00'), user_token=test_user_token)
    kategoria = Category(name='Jedzenie', type='expense', user_token=test_user_token)
    db.session.add_all([konto, kategoria])
    db.session.commit()
    t = Transaction(date=date(2024, 1, 10), title='Zakupy', amount=Decimal('-100.00'),
                    account_id=konto.id, category_id=kategoria.id, user_token=test_user_token)
    db.session.add(t)
    db.session.commit()
    return t


@pytest.mark.parametrize('schemat, dane', [
    (TransactionSchema, {'amount': ZA_DUZO, 'date': '2024-01-10', 'account_id': 1}),
    (TransactionSchema, {'amount': '-' + ZA_DUZO, 'date': '2024-01-10', 'account_id': 1}),
    (SplitSchema, {'amount': ZA_DUZO, 'category': 'Jedzenie'}),
    (PlannedTransactionSchema, {'amount': ZA_DUZO, 'title': 'x', 'account_id': 1, 'category_id': 1,
                                'execution_date': '2024-01-10'}),
    (RecurringTransactionSchema, {'amount': ZA_DUZO, 'title': 'x', 'account_id': 1, 'frequency': 'daily',
                                  'start_date': '2024-01-10'}),
])
def test_kwota_poza_zakresem_kolumny_jest_odrzucana(schemat, dane):
    with pytest.raises(ValidationError) as err:
        schemat().load(dane)
    assert 'amount' in err.value.messages


def test_dodanie_transakcji_z_za_duza_kwota_daje_400(logged_in_client, tx):
    resp = logged_in_client.post('/api/transactions', json={
        'amount': ZA_DUZO, 'date': '2024-01-10', 'account_id': tx.account_id, 'title': 'x'})

    assert resp.status_code == 400
    assert db.session.query(Transaction).count() == 1


def test_podzialy_ponad_kwote_transakcji_sa_odrzucane(logged_in_client, tx):
    resp = logged_in_client.put(f'/api/transactions/{tx.id}', json={'splits': [
        {'amount': 60, 'category': 'Jedzenie'}, {'amount': 40.01, 'category': 'Jedzenie'}]})

    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx.id).splits == []


def test_podzial_rowny_kwocie_transakcji_przechodzi(logged_in_client, tx):
    resp = logged_in_client.put(f'/api/transactions/{tx.id}', json={'splits': [
        {'amount': 60, 'category': 'Jedzenie'}, {'amount': 40, 'category': 'Jedzenie'}]})

    assert resp.status_code == 200
    db.session.expire_all()
    assert len(db.session.get(Transaction, tx.id).splits) == 2


def test_ujemny_podzial_jest_odrzucany(logged_in_client, tx):
    resp = logged_in_client.put(f'/api/transactions/{tx.id}', json={'splits': [
        {'amount': -10, 'category': 'Jedzenie'}]})

    assert resp.status_code == 400


def test_zmniejszenie_kwoty_ponizej_podzialow_jest_odrzucane(logged_in_client, tx):
    logged_in_client.put(f'/api/transactions/{tx.id}', json={'splits': [{'amount': 80, 'category': 'Jedzenie'}]})

    resp = logged_in_client.put(f'/api/transactions/{tx.id}', json={'amount': '-50.00'})

    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx.id).amount == Decimal('-100.00')
    assert db.session.get(Account, tx.account_id).balance == Decimal('-100.00')


def test_dodanie_transakcji_z_podzialami_ponad_kwote_daje_400(logged_in_client, tx):
    resp = logged_in_client.post('/api/transactions', json={
        'amount': '-50.00', 'date': '2024-01-10', 'account_id': tx.account_id, 'title': 'x',
        'splits': [{'amount': 60, 'category': 'Jedzenie'}]})

    assert resp.status_code == 400
    assert db.session.query(Transaction).count() == 1
    assert db.session.get(Account, tx.account_id).balance == Decimal('-100.00')


def test_za_dluga_nazwa_kontrahenta_daje_400(logged_in_client, app):
    resp = logged_in_client.post('/api/contractors', json={'name': 'x' * 101})

    assert resp.status_code == 400
    assert db.session.query(Contractor).count() == 0


def test_za_dluga_nazwa_kontrahenta_z_poczekalni_daje_400(logged_in_client, tx, test_user_token):
    stg = TransactionStaging(date=date(2024, 1, 10), amount=Decimal('-5.00'), title='x',
                             account_id=tx.account_id, user_token=test_user_token)
    db.session.add(stg)
    db.session.commit()

    resp = logged_in_client.post(f'/api/staging/{stg.id}/accept-contractor', json={'name': 'x' * 101})

    assert resp.status_code == 400
    assert db.session.query(Contractor).count() == 0
