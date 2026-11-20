"""Komunikat o zmianie dokumentów prawnych: baner w /api/init i potwierdzenie."""
from datetime import date, datetime, timedelta, timezone

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


def test_dziennik_zmian_jest_od_najnowszej_i_ma_streszczenia():
    wpisy = lns.ZMIANY_DOKUMENTOW
    daty = [w['data'] for w in wpisy]
    assert daty == sorted(daty, reverse=True) and len(set(daty)) == len(daty)
    assert lns.DOCS_LAST_UPDATED_DATE == daty[0]
    for w in wpisy:
        assert w['punkty'] and all(p.strip() for p in w['punkty'])
        assert w['od'] >= w['data']


def test_baner_zawiera_streszczenie_tylko_nowszych_zmian(logged_in_client, test_user_id):
    db.session.get(User, test_user_id).legal_docs_ack = lns.ZMIANY_DOKUMENTOW[1]['data']
    db.session.commit()
    zmiany = _stan(logged_in_client)['changes']
    assert [z['date'] for z in zmiany] == [lns.format_pl(lns.ZMIANY_DOKUMENTOW[0]['data'])]
    assert zmiany[0]['punkty'] == list(lns.ZMIANY_DOKUMENTOW[0]['punkty'])


def test_uzytkownik_bez_potwierdzenia_dostaje_cala_historie(logged_in_client):
    assert len(_stan(logged_in_client)['changes']) == len(lns.ZMIANY_DOKUMENTOW)


def test_po_potwierdzeniu_brak_zmian_w_odpowiedzi(logged_in_client):
    logged_in_client.post('/api/legal-ack')
    assert _stan(logged_in_client)['changes'] == []


def test_data_wejscia_w_zycie_tylko_dopoki_w_przyszlosci():
    od = lns.ZMIANY_DOKUMENTOW[0]['od']
    assert lns.obowiazuje_od(od - timedelta(days=1)) == lns.format_pl(od)
    assert lns.obowiazuje_od(od) is None


def test_strona_regulaminu_pokazuje_date_wejscia_w_zycie(client, monkeypatch):
    monkeypatch.setattr(lns, 'obowiazuje_od', lambda dzis=None: '27 listopada 2026')
    assert 'zmiany obowiązują od 27 listopada 2026' in client.get('/regulamin').get_data(as_text=True)
def test_potwierdzenie_zapisuje_moment_klikniecia(logged_in_client, test_user_id):
    assert db.session.get(User, test_user_id).legal_docs_ack_at is None
    logged_in_client.post('/api/legal-ack')
    kiedy = db.session.get(User, test_user_id).legal_docs_ack_at
    assert kiedy is not None and abs((datetime.now(timezone.utc).replace(tzinfo=None) - kiedy).total_seconds()) < 60


def test_rejestracja_nie_udaje_klikniecia(client):
    client.post('/api/register', json={
        'username': 'nowy2', 'email': 'nowy2@test.com', 'password': 'Haslo1234!x'})
    u = db.session.query(User).filter_by(username='nowy2').one()
    assert u.legal_docs_ack == lns.DOCS_LAST_UPDATED_DATE and u.legal_docs_ack_at is None


def test_lista_potwierdzen_rozroznia_trzy_stany(app, client, test_user, other_user):
    client.post('/api/register', json={
        'username': 'nowy3', 'email': 'nowy3@test.com', 'password': 'Haslo1234!x'})
    login_as(client, 'testuser')
    client.post('/api/legal-ack')
    stany = {w['username']: w['stan'] for w in lns.lista_potwierdzen()}
    assert stany == {'testuser': 'potwierdzil', 'intruz': 'brak', 'nowy3': 'rejestracja'}
    assert [w['username'] for w in lns.lista_potwierdzen(tylko_bez_potwierdzenia=True)] == ['intruz']


def test_lista_potwierdzen_pomija_demo(app, test_user):
    app.config['DEMO_USERNAME'] = 'testuser'
    assert lns.lista_potwierdzen() == []


def test_komenda_legal_ack_list(app, logged_in_client):
    logged_in_client.post('/api/legal-ack')
    wynik = app.test_cli_runner().invoke(args=['legal-ack-list'])
    assert wynik.exit_code == 0
    assert 'testuser' in wynik.output and 'potwierdzono' in wynik.output
    assert 'potwierdzili: 1' in wynik.output
    assert 'email' not in wynik.output.lower()
