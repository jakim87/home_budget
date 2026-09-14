"""Testy rejestracji, logowania i ochrony API przed dostępem bez uwierzytelnienia."""
from app import db
from app.models import User


def test_register_success(client, app):
    resp = client.post('/api/register', json={
        'username': 'nowy_user', 'email': 'nowy@test.com', 'password': 'sekret12345',
    })
    assert resp.status_code == 201
    user = db.session.query(User).filter_by(username='nowy_user').first()
    assert user is not None
    assert user.password_hash != 'sekret12345'  # hasło zahaszowane, nie plaintext
    assert user.token  # token UUID nadany automatycznie


def test_register_duplicate_username_rejected(client, app, test_user):
    resp = client.post('/api/register', json={
        'username': 'testuser', 'email': 'inny@test.com', 'password': 'sekret12345',
    })
    assert resp.status_code == 400


def test_register_duplicate_email_rejected(client, app, test_user):
    resp = client.post('/api/register', json={
        'username': 'zupelnie_inny', 'email': 'test@test.com', 'password': 'sekret12345',
    })
    assert resp.status_code == 400


def test_register_short_password_rejected(client, app):
    resp = client.post('/api/register', json={
        'username': 'krotki', 'email': 'krotki@test.com', 'password': '123',
    })
    assert resp.status_code == 400


def test_register_password_ponizej_10_znakow_odrzucone(client, app):
    """Granica wymogu dlugosci: 9 znakow odrzucone, 10 przyjete."""
    resp = client.post('/api/register', json={
        'username': 'dziewiec', 'email': 'dziewiec@test.com', 'password': 'a' * 9,
    })
    assert resp.status_code == 400

    resp = client.post('/api/register', json={
        'username': 'dziesiec', 'email': 'dziesiec@test.com', 'password': 'a' * 10,
    })
    assert resp.status_code == 201


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


def test_zmiana_hasla_uniewaznia_istniejace_sesje(logged_in_client, test_user):
    """Reset/zmiana hasła musi wyrzucić już otwarte sesje (A9).

    Sesja to podpisane ciasteczko z identyfikatorem użytkownika. Jeśli identyfikator
    nie zależy od hasła, przejęta sesja przeżywa reset-password — jedyną obroną była
    zmiana SECRET_KEY (wylogowuje wszystkich). Po poprawce ciasteczko niesie znacznik
    wersji hasła, więc zmiana hasła unieważnia stare sesje punktowo.
    """
    from werkzeug.security import generate_password_hash
    from app import load_user

    assert logged_in_client.get('/api/me').status_code == 200, "sesja powinna być aktywna"
    # Identyfikator z ciasteczka sesji — to on jest przekazywany do load_user przy
    # każdym żądaniu i to on decyduje, czy sesja nadal obowiązuje.
    with logged_in_client.session_transaction() as sess:
        cookie_uid = sess['_user_id']
    assert load_user(cookie_uid) is not None, "przed zmianą hasła sesja jest ważna"

    test_user.password_hash = generate_password_hash('calkiem-nowe-haslo-123')
    db.session.commit()
    # W produkcji kolejne żądanie ma świeżą sesję DB (teardown robi remove()), więc
    # load_user czyta nowy hash z bazy. Testy trzymają jedną sesję przez cały czas —
    # expire_all() odtwarza ten świeży odczyt, bez którego widać stary obiekt z identity map.
    db.session.expire_all()

    # Sedno A9: identyfikator wystawiony przy starym haśle nie waliduje się już wobec nowego.
    assert load_user(cookie_uid) is None, "stara sesja musi przestać działać po zmianie hasła"
