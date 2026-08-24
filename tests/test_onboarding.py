"""Onboarding nowego użytkownika: co dostaje zaraz po rejestracji.

Bez kategorii startowych nowy użytkownik nie może dodać ani jednej transakcji —
transakcja wymaga kategorii, a jedyna globalna to techniczne "Uzgadnianie salda".
"""
from app import db
from app.models import Category, User
from app.services.category_service import list_active


def _zarejestruj(client, username='nowa', email='nowa@example.com'):
    resp = client.post('/api/register', json={
        'username': username, 'email': email, 'password': 'DlugieHaslo123',
    })
    assert resp.status_code == 201, resp.get_json()
    return db.session.query(User).filter_by(username=username).first()


def test_nowy_uzytkownik_dostaje_kategorie_startowe(client, app):
    user = _zarejestruj(client)

    wlasne = db.session.query(Category).filter_by(user_token=user.token, is_active=True).all()
    assert len(wlasne) > 0, "nowy użytkownik nie ma żadnych własnych kategorii"


def test_kategorie_startowe_zawieraja_przelew_wewnetrzny(client, app):
    """Bez kategorii typu 'transfer' mechanizm przelewów między kontami nie zadziała."""
    user = _zarejestruj(client)

    transfery = db.session.query(Category).filter_by(
        user_token=user.token, type='transfer', is_active=True
    ).all()
    assert len(transfery) >= 1, "brak kategorii typu transfer — przelewy wewnętrzne nie zadziałają"
    assert any(c.name == 'Przelew wewnętrzny' for c in transfery)


def test_kategorie_startowe_pokrywaja_wydatki_i_przychody(client, app):
    user = _zarejestruj(client)
    typy = {c.type for c in db.session.query(Category).filter_by(user_token=user.token).all()}

    assert 'expense' in typy
    assert 'income' in typy


def test_kategorie_startowe_naleza_do_wlasciciela_nie_sa_globalne(client, app):
    """Kategorie startowe muszą być prywatne — globalnych użytkownik nie może usunąć."""
    user = _zarejestruj(client)
    wlasne = db.session.query(Category).filter_by(user_token=user.token).all()

    assert all(c.user_token == user.token for c in wlasne)
    assert all(c.is_system_category is False for c in wlasne)


def test_dwaj_uzytkownicy_dostaja_wlasne_kopie_kategorii(client, app):
    """Kategorie jednego użytkownika nie są współdzielone z drugim."""
    a = _zarejestruj(client, 'pierwsza', 'pierwsza@example.com')
    b = _zarejestruj(client, 'druga', 'druga@example.com')

    kat_a = {c.name for c in db.session.query(Category).filter_by(user_token=a.token).all()}
    kat_b = {c.name for c in db.session.query(Category).filter_by(user_token=b.token).all()}

    assert kat_a == kat_b, "obaj powinni dostać ten sam zestaw nazw"
    ids_a = {c.id for c in db.session.query(Category).filter_by(user_token=a.token).all()}
    ids_b = {c.id for c in db.session.query(Category).filter_by(user_token=b.token).all()}
    assert ids_a.isdisjoint(ids_b), "to muszą być osobne rekordy, nie te same"


def test_uzytkownik_widzi_swoje_kategorie_startowe_przez_list_active(client, app):
    """Sprawdzenie przez tę samą ścieżkę, z której korzysta /api/init."""
    user = _zarejestruj(client)
    widoczne = list_active(user.token)

    nazwy = {c.name for c in widoczne}
    assert 'Zakupy spożywcze' in nazwy
    assert 'Wynagrodzenie' in nazwy


def test_pelna_sciezka_nowego_uzytkownika(client, app):
    """Od rejestracji do pierwszej transakcji — bez ani jednego kroku w bazie ręcznie.

    Odtwarza dokładnie to, co robi frontend po założeniu konta (15_init.js):
    rejestracja -> logowanie -> utworzenie konta -> uzgodnienie salda -> transakcja.
    """
    resp = client.post('/api/register', json={
        'username': 'swiezak', 'email': 'swiezak@example.com', 'password': 'DlugieHaslo123',
    })
    assert resp.status_code == 201

    assert client.post('/api/login', json={
        'username': 'swiezak', 'password': 'DlugieHaslo123',
    }).status_code == 200

    # Kreator pierwszego konta
    resp = client.post('/api/accounts/', json={'name': 'Portfel', 'bank_name': '', 'is_default': True})
    assert resp.status_code == 201
    account_id = resp.get_json()['id']

    # Saldo startowe idzie przez uzgodnienie, nie przez pole balance
    resp = client.post(f'/api/accounts/{account_id}/reconcile',
                       json={'new_balance': 500.00, 'comment': 'Saldo początkowe'})
    assert resp.status_code == 200

    # Nowy użytkownik może od razu dodać transakcję na kategorii startowej
    resp = client.post('/api/transactions', json={
        'title': 'Zakupy', 'amount': -50.00, 'date': '2026-08-24',
        'account_id': account_id, 'category': 'Zakupy spożywcze',
    })
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()['category'] == 'Zakupy spożywcze'

    # /api/init widzi komplet: kategorie, konto i transakcję
    dane = client.get('/api/init').get_json()
    assert len(dane['categories']) >= 10
    assert len(dane['accounts']) == 1
    assert dane['accounts'][0]['balance'] == 450.00  # 500 - 50
    assert len(dane['transactions']) == 2  # uzgodnienie salda + zakupy
