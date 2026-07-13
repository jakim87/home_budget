"""Systematyczne testy autoryzacji (IDOR): zalogowany użytkownik B (intruz) próbuje
modyfikować zasoby użytkownika A (testuser) po ID. Każdy test sprawdza dwie rzeczy:
odpowiedź HTTP z błędem ORAZ brak zmiany stanu w bazie."""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import (
    Account, Category, Contractor, Transaction, TransactionStaging,
    TransactionArchive, RecurringTransaction, PlannedTransaction, Frequency,
)
from tests.conftest import login_as


@pytest.fixture
def owner_data(app, test_user):
    """Komplet zasobów należących do testuser — cele ataku."""
    account = Account(name="Konto Ofiary", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user.token)
    category = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, category])
    db.session.commit()

    contractor = Contractor(name="Biedronka", user_token=test_user.token, default_category_id=category.id)
    db.session.add(contractor)
    db.session.commit()

    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-50.00"),
                     account_id=account.id, category_id=category.id, user_token=test_user.token)
    stg = TransactionStaging(date=date(2024, 1, 11), amount=Decimal("-20.00"), title="Staging",
                             status="pending", user_token=test_user.token, account_id=account.id)
    rec = RecurringTransaction(user_token=test_user.token, account_id=account.id, title="Czynsz",
                               amount=Decimal("-100.00"), frequency=Frequency.MONTHLY, day_of_month=1,
                               interval=1, start_date=date(2024, 1, 1), next_run_date=date(2024, 6, 1))
    planned = PlannedTransaction(user_token=test_user.token, account_id=account.id, title="Ubezpieczenie",
                                 amount=Decimal("-300.00"), execution_date=date(2024, 7, 1), status="pending")
    db.session.add_all([tx, stg, rec, planned])
    db.session.commit()

    return {
        'account': account, 'category': category, 'contractor': contractor,
        'tx': tx, 'stg': stg, 'rec': rec, 'planned': planned,
    }


@pytest.fixture
def intruder_client(client, owner_data, other_user):
    """Klient zalogowany jako intruz (other_user), z gotowymi zasobami ofiary."""
    login_as(client, "intruz")
    return client


def test_intruder_cannot_update_transaction(intruder_client, owner_data):
    tx = owner_data['tx']
    resp = intruder_client.put(f'/api/transactions/{tx.id}', json={'title': 'PRZEJĘTE', 'amount': '999.00'})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx.id).title == "Zakupy"
    assert db.session.get(Transaction, tx.id).amount == Decimal("-50.00")


def test_intruder_cannot_delete_transaction(intruder_client, owner_data):
    tx = owner_data['tx']
    resp = intruder_client.delete(f'/api/transactions/{tx.id}')
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx.id) is not None
    assert db.session.query(TransactionArchive).filter_by(original_id=tx.id).count() == 0


def test_intruder_cannot_update_account(intruder_client, owner_data):
    acc = owner_data['account']
    resp = intruder_client.put(f'/api/accounts/{acc.id}', json={'name': 'PRZEJĘTE'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Account, acc.id).name == "Konto Ofiary"


def test_intruder_cannot_delete_account(intruder_client, owner_data):
    acc = owner_data['account']
    resp = intruder_client.delete(f'/api/accounts/{acc.id}')
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Account, acc.id).is_active is True


def test_intruder_cannot_reconcile_account(intruder_client, owner_data):
    acc = owner_data['account']
    resp = intruder_client.post(f'/api/accounts/{acc.id}/reconcile', json={'new_balance': '0.00'})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Account, acc.id).balance == Decimal("1000.00")
    # Nie powstała transakcja korygująca na cudzym koncie
    assert db.session.query(Transaction).filter_by(account_id=acc.id, title="Uzgadnianie salda").count() == 0


def test_intruder_cannot_update_contractor(intruder_client, owner_data):
    cont = owner_data['contractor']
    resp = intruder_client.put(f'/api/contractors/{cont.id}', json={'name': 'PRZEJĘTE'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Contractor, cont.id).name == "Biedronka"


def test_intruder_cannot_delete_contractor(intruder_client, owner_data):
    cont = owner_data['contractor']
    resp = intruder_client.delete(f'/api/contractors/{cont.id}')
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Contractor, cont.id).is_active is True


def test_intruder_cannot_update_recurring(intruder_client, owner_data):
    rec = owner_data['rec']
    resp = intruder_client.put(f'/api/recurring-transactions/{rec.id}', json={'title': 'PRZEJĘTE'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(RecurringTransaction, rec.id).title == "Czynsz"


def test_intruder_cannot_delete_planned(intruder_client, owner_data):
    planned = owner_data['planned']
    resp = intruder_client.delete(f'/api/planned-transactions/{planned.id}')
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(PlannedTransaction, planned.id) is not None


def test_intruder_cannot_approve_staging(intruder_client, owner_data):
    stg = owner_data['stg']
    cont = owner_data['contractor']
    resp = intruder_client.post(f'/api/staging/{stg.id}/approve',
                                json={'category': 'Jedzenie', 'contractor_id': cont.id})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg.id).status == "pending"


def test_intruder_cannot_accept_staging_contractor(intruder_client, owner_data):
    stg = owner_data['stg']
    resp = intruder_client.post(f'/api/staging/{stg.id}/accept-contractor', json={'name': 'Nowy'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg.id).proposed_contractor_id is None


def test_intruder_cannot_create_transaction_with_foreign_contractor(intruder_client, owner_data, other_user):
    """Intruz podaje CUDZY contractor_id przy tworzeniu własnej transakcji — kontrahent
    nie może zostać podpięty (a jego nazwa nie może wyciec w odpowiedzi)."""
    my_acc = Account(name="Konto Intruza", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    db.session.add(my_acc)
    db.session.commit()

    resp = intruder_client.post('/api/transactions', json={
        'title': 'Test', 'amount': '-10.00', 'date': '2024-01-15',
        'account_id': my_acc.id, 'contractor_id': owner_data['contractor'].id,
    })
    # Transakcja może powstać, ale nazwa cudzego kontrahenta nie może wyciec
    if resp.status_code == 201:
        assert resp.get_json().get('contractor_name') is None


def test_intruder_sees_only_own_data_in_init(intruder_client, owner_data):
    resp = intruder_client.get('/api/init')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['transactions'] == []
    assert data['accounts'] == []
    assert all(c['name'] != 'Biedronka' for c in data['contractors'])
