import pytest
import os
import sys

# Upewniamy się, że główny katalog jest w ścieżce (podobnie jak w test_db.py)
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app, db
from config import Config
from app.models import User
from werkzeug.security import generate_password_hash

class TestConfig(Config):
    TESTING = True
    # Używamy bazy danych SQLite w pamięci RAM, aby testy były błyskawiczne i izolowane
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()  # Tworzy struktury tabel przed testem
        yield app
        db.session.remove()
        db.drop_all()    # Ciszczy bazę po teście

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user_id(app):
    """Fixture przygotowujący użytkownika testowego i zwracający jego ID."""
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        return user.id