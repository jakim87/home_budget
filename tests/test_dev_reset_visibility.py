"""Przycisk „Wyczyść dane testowe" ma być widoczny dokładnie tam, gdzie działa endpoint.

Wcześniej kosz widniał w nagłówku zawsze — także na produkcji, gdzie dev_bp nie jest
zarejestrowany i kliknięcie kończy się 404.
"""
from app import create_app, db
from tests.conftest import TestConfig


class ProdLikeConfig(TestConfig):
    """Konfiguracja bez trybu dev — jak na serwerze produkcyjnym."""
    TESTING = False
    DEBUG = False


def test_przycisk_resetu_widoczny_w_trybie_testowym(client, app):
    html = client.get('/').get_data(as_text=True)
    assert 'resetDevData()' in html
    assert app.config['DEV_RESET_ENABLED'] is True


def test_przycisk_resetu_ukryty_bez_trybu_dev(monkeypatch):
    """Bez debug/testing i bez ENABLE_DEV_RESET kosz znika z nagłówka."""
    monkeypatch.delenv('ENABLE_DEV_RESET', raising=False)
    app = create_app(ProdLikeConfig)
    with app.app_context():
        db.create_all()
        assert app.config['DEV_RESET_ENABLED'] is False

        html = app.test_client().get('/').get_data(as_text=True)
        assert 'resetDevData()' not in html

        # Przycisk zniknął, bo endpoint faktycznie nie istnieje — nie odwrotnie.
        assert app.test_client().post('/api/dev/reset').status_code == 404
        db.drop_all()


def test_przycisk_resetu_wraca_przy_enable_dev_reset(monkeypatch):
    """Jawna zmienna ENABLE_DEV_RESET=1 przywraca i endpoint, i przycisk."""
    monkeypatch.setenv('ENABLE_DEV_RESET', '1')
    app = create_app(ProdLikeConfig)
    with app.app_context():
        db.create_all()
        assert app.config['DEV_RESET_ENABLED'] is True
        assert 'resetDevData()' in app.test_client().get('/').get_data(as_text=True)
        db.drop_all()
