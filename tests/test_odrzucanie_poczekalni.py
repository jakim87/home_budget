"""Precyzyjne odrzucanie z poczekalni: jeden wiersz albo cały wgrany plik.

„Odrzuć wszystkie" zabiera całą poczekalnię, a „To ta sama" działa tylko przy
możliwym duplikacie — wyciąg wgrany częściowo na złe konto nie miał jak zniknąć
sam, bez reszty poczekalni.
"""
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, StatementImport, Transaction, TransactionStaging
from app.services.import_history_service import account_has_statement_imports
from tests import test_import_flow
from tests.test_import_flow import _poczekalnia, _stg, _wyciagi

# Fixture z testów podglądu par — przypisanie zamiast importu, żeby pytest ją widział.
dwa_konta = test_import_flow.dwa_konta


def _konto(token, nazwa):
    konto = Account(name=nazwa, bank_name='Bank', user_token=token)
    db.session.add(konto)
    db.session.commit()
    return konto


def _wiersz(token, konto, kwota='-10.00'):
    row = TransactionStaging(date=date(2026, 5, 1), amount=Decimal(kwota), title='x',
                             status='pending', account_id=konto.id, user_token=token)
    db.session.add(row)
    db.session.commit()
    return row


def _wpis_importu(token, konto, batch='b1'):
    db.session.add(StatementImport(user_token=token, batch_id=batch, filename='w.csv', bank='ing',
                                   file_format='csv', account_id=konto.id))
    db.session.commit()


# --- Pojedynczy wiersz -------------------------------------------------------

def test_odrzucenie_wiersza_kasuje_tylko_ten_wiersz(logged_in_client, test_user):
    konto = _konto(test_user.token, 'Konto')
    odrzucany = _wiersz(test_user.token, konto).id
    zostaje = _wiersz(test_user.token, konto).id
    saldo = konto.balance

    resp = logged_in_client.delete(f'/api/staging/{odrzucany}')

    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(TransactionStaging, odrzucany) is None
    assert db.session.get(TransactionStaging, zostaje) is not None
    assert db.session.query(Transaction).count() == 0
    assert db.session.get(Account, konto.id).balance == saldo


def test_odrzucenie_nieistniejacego_wiersza_404(logged_in_client, test_user):
    resp = logged_in_client.delete('/api/staging/999999')
    assert resp.status_code == 404


def test_odrzucenie_ostatniego_wiersza_konta_bez_importu_kasuje_wpis_historii(logged_in_client, test_user):
    """Wiersze pomyłkowego wyciągu odrzucone pojedynczo — jak „Odrzuć wszystkie" (#181)."""
    konto = _konto(test_user.token, 'Cel: wakacje')
    _wpis_importu(test_user.token, konto)
    a, b = _wiersz(test_user.token, konto), _wiersz(test_user.token, konto)

    logged_in_client.delete(f'/api/staging/{a.id}')
    # Konto ma jeszcze wiersz w poczekalni — wyciąg nie jest jeszcze odrzucony.
    assert account_has_statement_imports(test_user.token, konto.id)

    logged_in_client.delete(f'/api/staging/{b.id}')
    assert not account_has_statement_imports(test_user.token, konto.id)


def test_odrzucenie_wiersza_zostawia_wpis_konta_z_zatwierdzonym_importem(logged_in_client, test_user):
    konto = _konto(test_user.token, 'Konto')
    _wpis_importu(test_user.token, konto)
    db.session.add(Transaction(date=date(2026, 4, 1), title='Z wyciągu', amount=Decimal('-5.00'),
                               account_id=konto.id, user_token=test_user.token, origin='import'))
    db.session.commit()
    row = _wiersz(test_user.token, konto)

    logged_in_client.delete(f'/api/staging/{row.id}')

    assert account_has_statement_imports(test_user.token, konto.id)


def test_odrzucenie_nogi_przelewu_przelicza_stan_drugiej(logged_in_client, test_user, dwa_konta):
    """Para z poczekalni traci partnera — druga noga nie może dalej wskazywać skasowanej."""
    k = dwa_konta
    _wyciagi(test_user.token, k['a'])
    _wyciagi(test_user.token, k['b'])
    # Konto B ma zaksięgowany import, więc jego wyciąg zostaje sygnałem pokrycia.
    db.session.add(Transaction(date=date(2026, 7, 1), title='Z wyciągu', amount=Decimal('-1.00'),
                               account_id=k['b'].id, user_token=test_user.token, origin='import'))
    db.session.commit()
    wyplyw = _stg(test_user.token, k['a'], "-500.00", k['cont_b'], k['cat'])
    wplyw = _stg(test_user.token, k['b'], "500.00", k['cont_a'], k['cat'])
    assert _poczekalnia(logged_in_client)[wyplyw.id]['transfer_pair_id'] == wplyw.id

    assert logged_in_client.delete(f'/api/staging/{wplyw.id}').status_code == 200

    wiersz = _poczekalnia(logged_in_client)[wyplyw.id]
    assert wiersz['transfer_pair'] == 'missing'
    assert wiersz['transfer_pair_id'] is None


# --- Cały plik i całe konto --------------------------------------------------

def _wgraj_html(client, konto_id):
    import io
    from tests.test_import_history import MBANK_HTML
    data = {'file': (io.BytesIO(MBANK_HTML.encode('utf-8')), 'wyciag.html'), 'account_id': str(konto_id)}
    return client.post('/api/import/auto', data=data, content_type='multipart/form-data')


def test_import_oznacza_wiersze_plikiem_i_poczekalnia_go_podaje(logged_in_client, test_user):
    konto = _konto(test_user.token, 'mBank')
    assert _wgraj_html(logged_in_client, konto.id).status_code == 201

    batch = db.session.query(StatementImport).one().batch_id
    assert {s.import_batch_id for s in db.session.query(TransactionStaging).all()} == {batch}
    wiersz = next(iter(_poczekalnia(logged_in_client).values()))
    assert wiersz['import_batch_id'] == batch
    assert wiersz['import_filename'] == 'wyciag.html'


def test_odrzucenie_pliku_zabiera_tylko_jego_wiersze(logged_in_client, test_user):
    konto = _konto(test_user.token, 'Konto')
    _wpis_importu(test_user.token, konto, 'plik1')
    _wpis_importu(test_user.token, konto, 'plik2')
    z_pliku1 = [_wiersz(test_user.token, konto) for _ in range(2)]
    z_pliku2 = _wiersz(test_user.token, konto)
    for w in z_pliku1:
        w.import_batch_id = 'plik1'
    z_pliku2.import_batch_id = 'plik2'
    db.session.commit()

    resp = logged_in_client.delete('/api/staging/batch/plik1')

    assert resp.status_code == 200
    assert resp.get_json()['count'] == 2
    db.session.expire_all()
    assert [s.id for s in db.session.query(TransactionStaging).all()] == [z_pliku2.id]
    # Konto ma jeszcze wiersz z innego pliku — dalej dostaje wyciągi.
    assert account_has_statement_imports(test_user.token, konto.id)


def test_odrzucenie_pliku_na_zle_konto_kasuje_wpis_historii(logged_in_client, test_user):
    """#181: pomyłkowy plik odrzucony w całości nie wyłącza kontu luster."""
    zle = _konto(test_user.token, 'Cel: wakacje')
    assert _wgraj_html(logged_in_client, zle.id).status_code == 201
    batch = db.session.query(StatementImport).one().batch_id

    assert logged_in_client.delete(f'/api/staging/batch/{batch}').status_code == 200

    assert db.session.query(TransactionStaging).count() == 0
    assert not account_has_statement_imports(test_user.token, zle.id)


def test_odrzucenie_nieznanego_pliku_404(logged_in_client, test_user):
    assert logged_in_client.delete('/api/staging/batch/nie-ma-takiego').status_code == 404


def test_odrzucenie_konta_zabiera_wiersze_tylko_tego_konta(logged_in_client, test_user):
    """Plik wielokontowy z jednym złym kontem: odrzucamy tylko jego wiersze."""
    zle, dobre = _konto(test_user.token, 'Złe'), _konto(test_user.token, 'Dobre')
    _wpis_importu(test_user.token, zle)
    _wpis_importu(test_user.token, dobre)
    for _ in range(2):
        _wiersz(test_user.token, zle)
    zostaje = _wiersz(test_user.token, dobre)

    resp = logged_in_client.delete(f'/api/staging/account/{zle.id}')

    assert resp.status_code == 200
    assert resp.get_json()['count'] == 2
    db.session.expire_all()
    assert [s.id for s in db.session.query(TransactionStaging).all()] == [zostaje.id]
    assert not account_has_statement_imports(test_user.token, zle.id)
    assert account_has_statement_imports(test_user.token, dobre.id)


def test_odrzucenie_konta_bez_poczekalni_404(logged_in_client, test_user):
    konto = _konto(test_user.token, 'Puste')
    assert logged_in_client.delete(f'/api/staging/account/{konto.id}').status_code == 404
