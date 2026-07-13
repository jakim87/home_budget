"""Testy kontrahentów — wcześniej zero pokrycia serwisu contractor_service."""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import Category, Contractor, TransactionStaging
from app.services.budget_service import accept_staging_contractor


@pytest.fixture
def cat_food(app):
    cat = Category(name="Jedzenie", type="expense")
    db.session.add(cat)
    db.session.commit()
    return cat


def test_create_contractor_with_category(logged_in_client, app, cat_food):
    resp = logged_in_client.post('/api/contractors', json={
        'name': 'Lidl', 'rules': 'lidl', 'category': 'Jedzenie',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['name'] == 'Lidl'
    assert data['default_category_id'] == cat_food.id
    assert data['default_category_name'] == 'Jedzenie'


def test_partial_update_preserves_default_category(logged_in_client, app, test_user, cat_food):
    """REGRESJA: PUT bez pola 'category' nie może kasować domyślnej kategorii kontrahenta."""
    cont = Contractor(name="Rossmann", user_token=test_user.token, default_category_id=cat_food.id)
    db.session.add(cont)
    db.session.commit()

    resp = logged_in_client.put(f'/api/contractors/{cont.id}', json={'rules': 'rossmann, drogeria'})

    assert resp.status_code == 200
    db.session.expire_all()
    updated = db.session.get(Contractor, cont.id)
    assert updated.mapping_rules == 'rossmann, drogeria'
    assert updated.default_category_id == cat_food.id  # NIE wyzerowane
    assert resp.get_json()['default_category_name'] == 'Jedzenie'


def test_update_with_category_changes_it(logged_in_client, app, test_user, cat_food):
    other_cat = Category(name="Chemia", type="expense")
    db.session.add(other_cat)
    db.session.commit()
    cont = Contractor(name="Rossmann", user_token=test_user.token, default_category_id=cat_food.id)
    db.session.add(cont)
    db.session.commit()

    resp = logged_in_client.put(f'/api/contractors/{cont.id}', json={'category': 'Chemia'})

    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Contractor, cont.id).default_category_id == other_cat.id


def test_soft_delete_contractor(logged_in_client, app, test_user):
    cont = Contractor(name="Do usunięcia", user_token=test_user.token)
    db.session.add(cont)
    db.session.commit()

    resp = logged_in_client.delete(f'/api/contractors/{cont.id}')
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Contractor, cont.id).is_active is False


def test_soft_delete_nonexistent_contractor_returns_error(logged_in_client, app):
    resp = logged_in_client.delete('/api/contractors/99999')
    assert resp.status_code == 400


def test_accept_staging_contractor_reuses_existing(app, test_user):
    """Zaakceptowanie sugestii z nazwą istniejącego aktywnego kontrahenta — reuse, nie duplikat."""
    existing = Contractor(name="Orlen", user_token=test_user.token)
    stg = TransactionStaging(date=date(2024, 5, 1), amount=Decimal("-200.00"), title="Paliwo",
                             status="pending", user_token=test_user.token,
                             suggested_contractor_name="Orlen")
    db.session.add_all([existing, stg])
    db.session.commit()

    result = accept_staging_contractor(test_user.token, stg.id, "Orlen")

    assert result['contractor_id'] == existing.id
    assert db.session.query(Contractor).filter_by(name="Orlen").count() == 1
    db.session.expire_all()
    refreshed = db.session.get(TransactionStaging, stg.id)
    assert refreshed.proposed_contractor_id == existing.id
    assert refreshed.suggested_contractor_name is None


def test_accept_staging_contractor_creates_new(app, test_user):
    stg = TransactionStaging(date=date(2024, 5, 2), amount=Decimal("-99.00"), title="Nowy sklep",
                             status="pending", user_token=test_user.token,
                             suggested_contractor_name="Nowy Sklep")
    db.session.add(stg)
    db.session.commit()

    result = accept_staging_contractor(test_user.token, stg.id, "Nowy Sklep")

    created = db.session.query(Contractor).filter_by(name="Nowy Sklep").one()
    assert result['contractor_id'] == created.id
    assert created.mapping_rules == "nowy sklep"  # reguła mapowania z nazwy (lowercase)
