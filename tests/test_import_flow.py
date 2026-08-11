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


MBANK_HTML_MINI = '''<HTML xmlns:ns1="http://www.bre.pl"><BODY>
<b>Lista operacji za okres od 2026-06-01 do 2026-06-30</b>
<table>
<tr class="head"><td>Data operacji</td><td>Opis operacji</td><td>Rachunek</td><td>Kategoria</td><td>Kwota</td></tr>
<tr><td>2026-06-05</td><td>SKLEP TESTOWY<br>PŁATNOŚĆ KARTĄ</td><td>K 1 ... 1</td><td>Zakupy</td><td><nobr>-15,00 PLN</nobr></td></tr>
</table></BODY></HTML>'''


def test_import_auto_detects_mbank_html(logged_in_client, app, import_account):
    """POST /api/import/auto: wykrywa mBank HTML, zapisuje do stagingu,
    zwraca wykryty bank/format w odpowiedzi."""
    resp = _upload(logged_in_client, import_account.id,
                   MBANK_HTML_MINI.encode('utf-8'), filename="zestawienie.html", bank="auto")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['detected'] == {'bank': 'mbank', 'format': 'html'}
    assert db.session.query(TransactionStaging).count() == 1
    assert db.session.query(TransactionStaging).first().amount == Decimal("-15.00")


def test_import_auto_detects_ing_csv(logged_in_client, app, import_account):
    """POST /api/import/auto: rozpoznaje istniejący format ING CSV bez wskazywania banku."""
    resp = _upload(logged_in_client, import_account.id, CSV_PL.encode('utf-8'), bank="auto")
    assert resp.status_code == 201
    assert resp.get_json()['detected'] == {'bank': 'ing', 'format': 'csv'}
    assert db.session.query(TransactionStaging).count() == 2


def test_import_auto_unknown_content_returns_400(logged_in_client, app, import_account):
    """Nierozpoznawalna zawartość → 400 z prośbą o ręczny wybór banku."""
    resp = _upload(logged_in_client, import_account.id, b'przypadkowy tekst', bank="auto")
    assert resp.status_code == 400
    assert db.session.query(TransactionStaging).count() == 0


MBANK_HTML_WITH_IBAN = '''<HTML xmlns:ns1="http://www.bre.pl"><BODY>
<b>Lista operacji za okres od 2026-06-01 do 2026-06-30</b>
dla rachunków:
<b>Kowalski - 22334455667788990011223344</b>
<table>
<tr class="head"><td>Data operacji</td><td>Opis operacji</td><td>Rachunek</td><td>Kategoria</td><td>Kwota</td></tr>
<tr><td>2026-06-07</td><td>SKLEP IBAN TEST<br>PŁATNOŚĆ</td><td>K 1 ... 1</td><td>Zakupy</td><td><nobr>-9,99 PLN</nobr></td></tr>
</table></BODY></HTML>'''


@pytest.fixture
def iban_account(app, test_user):
    """Konto z numerem zgodnym z IBAN-em w MBANK_HTML_WITH_IBAN."""
    account = Account(name="mBank IBAN", bank_name="mBank", user_token=test_user.token,
                      account_number="22 3344 5566 7788 9900 1122 3344")
    db.session.add(account)
    db.session.commit()
    return account


def _upload_auto_no_account(client, payload: bytes, filename="plik.html"):
    return client.post('/api/import/auto',
                       data={'file': (io.BytesIO(payload), filename)},
                       content_type='multipart/form-data')


def test_import_auto_resolves_account_by_statement_iban(logged_in_client, app, iban_account):
    """Bez account_id: konto rozpoznane po IBAN z nagłówka wyciągu."""
    resp = _upload_auto_no_account(logged_in_client, MBANK_HTML_WITH_IBAN.encode('utf-8'))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body.get('resolved_account', {}).get('id') == iban_account.id
    stg = db.session.query(TransactionStaging).first()
    assert stg.account_id == iban_account.id


def test_import_auto_no_account_and_unknown_iban_returns_400(logged_in_client, app, import_account):
    """Bez account_id i bez pasującego konta w słowniku → czytelny 400, nic nie zapisane."""
    resp = _upload_auto_no_account(logged_in_client, MBANK_HTML_WITH_IBAN.encode('utf-8'))
    assert resp.status_code == 400
    assert 'IBAN' in resp.get_json()['error'] or 'konta' in resp.get_json()['error']
    assert db.session.query(TransactionStaging).count() == 0


def test_import_auto_rejects_account_iban_mismatch(logged_in_client, app, import_account, iban_account):
    """Wybrane konto ≠ IBAN wyciągu → 400 (ochrona przed importem na złe konto)."""
    resp = _upload(logged_in_client, import_account.id,
                   MBANK_HTML_WITH_IBAN.encode('utf-8'), filename="z.html", bank="auto")
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


# --- Wykrywanie duplikatów: wiersz importu vs transakcja wpisana wcześniej ręcznie ---

@pytest.fixture
def dup_setup(app, test_user):
    """Odtwarza realny przypadek: ręczny wpis 'XTB' -150,00 z 2026-08-01 oraz wiersz
    stagingu z wyciągu o tej samej kwocie i dacie, ale innym tytułem."""
    account = Account(name="Moje ING", bank_name="ING", balance=Decimal("1000.00"), user_token=test_user.token)
    cat = Category(name="Przelew wewnętrzny", type="transfer", user_token=test_user.token)
    db.session.add_all([account, cat])
    db.session.commit()

    manual = Transaction(date=date(2026, 8, 1), title="XTB", amount=Decimal("-150.00"),
                         account_id=account.id, category_id=cat.id,
                         user_token=test_user.token, origin='manual')
    stg = TransactionStaging(date=date(2026, 8, 1), amount=Decimal("-150.00"), title="54174604",
                             contractor="XTB SPOLKA AKCYJNA", status="pending",
                             user_token=test_user.token, account_id=account.id)
    db.session.add_all([manual, stg])
    db.session.commit()
    return {'account': account, 'manual': manual, 'stg': stg}


def test_duplicate_candidate_found_for_manual_entry(logged_in_client, app, dup_setup):
    """Ten sam dzień, kwota i konto, inny tytuł → wiersz stagingu dostaje kandydata."""
    resp = logged_in_client.get('/api/staging/pending')
    assert resp.status_code == 200
    row = next(r for r in resp.get_json() if r['id'] == dup_setup['stg'].id)
    assert len(row['duplicate_candidates']) == 1
    cand = row['duplicate_candidates'][0]
    assert cand['id'] == dup_setup['manual'].id
    assert cand['title'] == "XTB"
    assert cand['origin'] == 'manual'
    assert cand['days_diff'] == 0


@pytest.mark.parametrize("field,value", [
    ("amount", Decimal("-151.00")),   # inna kwota
    ("date", date(2026, 8, 6)),       # 5 dni różnicy — poza oknem ±4
])
def test_no_duplicate_candidate_outside_criteria(logged_in_client, app, dup_setup, field, value):
    setattr(dup_setup['manual'], field, value)
    db.session.commit()

    resp = logged_in_client.get('/api/staging/pending')
    row = next(r for r in resp.get_json() if r['id'] == dup_setup['stg'].id)
    assert row['duplicate_candidates'] == []


def test_no_duplicate_candidate_on_other_account(logged_in_client, app, dup_setup, test_user):
    """Ta sama kwota i data, ale inne konto → to nie ta sama operacja."""
    other = Account(name="Inne", bank_name="ING", balance=Decimal("0.00"), user_token=test_user.token)
    db.session.add(other)
    db.session.commit()
    dup_setup['manual'].account_id = other.id
    db.session.commit()

    resp = logged_in_client.get('/api/staging/pending')
    row = next(r for r in resp.get_json() if r['id'] == dup_setup['stg'].id)
    assert row['duplicate_candidates'] == []


def test_dismiss_staging_as_duplicate(logged_in_client, app, dup_setup):
    """Potwierdzenie duplikatu usuwa TYLKO wiersz stagingu — transakcja i saldo bez zmian."""
    stg_id = dup_setup['stg'].id
    tx_id = dup_setup['manual'].id
    acc_id = dup_setup['account'].id

    resp = logged_in_client.post(f'/api/staging/{stg_id}/duplicate-of', json={'transaction_id': tx_id})

    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg_id) is None
    assert db.session.get(Transaction, tx_id).amount == Decimal("-150.00")
    assert db.session.get(Account, acc_id).balance == Decimal("1000.00")


def test_dismiss_duplicate_requires_integer_transaction_id(logged_in_client, app, dup_setup):
    resp = logged_in_client.post(f'/api/staging/{dup_setup["stg"].id}/duplicate-of', json={})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(TransactionStaging, dup_setup['stg'].id) is not None


def test_origin_manual_vs_import(logged_in_client, app, dup_setup, test_user):
    """Transakcja z zatwierdzonego stagingu ma origin='import', ręczna 'manual'."""
    cont = Contractor(name="XTB", user_token=test_user.token)
    db.session.add(cont)
    db.session.commit()

    resp = logged_in_client.post(f'/api/staging/{dup_setup["stg"].id}/approve',
                                 json={'category': 'Przelew wewnętrzny', 'contractor_id': cont.id})
    assert resp.status_code == 200
    imported = db.session.get(Transaction, resp.get_json()['transaction_id'])
    assert imported.origin == 'import'
    assert db.session.get(Transaction, dup_setup['manual'].id).origin == 'manual'
