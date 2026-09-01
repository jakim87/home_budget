"""Testy zgłoszeń użytkowników.

Aplikacja webowa wyłącznie ZAPISUJE zgłoszenia — nie ma trasy, która by je
pokazywała. Odczyt i kasowanie idą przez CLI, czyli spod konta z dostępem do
serwera, dlatego testy dzielą się na dwie grupy: bariery na endpoincie zapisu
i zachowanie komend terminalowych.
"""
import pytest

from app import db
from app.models import Feedback, User
from app.services.feedback_service import create_feedback, list_feedback


def _wyslij(client, tresc='Wykres na dashboardzie nie ładuje się po zmianie miesiąca.', **reszta):
    return client.post('/api/feedback', json={'content': tresc, **reszta})


# --- Endpoint zapisu ---

def test_zalogowany_moze_wyslac_zgloszenie(logged_in_client, test_user_token):
    odpowiedz = _wyslij(logged_in_client, context='zakładka: Raporty · wersja: 0.9.0-beta')
    assert odpowiedz.status_code == 201

    zapisane = db.session.query(Feedback).filter_by(user_token=test_user_token).all()
    assert len(zapisane) == 1
    assert 'nie ładuje się' in zapisane[0].content
    assert zapisane[0].context == 'zakładka: Raporty · wersja: 0.9.0-beta'
    # User-Agent bierzemy z nagłówka żądania, nie od klienta w treści JSON.
    assert zapisane[0].user_agent is not None


def test_niezalogowany_nie_wysle(client):
    assert _wyslij(client).status_code in (302, 401)
    assert db.session.query(Feedback).count() == 0


def test_konto_demo_nie_moze_wysylac(app, client):
    """Demo jest publiczne — formularz dostępny z niego byłby anonimowym
    endpointem zapisu dla całego internetu."""
    from werkzeug.security import generate_password_hash
    db.session.add(User(username='demo', email='demo@example.invalid',
                        password_hash=generate_password_hash('demo-do-ogladania')))
    db.session.commit()

    client.post('/api/login', json={'username': 'demo', 'password': 'demo-do-ogladania'})
    assert _wyslij(client).status_code == 403
    assert db.session.query(Feedback).count() == 0


def test_za_krotka_tresc_odrzucona(logged_in_client):
    assert _wyslij(logged_in_client, tresc='ok').status_code == 400
    assert db.session.query(Feedback).count() == 0


def test_aplikacja_nie_udostepnia_zgloszen_przez_http(logged_in_client):
    """Odczyt jest wyłącznie z terminala. Gdyby ktoś kiedyś dodał trasę czytającą,
    ten test ma o tym przypomnieć — lista pokazuje treści WSZYSTKICH użytkowników."""
    _wyslij(logged_in_client)
    for sciezka in ('/zgloszenia', '/api/feedback', '/api/feedback/1'):
        odpowiedz = logged_in_client.get(sciezka)
        assert odpowiedz.status_code in (404, 405), f'{sciezka} nie powinno oddawać zgłoszeń'


# --- Serwis ---

def test_lista_od_najnowszego(app, test_user):
    for i in range(3):
        create_feedback(test_user.token, f'Zgłoszenie numer {i} z opisem problemu.')
    wszystkie = list_feedback()
    assert [z.id for z in wszystkie] == sorted([z.id for z in wszystkie], reverse=True)


def test_pusta_tresc_odrzucona_w_serwisie(app, test_user):
    """Serwis broni się sam — blueprint nie jest jedyną bramką."""
    with pytest.raises(ValueError):
        create_feedback(test_user.token, '   ')


# --- CLI ---

def test_cli_wypisuje_zgloszenia(app, test_user):
    create_feedback(test_user.token, 'Import wyciągu z mBanku gubi ostatnią transakcję.',
                    context='zakładka: Transakcje')
    wynik = app.test_cli_runner().invoke(args=['feedback-list'])

    assert wynik.exit_code == 0
    assert 'mBanku' in wynik.output
    assert 'testuser' in wynik.output
    assert 'zakładka: Transakcje' in wynik.output


def test_cli_bez_zgloszen(app):
    wynik = app.test_cli_runner().invoke(args=['feedback-list'])
    assert wynik.exit_code == 0
    assert 'Brak zgłoszeń' in wynik.output


def test_cli_wycina_znaki_sterujace(app, test_user):
    """Treść pisze użytkownik i trafia wprost na terminal — sekwencje ANSI
    pozwoliłyby ukryć albo podmienić fragment wyniku."""
    create_feedback(test_user.token, 'Zwykły tekst \x1b[31mCZERWONY\x1b[0m i \x07 dzwonek.')
    wynik = app.test_cli_runner().invoke(args=['feedback-list'])

    assert '\x1b' not in wynik.output
    assert '\x07' not in wynik.output
    assert 'CZERWONY' in wynik.output


def test_cli_usuwa_wskazane_zgloszenia(app, test_user):
    zostaje = create_feedback(test_user.token, 'Sensowna uwaga, która ma zostać w bazie.')
    smiec = create_feedback(test_user.token, 'asdfasdf test test test ignoruj to.')

    wynik = app.test_cli_runner().invoke(args=['feedback-delete', '--id', str(smiec.id), '--yes'])

    assert wynik.exit_code == 0
    pozostale = [z.id for z in db.session.query(Feedback).all()]
    assert pozostale == [zostaje.id]


def test_cli_bez_potwierdzenia_nic_nie_kasuje(app, test_user):
    """Bez --yes komenda pyta; odpowiedź „nie" zostawia bazę nietkniętą."""
    zgloszenie = create_feedback(test_user.token, 'Uwaga, której nie chcę stracić.')

    wynik = app.test_cli_runner().invoke(args=['feedback-delete', '--id', str(zgloszenie.id)], input='n\n')

    assert 'Przerwano' in wynik.output
    assert db.session.query(Feedback).count() == 1


def test_cli_delete_nieistniejacy_numer(app, test_user):
    create_feedback(test_user.token, 'Jedyne zgłoszenie w bazie, ma zostać.')
    wynik = app.test_cli_runner().invoke(args=['feedback-delete', '--id', '9999', '--yes'])

    assert wynik.exit_code == 0
    assert 'Nie znaleziono' in wynik.output
    assert db.session.query(Feedback).count() == 1
