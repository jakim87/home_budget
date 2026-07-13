"""Testy rejestracji, logowania i ochrony API przed dostępem bez uwierzytelnienia."""
from app import db
from app.models import User


def test_register_success(client, app):
    resp = client.post('/api/register', json={
        'username': 'nowy_user', 'email': 'nowy@test.com', 'password': 'sekret123',
    })
    assert resp.status_code == 201
    user = db.session.query(User).filter_by(username='nowy_user').first()
    assert user is not None
    assert user.password_hash != 'sekret123'  # hasło zahaszowane, nie plaintext
    assert user.token  # token UUID nadany automatycznie


def test_register_duplicate_username_rejected(client, app, test_user):
    resp = client.post('/api/register', json={
        'username': 'testuser', 'email': 'inny@test.com', 'password': 'sekret123',
    })
    assert resp.status_code == 400


def test_register_duplicate_email_rejected(client, app, test_user):
    resp = client.post('/api/register', json={
        'username': 'zupelnie_inny', 'email': 'test@test.com', 'password': 'sekret123',
    })
    assert resp.status_code == 400


def test_register_short_password_rejected(client, app):
    resp = client.post('/api/register', json={
        'username': 'krotki', 'email': 'krotki@test.com', 'password': '123',
    })
    assert resp.status_code == 400


def test_login_wrong_password_returns_401(client, app, test_user):
    resp = client.post('/api/login', json={'username': 'testuser', 'password': 'zle_haslo'})
    assert resp.status_code == 401


def test_login_by_email(client, app, test_user):
    resp = client.post('/api/login', json={'username': 'test@test.com', 'password': 'password'})
    assert resp.status_code == 200


def test_api_requires_authentication(client, app):
    """Kluczowe endpointy bez zalogowania → 401 (JSON, nie redirect)."""
    protected = [
        ('get', '/api/init'),
        ('post', '/api/transactions'),
        ('get', '/api/staging/pending'),
        ('get', '/api/recurring-transactions/'),
        ('get', '/api/planned-transactions/'),
    ]
    for method, url in protected:
        resp = getattr(client, method)(url, json={})
        assert resp.status_code == 401, f"{method.upper()} {url} nie wymaga logowania!"


def test_me_returns_current_user(logged_in_client, app, test_user):
    resp = logged_in_client.get('/api/me')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['username'] == 'testuser'
