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


def test_soft_delete_nonexistent_category_raises(app):
    with pytest.raises(ValueError):
        soft_delete_category('NieMaTakiej')


def test_soft_delete_targets_active_duplicate(app):
    """Przy duplikacie nazw (nieaktywna + aktywna) usuwana jest AKTYWNA — nie martwy rekord."""
    inactive = Category(name="Podwójna", type="expense", is_active=False)
    active = Category(name="Podwójna", type="expense", is_active=True)
    db.session.add_all([inactive, active])
    db.session.commit()

    soft_delete_category("Podwójna")

    db.session.expire_all()
    assert db.session.get(Category, active.id).is_active is False
    assert db.session.get(Category, inactive.id).is_active is False


def test_delete_nonexistent_category_via_api_returns_400(logged_in_client, app):
    resp = logged_in_client.delete('/api/categories/Widmo')
    assert resp.status_code == 400
