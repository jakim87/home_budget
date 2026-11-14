"""Zapisane widoki zakładki Wnioski i ulubione konta.

Widok to nazwa + konfiguracja filtrów (okres względny, konta, kategorie,
kontrahenci po ID, co liczyć, jak pokazać). Konfiguracja przychodzi od klienta,
więc serwer przepuszcza ją przez schemat: nieznany klucz albo zła wartość = 400,
a do bazy trafia tylko to, co schemat zna.
"""
import json
from decimal import Decimal

import pytest

from app import db
from app.models import Account, SavedView

CFG = {
    'okres': {'typ': 'n', 'n': 6},
    'konta': [],
    'kategorie': [3, 1],
    'kontrahenci': [],
    'liczy': 'wydatki',
    'pokaz': 'czas',
    'sald': 'auto',
    'ulubione': False,
}


def _widoki(user_token):
    db.session.expire_all()
    return db.session.query(SavedView).filter_by(user_token=user_token).order_by(SavedView.id).all()


# --- Zapis, zmiana, usunięcie ---

def test_zapis_widoku(logged_in_client, test_user_token):
    resp = logged_in_client.post('/api/views', json={'name': 'Jedzenie', 'config': CFG})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['name'] == 'Jedzenie'
    assert body['config']['kategorie'] == [1, 3]  # posortowane — porównanie „zmieniony?" na froncie

    [w] = _widoki(test_user_token)
    assert w.name == 'Jedzenie'
    assert json.loads(w.config)['okres'] == {'typ': 'n', 'n': 6}


def test_zmiana_widoku(logged_in_client, test_user_token):
    vid = logged_in_client.post('/api/views', json={'name': 'Jedzenie', 'config': CFG}).get_json()['id']
    nowa = {**CFG, 'pokaz': 'kontrahenci', 'ulubione': True}
    resp = logged_in_client.put(f'/api/views/{vid}', json={'name': 'Jedzenie 2', 'config': nowa})
    assert resp.status_code == 200
    [w] = _widoki(test_user_token)
    assert w.name == 'Jedzenie 2'
    assert json.loads(w.config)['pokaz'] == 'kontrahenci'
    assert json.loads(w.config)['ulubione'] is True


def test_usuniecie_widoku(logged_in_client, test_user_token):
    vid = logged_in_client.post('/api/views', json={'name': 'Jedzenie', 'config': CFG}).get_json()['id']
    assert logged_in_client.delete(f'/api/views/{vid}').status_code == 200
    assert _widoki(test_user_token) == []
    assert logged_in_client.delete(f'/api/views/{vid}').status_code == 404


def test_widoki_w_init(logged_in_client):
    logged_in_client.post('/api/views', json={'name': 'Jedzenie', 'config': CFG})
    data = logged_in_client.get('/api/init').get_json()
    [w] = data['saved_views']
    assert w['name'] == 'Jedzenie'
    assert w['config']['liczy'] == 'wydatki'


# --- Walidacja ---

@pytest.mark.parametrize('zly', [
    {**CFG, 'tajne': 1},                         # nieznany klucz
    {**CFG, 'okres': {'typ': 'n', 'n': 5}},      # okres spoza listy
    {**CFG, 'okres': {'typ': 'od-do'}},
    {**CFG, 'okres': {'typ': 'miesiac', 'x': 1}},
    {**CFG, 'liczy': 'wszystko'},
    {**CFG, 'pokaz': 'mapa'},
    {**CFG, 'sald': 'kolo'},
    {**CFG, 'konta': ['1']},                      # ID tylko jako liczby
    {**CFG, 'konta': [10**20]},                   # ID w zakresie kolumny (inaczej megabajty w bazie)
    {**CFG, 'kategorie': [0]},
    {**CFG, 'ulubione': 1},                       # 1 to nie True
    {**CFG, 'kategorie': list(range(501))},       # górna granica listy
    {**CFG, 'ulubione': 'tak'},
    {**CFG, 'dzien': 14},                         # dnia nie zapisujemy (decyzja 16)
])
def test_zla_konfiguracja_odrzucona(logged_in_client, test_user_token, zly):
    resp = logged_in_client.post('/api/views', json={'name': 'Zły', 'config': zly})
    assert resp.status_code == 400
    assert _widoki(test_user_token) == []


def test_brak_konfiguracji_i_nazwy(logged_in_client, test_user_token):
    assert logged_in_client.post('/api/views', json={'name': 'X'}).status_code == 400
    assert logged_in_client.post('/api/views', json={'name': '   ', 'config': CFG}).status_code == 400
    assert logged_in_client.post('/api/views', json={'name': 'x' * 61, 'config': CFG}).status_code == 400
    assert _widoki(test_user_token) == []


def test_brakujace_pola_dostaja_domyslne(logged_in_client):
    resp = logged_in_client.post('/api/views', json={'name': 'Minimum', 'config': {'pokaz': 'salda'}})
    assert resp.status_code == 201
    cfg = resp.get_json()['config']
    assert cfg['okres'] == {'typ': 'miesiac'}
    assert cfg['konta'] == [] and cfg['ulubione'] is False and cfg['liczy'] == 'oba'


def test_nazwa_niepowtarzalna_bez_wielkosci_liter(logged_in_client, test_user_token):
    logged_in_client.post('/api/views', json={'name': 'Jedzenie', 'config': CFG})
    resp = logged_in_client.post('/api/views', json={'name': ' jedzenie ', 'config': CFG})
    assert resp.status_code == 400
    assert len(_widoki(test_user_token)) == 1


def test_nazwa_widoku_wbudowanego_zajeta(logged_in_client, test_user_token):
    resp = logged_in_client.post('/api/views', json={'name': 'Miesiąc w liczbach', 'config': CFG})
    assert resp.status_code == 400
    assert _widoki(test_user_token) == []


def test_zmiana_na_nazwe_innego_widoku_odrzucona(logged_in_client, test_user_token):
    logged_in_client.post('/api/views', json={'name': 'A', 'config': CFG})
    vid = logged_in_client.post('/api/views', json={'name': 'B', 'config': CFG}).get_json()['id']
    assert logged_in_client.put(f'/api/views/{vid}', json={'name': 'a', 'config': CFG}).status_code == 400
    # Ta sama nazwa przy zapisie zmian we własnym widoku jest w porządku.
    assert logged_in_client.put(f'/api/views/{vid}', json={'name': 'B', 'config': CFG}).status_code == 200
    assert [w.name for w in _widoki(test_user_token)] == ['A', 'B']


def test_limit_siedmiu_widokow(logged_in_client, test_user_token):
    for i in range(7):
        assert logged_in_client.post('/api/views', json={'name': f'W{i}', 'config': CFG}).status_code == 201
    resp = logged_in_client.post('/api/views', json={'name': 'Ósmy', 'config': CFG})
    assert resp.status_code == 400
    assert 'Usuń któryś' in resp.get_json()['error']
    assert len(_widoki(test_user_token)) == 7


def test_limit_liczony_per_uzytkownik(logged_in_client, other_user):
    for i in range(7):
        db.session.add(SavedView(user_token=other_user.token, name=f'W{i}', config='{}'))
    db.session.commit()
    assert logged_in_client.post('/api/views', json={'name': 'Mój', 'config': CFG}).status_code == 201


def test_trasy_wymagaja_logowania(client):
    assert client.post('/api/views', json={'name': 'X', 'config': CFG}).status_code == 401
    assert client.put('/api/views/1', json={'name': 'X', 'config': CFG}).status_code == 401
    assert client.delete('/api/views/1').status_code == 401
    assert client.put('/api/accounts/1/favorite', json={'is_favorite': True}).status_code == 401


# --- Ulubione konta ---

def _konto(user_token, nazwa='Konto', **kw):
    a = Account(name=nazwa, bank_name='Bank', balance=Decimal('0.00'), user_token=user_token, **kw)
    db.session.add(a)
    db.session.commit()
    return a


def test_przelaczenie_ulubionego(logged_in_client, test_user_token):
    a = _konto(test_user_token)
    resp = logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': True})
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Account, a.id).is_favorite is True
    init = logged_in_client.get('/api/init').get_json()
    assert init['accounts'][0]['is_favorite'] is True

    assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': False}).status_code == 200
    db.session.expire_all()
    assert db.session.get(Account, a.id).is_favorite is False


def test_ulubione_nie_zmienia_konta_glownego(logged_in_client, test_user_token):
    a = _konto(test_user_token, is_default=True)
    logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': True})
    db.session.expire_all()
    assert db.session.get(Account, a.id).is_default is True


def test_jedenaste_ulubione_odrzucone(logged_in_client, test_user_token):
    konta = [_konto(test_user_token, f'K{i}') for i in range(11)]
    for a in konta[:10]:
        assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': True}).status_code == 200
    resp = logged_in_client.put(f'/api/accounts/{konta[10].id}/favorite', json={'is_favorite': True})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Account, konta[10].id).is_favorite is False
    # Ponowne oznaczenie już ulubionego nie wlicza się drugi raz.
    assert logged_in_client.put(f'/api/accounts/{konta[0].id}/favorite', json={'is_favorite': True}).status_code == 200


def test_konto_zamkniete_nie_wlicza_sie_do_limitu(logged_in_client, test_user_token):
    for i in range(10):
        _konto(test_user_token, f'Z{i}', is_favorite=True, is_active=i > 0)
    a = _konto(test_user_token, 'Nowe')
    assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': True}).status_code == 200


def test_zamkniete_konto_nie_zostaje_ulubionym(logged_in_client, test_user_token):
    a = _konto(test_user_token, is_active=False)
    assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': True}).status_code == 404
    db.session.expire_all()
    assert db.session.get(Account, a.id).is_favorite is False


def test_ulubione_wymaga_wartosci_logicznej(logged_in_client, test_user_token):
    a = _konto(test_user_token)
    assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': 'tak'}).status_code == 400
    assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={'is_favorite': 1}).status_code == 400
    assert logged_in_client.put(f'/api/accounts/{a.id}/favorite', json={}).status_code == 400


# --- Konto demo ---

def test_wipe_user_data_kasuje_widoki(app, test_user_token):
    from app.services.demo_service import wipe_user_data
    db.session.add(SavedView(user_token=test_user_token, name='Gość', config='{}'))
    db.session.commit()
    wipe_user_data(test_user_token)
    assert _widoki(test_user_token) == []
