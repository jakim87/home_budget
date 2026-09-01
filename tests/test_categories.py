"""Testy kategorii — duplikaty nazw i krawędzie miękkiego usuwania."""
from app import db
from app.models import Category
from app.services.category_service import soft_delete_category

import pytest


def test_create_duplicate_active_category_rejected(logged_in_client, app):
    resp1 = logged_in_client.post('/api/categories', json={'name': 'Paliwo', 'type': 'expense'})
    assert resp1.status_code == 201

    resp2 = logged_in_client.post('/api/categories', json={'name': 'Paliwo', 'type': 'expense'})
    assert resp2.status_code == 400
    assert db.session.query(Category).filter_by(name='Paliwo').count() == 1


def test_recreate_category_after_soft_delete(logged_in_client, app):
    """Po miękkim usunięciu można utworzyć kategorię o tej samej nazwie."""
    logged_in_client.post('/api/categories', json={'name': 'Hobby', 'type': 'expense'})
    logged_in_client.delete('/api/categories/Hobby')

    resp = logged_in_client.post('/api/categories', json={'name': 'Hobby', 'type': 'expense'})
    assert resp.status_code == 201
    cats = db.session.query(Category).filter_by(name='Hobby').all()
    assert len(cats) == 2
    assert sorted(c.is_active for c in cats) == [False, True]


def test_soft_delete_nonexistent_category_raises(app, test_user_token):
    with pytest.raises(ValueError):
        soft_delete_category(test_user_token, 'NieMaTakiej')


def test_soft_delete_targets_active_duplicate(app, test_user_token):
    """Przy duplikacie nazw (nieaktywna + aktywna) usuwana jest AKTYWNA — nie martwy rekord."""
    inactive = Category(name="Podwójna", type="expense", is_active=False, user_token=test_user_token)
    active = Category(name="Podwójna", type="expense", is_active=True, user_token=test_user_token)
    db.session.add_all([inactive, active])
    db.session.commit()

    soft_delete_category(test_user_token, "Podwójna")

    db.session.expire_all()
    assert db.session.get(Category, active.id).is_active is False
    assert db.session.get(Category, inactive.id).is_active is False


def test_global_category_not_deletable_by_user(app, test_user_token):
    """Kategorii globalnej (user_token IS NULL) nie usuwa żaden użytkownik."""
    globalna = Category(name="Uzgadnianie salda", type="system_reconciliation",
                        is_system_category=True, user_token=None)
    db.session.add(globalna)
    db.session.commit()

    with pytest.raises(ValueError):
        soft_delete_category(test_user_token, "Uzgadnianie salda")

    db.session.expire_all()
    assert db.session.get(Category, globalna.id).is_active is True


def test_user_cannot_delete_other_users_category(app, test_user_token, other_user):
    """Kategoria innego użytkownika jest poza zasięgiem — to był realny problem."""
    cudza = Category(name="Cudza", type="expense", user_token=other_user.token)
    db.session.add(cudza)
    db.session.commit()

    with pytest.raises(ValueError):
        soft_delete_category(test_user_token, "Cudza")

    db.session.expire_all()
    assert db.session.get(Category, cudza.id).is_active is True


def test_delete_nonexistent_category_via_api_returns_400(logged_in_client, app):
    resp = logged_in_client.delete('/api/categories/Widmo')
    assert resp.status_code == 400


def test_create_category_zwraca_id_jak_api_init(logged_in_client, app):
    """POST musi oddać ten sam kształt co /api/init — front robi categories.push(saved)
    i renderuje kategorię w selektach po ID. Bez 'id' trafiała tam jako value='undefined'."""
    resp = logged_in_client.post('/api/categories', json={'name': 'Prezenty', 'type': 'expense'})
    assert resp.status_code == 201
    body = resp.get_json()
    assert set(body) == {'id', 'name', 'type', 'is_system_category'}
    assert body['id'] == db.session.query(Category).filter_by(name='Prezenty').one().id
