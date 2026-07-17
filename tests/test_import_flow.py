"""Przepływ importu CSV: deduplikacja, kodowania, atomowość zatwierdzania stagingu."""
import io
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, Transaction, TransactionStaging
from app.services.budget_service import save_transactions_to_staging


CSV_PL = """Data transakcji;Data księgowania;Dane kontrahenta;Tytuł;Nr rachunku;Konto;Bank;Szczegóły;NrTx;Kwota transakcji;Waluta
2024-03-05;2024-03-05;Żabka Sp. z o.o.;Zakupy spożywcze;;;Bank;;;-25,50;PLN
2024-03-06;2024-03-06;Pracodawca;Wypłata za marzec;;;Bank;;;5000,00;PLN
"""


@pytest.fixture
def import_account(app, test_user):
    account = Account(name="Konto Importowe", bank_name="ING", user_token=test_user.token)
    db.session.add(account)
    db.session.commit()
    return account


def _upload(client, account_id, payload: bytes, filename="wyciag.csv", bank="ing"):
    return client.post(f'/api/import/{bank}',
                       data={'file': (io.BytesIO(payload), filename), 'account_id': account_id},
                       content_type='multipart/form-data')


MBANK_CSV = """mBank S.A. Bankowość Detaliczna;

#Data operacji;#Opis operacji;#Rachunek;#Kategoria;#Kwota;
2026-06-30;"SKLEP TESTOWY   PŁATNOŚĆ KARTĄ   ";"Konto 1111 ... 1111";"Zakupy";-49,99 PLN;;
"""


def test_import_dispatch_mbank_bank_param(logged_in_client, app, import_account):
    """Endpoint /api/import/mbank routuje do parsera mBank i zapisuje transakcję do stagingu."""
    resp = _upload(logged_in_client, import_account.id, MBANK_CSV.encode('utf-8'), bank="mbank")
    assert resp.status_code == 201
    assert db.session.query(TransactionStaging).count() == 1
    stg = db.session.query(TransactionStaging).first()
    assert stg.amount == Decimal("-49.99")


def test_import_unknown_bank_returns_400(logged_in_client, app, import_account):
    """Nieobsługiwany bank w URL → 400, brak wpisów w stagingu."""
    resp = _upload(logged_in_client, import_account.id, CSV_PL.encode('utf-8'), bank="pekao")
    assert resp.status_code == 400
    assert db.session.query(TransactionStaging).count() == 0


def test_reimport_same_parsed_rows_skips_duplicates(app, test_user, import_account):
    """Serwis: ponowny zapis tych samych wierszy nie tworzy duplikatów w stagingu."""
    rows = [
        {'date': date(2024, 3, 1), 'title': 'Czynsz', 'amount': Decimal("-1200.00"),
         'contractor': None, 'account_id': import_account.id},
    ]
    first = save_transactions_to_staging(rows, user_token=test_user.token)
    second = save_transactions_to_staging(rows, user_token=test_user.token)

    assert len(first) == 1
    assert len(second) == 0
    assert db.session.query(TransactionStaging).count() == 1


def test_reimport_same_csv_via_api_adds_nothing(logged_in_client, app, import_account):
    """API: drugi upload tego samego pliku → 0 nowych wierszy stagingu."""
    resp1 = _upload(logged_in_client, import_account.id, CSV_PL.encode('utf-8'))
    assert resp1.status_code == 201
    assert resp1.get_json()['count'] == 2

    resp2 = _upload(logged_in_client, import_account.id, CSV_PL.encode('utf-8'))
    assert resp2.status_code == 201
    assert resp2.get_json()['count'] == 0
    assert db.session.query(TransactionStaging).count() == 2


def test_import_windows_1250_encoding(logged_in_client, app, import_account):
    """Plik w windows-1250 (realny eksport ING) — polskie znaki dekodowane poprawnie."""
    resp = _upload(logged_in_client, import_account.id, CSV_PL.encode('windows-1250'))
    assert resp.status_code == 201
    assert resp.get_json()['count'] == 2

    titles = {s.title for s in db.session.query(TransactionStaging).all()}
    assert "Zakupy spożywcze" in titles  # znaki 'ż', 'ą' przetrwały dekodowanie
    contractors = {s.contractor for s in db.session.query(TransactionStaging).all()}
    assert "Żabka Sp. z o.o." in contractors


def test_import_utf8_sig_bom(logged_in_client, app, import_account):
    """Plik UTF-8 z BOM (drugi wariant eksportu ING) — BOM nie zaśmieca nagłówka."""
    resp = _upload(logged_in_client, import_account.id, CSV_PL.encode('utf-8-sig'))
    assert resp.status_code == 201
    assert resp.get_json()['count'] == 2


def test_import_unsupported_encoding_returns_400(logged_in_client, app, import_account):
    """Bajty nieprawidłowe i dla UTF-8, i dla cp1250 → czytelny błąd 400, nie 500."""
    invalid = b"\xff\x81\x90\x98\x83\xff"
    resp = _upload(logged_in_client, import_account.id, invalid)
    assert resp.status_code == 400
    assert 'kodowanie' in resp.get_json()['error'].lower()


def test_approve_failure_keeps_staging_and_balance(logged_in_client, app, test_user):
    """Atomowość: zatwierdzenie z nieistniejącą kategorią → staging dalej pending,
    saldo nietknięte, transakcja nie powstała."""
    account = Account(name="Konto Atom", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user.token)
    db.session.add(account)
    db.session.commit()
    cont = Contractor(name="Sklep", user_token=test_user.token)
    stg = TransactionStaging(date=date(2024, 3, 10), amount=Decimal("-30.00"), title="Zakup",
                             status="pending", user_token=test_user.token, account_id=account.id)
    db.session.add_all([cont, stg])
    db.session.commit()
    stg_id, acc_id, cont_id = stg.id, account.id, cont.id

    resp = logged_in_client.post(f'/api/staging/{stg_id}/approve',
                                 json={'category': 'NieistniejącaKategoria', 'contractor_id': cont_id})

    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg_id).status == "pending"
    assert db.session.get(Account, acc_id).balance == Decimal("100.00")
    assert db.session.query(Transaction).count() == 0


def test_approve_to_inactive_account_rejected(logged_in_client, app, test_user):
    """Konto dezaktywowane między importem a zatwierdzeniem → odmowa, staging zostaje."""
    account = Account(name="Konto Zamknięte", bank_name="Bank", balance=Decimal("0.00"),
                      user_token=test_user.token, is_active=False)
    cat = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, cat])
    db.session.commit()
    cont = Contractor(name="Sklep", user_token=test_user.token)
    stg = TransactionStaging(date=date(2024, 3, 11), amount=Decimal("-15.00"), title="Zakup",
                             status="pending", user_token=test_user.token, account_id=account.id)
    db.session.add_all([cont, stg])
    db.session.commit()
    stg_id, cont_id = stg.id, cont.id

    resp = logged_in_client.post(f'/api/staging/{stg_id}/approve',
                                 json={'category': 'Jedzenie', 'contractor_id': cont_id})

    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg_id).status == "pending"
    assert db.session.query(Transaction).count() == 0
