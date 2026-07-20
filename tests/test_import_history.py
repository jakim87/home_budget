"""Historia importów: ewidencja wgranych wyciągów + ostrzeżenie o nakładających się zakresach.

Historia pełni DWIE role:
1. audyt — co, kiedy i za jaki okres zostało wgrane,
2. sygnał pokrycia — czy dane konto w ogóle dostaje własne wyciągi. Ten drugi
   punkt jest fundamentem modelu transferów (czy generować lustro).
"""
import io
from datetime import date

import pytest

from app import db
from app.models import Account, StatementImport
from app.services.import_history_service import (
    account_has_statement_imports,
    find_overlapping_imports,
    record_statement_import,
)


@pytest.fixture
def acc(app, test_user):
    account = Account(name="Konto Historii", bank_name="mBank", user_token=test_user.token,
                      account_number="11 1111 1111 1111 1111 1111 1111")
    db.session.add(account)
    db.session.commit()
    return account


MBANK_HTML = '''<HTML xmlns:ns1="http://www.bre.pl"><BODY>
<b>Lista operacji za okres od 2026-06-01 do 2026-06-30</b>
dla rachunków: <b>X - 11111111111111111111111111</b>
<table>
<tr class="head"><td>Data operacji</td><td>Opis operacji</td><td>Rachunek</td><td>Kategoria</td><td>Kwota</td></tr>
<tr><td>2026-06-10</td><td>HIST TEST A<br>SZCZEGÓŁY</td><td>K</td><td>Inne</td><td><nobr>-10,00 PLN</nobr></td></tr>
<tr><td>2026-06-20</td><td>HIST TEST B<br>SZCZEGÓŁY</td><td>K</td><td>Inne</td><td><nobr>-20,00 PLN</nobr></td></tr>
</table></BODY></HTML>'''


def _upload(client, payload: bytes, filename="wyciag.html"):
    return client.post('/api/import/auto',
                       data={'file': (io.BytesIO(payload), filename)},
                       content_type='multipart/form-data')


def test_import_records_history_entry(logged_in_client, app, acc):
    """Udany import zapisuje wpis historii z zakresem dat i liczbą transakcji."""
    resp = _upload(logged_in_client, MBANK_HTML.encode('utf-8'), filename="czerwiec.html")
    assert resp.status_code == 201

    entry = db.session.query(StatementImport).one()
    assert entry.filename == "czerwiec.html"
    assert entry.bank == "mbank"
    assert entry.file_format == "html"
    assert entry.account_id == acc.id
    assert entry.period_start == date(2026, 6, 10)
    assert entry.period_end == date(2026, 6, 20)
    assert entry.transaction_count == 2


def test_failed_import_records_no_history(logged_in_client, app, acc):
    """Odrzucony plik (nierozpoznany) nie zostawia śladu w historii."""
    resp = _upload(logged_in_client, b'zupelnie przypadkowa tresc', filename="smiec.txt")
    assert resp.status_code == 400
    assert db.session.query(StatementImport).count() == 0


def test_reimport_same_period_returns_overlap_warning(logged_in_client, app, acc):
    """Ponowny import tego samego zakresu → ostrzeżenie o nakładaniu (nie błąd)."""
    first = _upload(logged_in_client, MBANK_HTML.encode('utf-8'))
    assert first.status_code == 201
    assert not first.get_json().get('overlap_warning')

    second = _upload(logged_in_client, MBANK_HTML.encode('utf-8'))
    assert second.status_code == 201
    warning = second.get_json().get('overlap_warning')
    assert warning, "drugi import tego samego okresu powinien zwrócić ostrzeżenie"
    assert 'Konto Historii' in warning


def test_find_overlapping_imports_boundaries(app, test_user, acc):
    """Nakładanie liczone inkluzywnie; rozłączne zakresy nie dają dopasowania."""
    record_statement_import(
        user_token=test_user.token, filename="a.csv", bank="mbank", file_format="csv",
        account_id=acc.id, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
        transaction_count=5, skipped_count=0, batch_id="b1",
    )

    assert find_overlapping_imports(test_user.token, acc.id, date(2026, 6, 15), date(2026, 7, 5))
    assert find_overlapping_imports(test_user.token, acc.id, date(2026, 6, 30), date(2026, 7, 5))
    assert not find_overlapping_imports(test_user.token, acc.id, date(2026, 7, 1), date(2026, 7, 31))
    assert not find_overlapping_imports(test_user.token, acc.id, date(2026, 5, 1), date(2026, 5, 31))


def test_account_has_statement_imports_is_coverage_signal(app, test_user, acc):
    """Sygnał pokrycia dla modelu transferów: czy konto dostaje własne wyciągi."""
    other = Account(name="Cel bez wyciągu", bank_name="mBank", user_token=test_user.token)
    db.session.add(other)
    db.session.commit()

    record_statement_import(
        user_token=test_user.token, filename="a.csv", bank="mbank", file_format="csv",
        account_id=acc.id, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
        transaction_count=5, skipped_count=0, batch_id="b1",
    )

    assert account_has_statement_imports(test_user.token, acc.id) is True
    assert account_has_statement_imports(test_user.token, other.id) is False


def test_history_endpoint_lists_imports(logged_in_client, app, acc):
    """GET /api/import/history zwraca wpisy najnowsze najpierw, z nazwą konta."""
    _upload(logged_in_client, MBANK_HTML.encode('utf-8'), filename="czerwiec.html")

    resp = logged_in_client.get('/api/import/history')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['filename'] == "czerwiec.html"
    assert data[0]['account_name'] == "Konto Historii"
    assert data[0]['period_start'] == "2026-06-10"
    assert data[0]['transaction_count'] == 2


def test_history_is_per_user(app, test_user, other_user, acc):
    """Historia jest izolowana per użytkownik (IDOR)."""
    record_statement_import(
        user_token=test_user.token, filename="moj.csv", bank="mbank", file_format="csv",
        account_id=acc.id, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
        transaction_count=1, skipped_count=0, batch_id="b1",
    )
    assert db.session.query(StatementImport).filter_by(user_token=other_user.token).count() == 0
    assert account_has_statement_imports(other_user.token, acc.id) is False
