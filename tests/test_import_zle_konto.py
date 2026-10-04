"""Wyciąg wgrany na złe konto (#181, A8 z audytu 2026-09-13).

Dwie bariery:
1. Numer rachunku z wyciągu musi zgadzać się z wybranym kontem — także wtedy, gdy
   bank wskazano ręcznie z listy (tryb automatyczny pilnował tego od początku).
2. Tam, gdzie numeru nie da się porównać (plik albo konto bez numeru), pomyłkę
   cofa „Odrzuć wszystkie": razem z poczekalnią znika wpis historii importu. Ten
   wpis to sygnał „konto dostaje własne wyciągi", który wyłącza lustra przelewów —
   pozostawiony po pomyłce wyłączałby je temu kontu na stałe.
"""
import io
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, StatementImport, Transaction, TransactionStaging
from app.services.budget_service import clear_pending_staging
from app.services.import_history_service import account_has_statement_imports
from tests.test_import_history import MBANK_HTML

NRB_Z_WYCIAGU = '11111111111111111111111111'
INNY_NRB = '61109010140000071219812874'


def _konto(token, nazwa, numer=None):
    konto = Account(name=nazwa, bank_name='Bank', user_token=token, account_number=numer)
    db.session.add(konto)
    db.session.commit()
    return konto


def _wgraj(client, url, konto_id=None):
    data = {'file': (io.BytesIO(MBANK_HTML.encode('utf-8')), 'wyciag.html')}
    if konto_id:
        data['account_id'] = str(konto_id)
    return client.post(url, data=data, content_type='multipart/form-data')


# --- 1. Tryb ręczny sprawdza numer rachunku ---------------------------------

def test_tryb_reczny_odrzuca_wyciag_na_konto_o_innym_numerze(logged_in_client, test_user):
    zle = _konto(test_user.token, 'Cel: wakacje', INNY_NRB)

    resp = _wgraj(logged_in_client, '/api/import/mbank/html', zle.id)

    assert resp.status_code == 400
    assert 'Cel: wakacje' in resp.get_json()['error']
    assert db.session.query(TransactionStaging).count() == 0
    assert db.session.query(StatementImport).count() == 0


def test_tryb_reczny_odrzuca_gdy_wyciag_pasuje_do_innego_konta(logged_in_client, test_user):
    _konto(test_user.token, 'mBank', NRB_Z_WYCIAGU)
    zle = _konto(test_user.token, 'Cel: wakacje')

    resp = _wgraj(logged_in_client, '/api/import/mbank/html', zle.id)

    assert resp.status_code == 400
    assert 'mBank' in resp.get_json()['error']
    assert db.session.query(TransactionStaging).count() == 0


def test_tryb_reczny_przyjmuje_wyciag_na_wlasciwe_konto(logged_in_client, test_user):
    dobre = _konto(test_user.token, 'mBank', NRB_Z_WYCIAGU)

    resp = _wgraj(logged_in_client, '/api/import/mbank/html', dobre.id)

    assert resp.status_code == 201
    assert {s.account_id for s in db.session.query(TransactionStaging).all()} == {dobre.id}


def test_tryb_reczny_sam_rozpoznaje_konto_po_numerze(logged_in_client, test_user):
    dobre = _konto(test_user.token, 'mBank', NRB_Z_WYCIAGU)

    resp = _wgraj(logged_in_client, '/api/import/mbank/html')

    assert resp.status_code == 201
    assert {s.account_id for s in db.session.query(TransactionStaging).all()} == {dobre.id}


# --- 2. Odrzucenie poczekalni cofa pomyłkowy wpis historii -------------------

def test_odrzucenie_poczekalni_kasuje_wpis_historii_konta_bez_importu(logged_in_client, test_user):
    """Konto bez numeru: aplikacja ufa wyborowi z listy, więc pomyłka przechodzi."""
    zle = _konto(test_user.token, 'Cel: wakacje')
    assert _wgraj(logged_in_client, '/api/import/auto', zle.id).status_code == 201
    assert account_has_statement_imports(test_user.token, zle.id)

    resp = logged_in_client.delete('/api/staging/pending')

    assert resp.status_code == 200
    assert db.session.query(TransactionStaging).count() == 0
    # Konto znów „nie dostaje wyciągów" — przelewy na nie dostaną lustro.
    assert not account_has_statement_imports(test_user.token, zle.id)


def test_odrzucenie_poczekalni_zostawia_wpis_konta_z_zatwierdzonym_importem(logged_in_client, test_user):
    konto = _konto(test_user.token, 'mBank', NRB_Z_WYCIAGU)
    db.session.add(Transaction(date=date(2026, 5, 1), title='Wcześniejszy import', amount=Decimal('-5.00'),
                               account_id=konto.id, user_token=test_user.token, origin='import'))
    db.session.commit()
    assert _wgraj(logged_in_client, '/api/import/auto', konto.id).status_code == 201

    logged_in_client.delete('/api/staging/pending')

    assert account_has_statement_imports(test_user.token, konto.id)


def test_odrzucenie_poczekalni_zostawia_wpis_konta_z_historia_sprzed_kolumny_origin(logged_in_client, test_user):
    """origin='unknown' mógł być importem — w razie wątpliwości pokrycie zostaje."""
    konto = _konto(test_user.token, 'mBank', NRB_Z_WYCIAGU)
    db.session.add(Transaction(date=date(2026, 5, 1), title='Stara operacja', amount=Decimal('-5.00'),
                               account_id=konto.id, user_token=test_user.token, origin='unknown'))
    db.session.commit()
    assert _wgraj(logged_in_client, '/api/import/auto', konto.id).status_code == 201

    logged_in_client.delete('/api/staging/pending')

    assert account_has_statement_imports(test_user.token, konto.id)


def test_odrzucenie_poczekalni_nie_rusza_kont_spoza_poczekalni(app, test_user, other_user):
    """Kasujemy tylko wpisy kont, których wiersze właśnie odrzucono — i tylko własne."""
    moje_inne = _konto(test_user.token, 'Bez poczekalni')
    cudze = _konto(other_user.token, 'Cudze')
    odrzucane = _konto(test_user.token, 'Odrzucane')
    for token, konto in ((test_user.token, moje_inne), (other_user.token, cudze), (test_user.token, odrzucane)):
        db.session.add(StatementImport(user_token=token, batch_id='b', filename='f', bank='ing',
                                       file_format='csv', account_id=konto.id))
    for token, konto in ((other_user.token, cudze), (test_user.token, odrzucane)):
        db.session.add(TransactionStaging(date=date(2026, 5, 1), amount=Decimal('-1.00'), title='x',
                                          account_id=konto.id, user_token=token))
    db.session.commit()

    assert clear_pending_staging(test_user.token) == 1

    assert not account_has_statement_imports(test_user.token, odrzucane.id)
    assert account_has_statement_imports(test_user.token, moje_inne.id)
    assert account_has_statement_imports(other_user.token, cudze.id)
    assert db.session.query(TransactionStaging).filter_by(user_token=other_user.token).count() == 1
