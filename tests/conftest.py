import pytest
import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app, db
from config import Config
from app.models import User
from werkzeug.security import generate_password_hash

class TestConfig(Config):
    TESTING = True
    # Domyślnie in-memory SQLite (szybkie uruchomienia lokalne). Ustawienie zmiennej
    # środowiskowej TEST_DATABASE_URL (np. w CI) uruchamia TEN SAM pakiet testów na
    # PostgreSQL — wykrywa rozjazdy zachowań SQLite vs Postgres (constraints, typy).
    # UWAGA: TEST_DATABASE_URL musi wskazywać na osobną bazę testową (tabele są
    # tworzone i KASOWANE przy każdym teście) — nigdy na produkcyjną budget_db!
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user(app):
    """Użytkownik testowy (testuser / password). Wspólne źródło dla test_user_id
    i test_user_token — dzięki temu można ich używać razem w jednym teście."""
    user = User(username="testuser", email="test@test.com",
                password_hash=generate_password_hash("password"))
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def test_user_id(test_user):
    """ID użytkownika testowego (potrzebne do Flask-Login)."""
    return test_user.id

@pytest.fixture
def test_user_token(test_user):
    """Token użytkownika testowego (do filtrowania danych finansowych)."""
    return test_user.token

@pytest.fixture
def other_user(app):
    """Drugi użytkownik — do testów autoryzacji (próby dostępu do cudzych zasobów)."""
    user = User(username="intruz", email="intruz@test.com",
                password_hash=generate_password_hash("password"))
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def logged_in_client(client, test_user):
    """Klient HTTP zalogowany jako testuser — zastępuje kopiowany login_user_helper."""
    client.post('/api/login', json={'username': 'testuser', 'password': 'password'})
    return client

def login_as(client, username, password="password"):
    """Pomocnik: przelogowanie klienta na innego użytkownika (testy autoryzacji)."""
    client.post('/api/logout')
    return client.post('/api/login', json={'username': username, 'password': password})
