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
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

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
def test_user_id(app):
    """Fixture zwracający ID użytkownika testowego (potrzebne do Flask-Login)."""
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        return user.id

@pytest.fixture
def test_user_token(app):
    """Fixture zwracający token użytkownika testowego (do filtrowania danych finansowych)."""
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        return user.token
