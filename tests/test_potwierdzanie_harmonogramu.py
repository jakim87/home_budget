"""Potwierdzanie wystąpień cyklicznych i zaplanowanych.

Harmonogram nie księguje się sam: wystąpienie, którego termin nadszedł, czeka „do
potwierdzenia”. Użytkownik potwierdza je (z kwotą i datą z harmonogramu albo
poprawionymi) lub pomija, gdy płatność w tym terminie nie wyszła.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta

from app import db
from app.models import Account, Category, Frequency, PlannedTransaction, RecurringTransaction, Transaction


@pytest.fixture
def harmonogram(app, test_user_token):
    """Miesięczny czynsz z dwoma zaległymi wystąpieniami (miesiąc temu i dziś)."""
    konto = Account(name="Konto", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user_token)
    kategoria = Category(name="Czynsz", type="expense")
    db.session.add_all([konto, kategoria])
    db.session.commit()
    dzis = date.today()
    start = dzis - relativedelta(months=1)
    rec = RecurringTransaction(
        user_token=test_user_token, account_id=konto.id, category_id=kategoria.id,
        title="Czynsz", amount=Decimal("-800.00"), frequency=Frequency.MONTHLY,
        day_of_month=dzis.day, start_date=start, next_run_date=start,
    )
    db.session.add(rec)
    db.session.commit()
    return rec, konto, start


def _saldo(konto_id):
    db.session.expire_all()
    return db.session.get(Account, konto_id).balance


def test_potwierdzenie_ksieguje_i_przesuwa_kursor(logged_in_client, harmonogram):
    rec, konto, start = harmonogram

    resp = logged_in_client.post(f'/api/recurring-transactions/{rec.id}/potwierdz',
                                 json={'occurrence_date': start.isoformat()})

    assert resp.status_code == 201
    tx = db.session.get(Transaction, resp.get_json()['transaction_id'])
    assert (tx.amount, tx.date, tx.origin, tx.source_recurring_id) == (
        Decimal("-800.00"), start, 'recurring', rec.id)
    assert _saldo(konto.id) == Decimal("200.00")
    assert db.session.get(RecurringTransaction, rec.id).next_run_date > start


def test_poprawiona_kwota_i_data_zachowuja_znak_harmonogramu(logged_in_client, harmonogram):
    """Formularz podaje kwotę bez znaku — wydatek nie może stać się przychodem."""
    rec, konto, start = harmonogram
    dzien_pozniej = start + timedelta(days=1)

    resp = logged_in_client.post(f'/api/recurring-transactions/{rec.id}/potwierdz', json={
        'occurrence_date': start.isoformat(), 'amount': '812.40', 'date': dzien_pozniej.isoformat()})

    assert resp.status_code == 201
    tx = db.session.get(Transaction, resp.get_json()['transaction_id'])
    assert (tx.amount, tx.date) == (Decimal("-812.40"), dzien_pozniej)
    assert _saldo(konto.id) == Decimal("187.60")
    # Harmonogram bez zmian — poprawka dotyczy tylko tego wystąpienia.
    assert db.session.get(RecurringTransaction, rec.id).amount == Decimal("-800.00")


def test_pominiecie_przesuwa_kursor_bez_transakcji(logged_in_client, harmonogram):
    rec, konto, start = harmonogram

    resp = logged_in_client.post(f'/api/recurring-transactions/{rec.id}/pomin',
                                 json={'occurrence_date': start.isoformat()})

    assert resp.status_code == 200
    assert db.session.query(Transaction).filter_by(source_recurring_id=rec.id).count() == 0
    assert _saldo(konto.id) == Decimal("1000.00")
    assert db.session.get(RecurringTransaction, rec.id).next_run_date > start


def test_nie_mozna_rozstrzygnac_wystapienia_poza_kolejnoscia(logged_in_client, harmonogram):
    """Kursor posuwa się po jednym kroku — późniejsze wystąpienie czeka na wcześniejsze."""
    rec, konto, _ = harmonogram

    resp = logged_in_client.post(f'/api/recurring-transactions/{rec.id}/potwierdz',
                                 json={'occurrence_date': date.today().isoformat()})

    assert resp.status_code == 400
    assert db.session.query(Transaction).filter_by(source_recurring_id=rec.id).count() == 0
    assert _saldo(konto.id) == Decimal("1000.00")


def test_nie_mozna_potwierdzic_przyszlego_wystapienia(logged_in_client, harmonogram):
    rec, konto, _ = harmonogram
    jutro = date.today() + timedelta(days=1)
    rec.next_run_date = jutro
    db.session.commit()

    resp = logged_in_client.post(f'/api/recurring-transactions/{rec.id}/potwierdz',
                                 json={'occurrence_date': jutro.isoformat()})

    assert resp.status_code == 400
    assert _saldo(konto.id) == Decimal("1000.00")


@pytest.mark.parametrize('kwota', ['0', '-10.00'])
def test_zerowa_albo_ujemna_kwota_poprawki_odrzucona(logged_in_client, harmonogram, kwota):
    rec, konto, start = harmonogram

    resp = logged_in_client.post(f'/api/recurring-transactions/{rec.id}/potwierdz', json={
        'occurrence_date': start.isoformat(), 'amount': kwota})

    assert resp.status_code == 400
    assert _saldo(konto.id) == Decimal("1000.00")


def test_init_podaje_oczekujace_ze_wszystkich_miesiecy(logged_in_client, harmonogram, test_user_token):
    _, konto, _ = harmonogram
    db.session.add(PlannedTransaction(
        user_token=test_user_token, account_id=konto.id, title="OC",
        amount=Decimal("-450.00"), execution_date=date.today() - timedelta(days=3)))
    db.session.add(PlannedTransaction(
        user_token=test_user_token, account_id=konto.id, title="Przyszła",
        amount=Decimal("-10.00"), execution_date=date.today() + timedelta(days=3)))
    db.session.commit()

    oczekujace = logged_in_client.get('/api/init').get_json()['do_potwierdzenia']

    assert sorted(w['desc'] for w in oczekujace) == ['Czynsz', 'Czynsz', 'OC']
    assert [w['date'] for w in oczekujace] == sorted(w['date'] for w in oczekujace)


def test_podglad_miesiaca_pokazuje_oczekujaca_zaplanowana(logged_in_client, harmonogram, test_user_token):
    """Zaplanowana trafia na listę operacji obok cyklicznych — inaczej nie byłoby jej
    gdzie potwierdzić."""
    _, konto, _ = harmonogram
    dzis = date.today()
    db.session.add(PlannedTransaction(user_token=test_user_token, account_id=konto.id, title="OC",
                                      amount=Decimal("-450.00"), execution_date=dzis))
    db.session.commit()

    resp = logged_in_client.get(f'/api/recurring-transactions/preview?year={dzis.year}&month={dzis.month}')

    zaplanowane = [w for w in resp.get_json() if w.get('planned_id')]
    assert [(w['desc'], w['amount'], w['do_potwierdzenia']) for w in zaplanowane] == [('OC', -450.0, True)]


def test_zaplanowana_potwierdzenie_z_poprawka(logged_in_client, harmonogram, test_user_token):
    _, konto, _ = harmonogram
    pt = PlannedTransaction(user_token=test_user_token, account_id=konto.id, title="OC",
                            amount=Decimal("-450.00"), execution_date=date.today())
    db.session.add(pt)
    db.session.commit()

    resp = logged_in_client.post(f'/api/planned-transactions/{pt.id}/potwierdz', json={'amount': '430.00'})

    assert resp.status_code == 201
    tx = db.session.get(Transaction, resp.get_json()['transaction_id'])
    assert (tx.amount, tx.origin) == (Decimal("-430.00"), 'planned')
    assert db.session.get(PlannedTransaction, pt.id).status == 'processed'
    assert _saldo(konto.id) == Decimal("570.00")


def test_zaplanowana_pominieta_znika_z_oczekujacych(logged_in_client, harmonogram, test_user_token):
    _, konto, _ = harmonogram
    pt = PlannedTransaction(user_token=test_user_token, account_id=konto.id, title="OC",
                            amount=Decimal("-450.00"), execution_date=date.today())
    db.session.add(pt)
    db.session.commit()

    resp = logged_in_client.post(f'/api/planned-transactions/{pt.id}/pomin', json={})

    assert resp.status_code == 200
    assert db.session.get(PlannedTransaction, pt.id).status == 'skipped'
    assert _saldo(konto.id) == Decimal("1000.00")
    oczekujace = logged_in_client.get('/api/init').get_json()['do_potwierdzenia']
    assert all(w.get('planned_id') != pt.id for w in oczekujace)


def test_zaplanowana_w_przyszlosci_nie_do_potwierdzenia(logged_in_client, harmonogram, test_user_token):
    _, konto, _ = harmonogram
    pt = PlannedTransaction(user_token=test_user_token, account_id=konto.id, title="OC",
                            amount=Decimal("-450.00"), execution_date=date.today() + timedelta(days=1))
    db.session.add(pt)
    db.session.commit()

    resp = logged_in_client.post(f'/api/planned-transactions/{pt.id}/potwierdz', json={})

    assert resp.status_code == 400
    assert db.session.get(PlannedTransaction, pt.id).status == 'pending'
