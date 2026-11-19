"""Komunikat o zmianie dokumentów prawnych: baner w /api/init i potwierdzenie."""
from datetime import date, timedelta

from app import db
from app.models import User
from app.services import legal_notice_service as lns
from tests.conftest import login_as


def _stan(client):
    return client.get('/api/init').get_json()['legal_notice']


def test_dotychczasowy_uzytkownik_widzi_baner_z_data(logged_in_client):
    stan = _stan(logged_in_client)
    assert stan['show'] is True
    assert stan['updated'] == lns.format_pl(lns.DOCS_LAST_UPDATED_DATE)


def test_potwierdzenie_zapisuje_date_i_chowa_baner(logged_in_client, test_user_id):
    resp = logged_in_client.post('/api/legal-ack')
    assert resp.status_code == 200
    assert db.session.get(User, test_user_id).legal_docs_ack == lns.DOCS_LAST_UPDATED_DATE
    assert _stan(logged_in_client)['show'] is False


def test_nowsza_data_dokumentow_pokazuje_baner_ponownie(logged_in_client, test_user_id, monkeypatch):
    logged_in_client.post('/api/legal-ack')
    monkeypatch.setattr(lns, 'DOCS_LAST_UPDATED_DATE', lns.DOCS_LAST_UPDATED_DATE + timedelta(days=1))
    assert _stan(logged_in_client)['show'] is True


def test_starsza_potwierdzona_data_pokazuje_baner(logged_in_client, test_user_id):
    db.session.get(User, test_user_id).legal_docs_ack = date(2020, 1, 1)
    db.session.commit()
    assert _stan(logged_in_client)['show'] is True


def test_nowy_uzytkownik_nie_widzi_banera_po_rejestracji(client):
    client.post('/api/register', json={
        'username': 'nowy', 'email': 'nowy@test.com', 'password': 'Haslo1234!x'})
    login_as(client, 'nowy', 'Haslo1234!x')
    assert _stan(client)['show'] is False


def test_potwierdzenie_wymaga_logowania(client):
    assert client.post('/api/legal-ack').status_code == 401


def test_konto_demo_nie_widzi_banera_i_nie_zapisuje(app, client):
    app.config['DEMO_USERNAME'] = 'demo'
    from werkzeug.security import generate_password_hash
    db.session.add(User(username='demo', email='demo@test.com',
                        password_hash=generate_password_hash('password')))
    db.session.commit()
    login_as(client, 'demo')
    assert _stan(client)['show'] is False
    assert client.post('/api/legal-ack').status_code == 403
    assert db.session.query(User).filter_by(username='demo').one().legal_docs_ack is None


def test_strony_prawne_pokazuja_te_sama_date(client):
    tekst = lns.format_pl(lns.DOCS_LAST_UPDATED_DATE)
    assert tekst in client.get('/regulamin').get_data(as_text=True)
    assert tekst in client.get('/polityka-prywatnosci').get_data(as_text=True)
