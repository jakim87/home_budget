"""Testy zaplanowanych transakcji (API + walidacja własności) — wcześniej zero pokrycia.
Idempotentność przetwarzania jest w test_data_integrity.py."""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, PlannedTransaction


@pytest.fixture
def planned_setup(app, test_user):
    account = Account(name="Konto Plan", bank_name="Bank", balance=Decimal("500.00"), user_token=test_user.token)
    category = Category(name="Ubezpieczenia", type="expense")
    db.session.add_all([account, category])
    db.session.commit()
    return account, category


def test_create_planned_transaction(logged_in_client, app, planned_setup):
    account, category = planned_setup
    resp = logged_in_client.post('/api/planned-transactions/', json={
        'title': 'OC samochodu',
        'amount': '-450.00',
        'account_id': account.id,
        'category_id': category.id,
        'execution_date': '2024-09-01',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['title'] == 'OC samochodu'
    assert data['status'] == 'pending'
    assert db.session.query(PlannedTransaction).count() == 1


def test_create_planned_rejects_foreign_account(logged_in_client, app, planned_setup, other_user):
    """Konto innego użytkownika w definicji → 400, definicja nie powstaje."""
    _, category = planned_setup
    foreign_acc = Account(name="Cudze", bank_name="Bank", user_token=other_user.token)
    db.session.add(foreign_acc)
    db.session.commit()

    resp = logged_in_client.post('/api/planned-transactions/', json={
        'title': 'Podstęp', 'amount': '-1.00', 'account_id': foreign_acc.id,
        'category_id': category.id, 'execution_date': '2024-09-01',
    })
    assert resp.status_code == 400
    assert db.session.query(PlannedTransaction).count() == 0


def test_create_planned_rejects_foreign_contractor(logged_in_client, app, planned_setup, other_user):
    account, category = planned_setup
    foreign_cont = Contractor(name="Cudzy kontrahent", user_token=other_user.token)
    db.session.add(foreign_cont)
    db.session.commit()

    resp = logged_in_client.post('/api/planned-transactions/', json={
        'title': 'Podstęp', 'amount': '-1.00', 'account_id': account.id,
        'category_id': category.id, 'contractor_id': foreign_cont.id,
        'execution_date': '2024-09-01',
    })
    assert resp.status_code == 400
    assert db.session.query(PlannedTransaction).count() == 0


def test_create_planned_rejects_inactive_account(logged_in_client, app, test_user, planned_setup):
    _, category = planned_setup
    closed = Account(name="Zamknięte", bank_name="Bank", user_token=test_user.token, is_active=False)
    db.session.add(closed)
    db.session.commit()

    resp = logged_in_client.post('/api/planned-transactions/', json={
        'title': 'Na zamknięte', 'amount': '-1.00', 'account_id': closed.id,
        'category_id': category.id, 'execution_date': '2024-09-01',
    })
    assert resp.status_code == 400


def test_list_planned_returns_only_pending_sorted(logged_in_client, app, test_user, planned_setup):
    account, category = planned_setup
    p1 = PlannedTransaction(user_token=test_user.token, account_id=account.id, category_id=category.id,
                            title="Późniejsza", amount=Decimal("-10.00"),
                            execution_date=date(2024, 12, 1), status="pending")
    p2 = PlannedTransaction(user_token=test_user.token, account_id=account.id, category_id=category.id,
                            title="Wcześniejsza", amount=Decimal("-20.00"),
                            execution_date=date(2024, 8, 1), status="pending")
    p3 = PlannedTransaction(user_token=test_user.token, account_id=account.id, category_id=category.id,
                            title="Wykonana", amount=Decimal("-30.00"),
                            execution_date=date(2024, 7, 1), status="processed")
    db.session.add_all([p1, p2, p3])
    db.session.commit()

    resp = logged_in_client.get('/api/planned-transactions/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert [item['title'] for item in data] == ["Wcześniejsza", "Późniejsza"]  # tylko pending, rosnąco po dacie


def test_delete_planned_transaction(logged_in_client, app, test_user, planned_setup):
    account, category = planned_setup
    pt = PlannedTransaction(user_token=test_user.token, account_id=account.id, category_id=category.id,
                            title="Do usunięcia", amount=Decimal("-5.00"),
                            execution_date=date(2024, 10, 1), status="pending")
    db.session.add(pt)
    db.session.commit()
    pt_id = pt.id

    resp = logged_in_client.delete(f'/api/planned-transactions/{pt_id}')
    assert resp.status_code == 200
    assert db.session.get(PlannedTransaction, pt_id) is None
