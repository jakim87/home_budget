"""Detekcja banku i formatu wyciągu + parsery mBank HTML/PDF.

Wszystkie fixtures ZANONIMIZOWANE (zmyślone nazwiska, numery kont, kwoty).
PDF-y generowane programowo przez pymupdf — bez binariów w repo.
"""
import pytest
from decimal import Decimal
from datetime import date

from app import db
from app.models import User, Account
from app.services.statement_parsers import (
    detect_bank_and_format,
    parse_mbank_html,
    parse_mbank_pdf,
)

# --- Fixtures treściowe -----------------------------------------------------

ING_CSV_SAMPLE = '''"Wybrane rachunki:";
"KONTO Testowe (PLN)";;"10 1050 0099 7603 1234 5678 9123";

"Data transakcji";"Data księgowania";"Dane kontrahenta";"Tytuł";"Nr rachunku";"Kwota transakcji (waluta rachunku)";"Waluta";"Konto"
"2026-06-05";"2026-06-05";"Sklep";"Zakupy";"";"-10,00";"PLN";"KONTO Testowe"
'''

MBANK_CSV_SAMPLE = '''mBank S.A. Bankowość Detaliczna;

#Data operacji;#Opis operacji;#Rachunek;#Kategoria;#Kwota;
2026-06-05;"SKLEP TESTOWY   ";"Konto 1111 ... 1111";"Zakupy";-10,00 PLN;;
'''

MBANK_HTML_SAMPLE = '''﻿<HTML xmlns:ns1="http://www.bre.pl">
  <HEAD><TITLE>Zestawienie operacji</TITLE></HEAD>
  <BODY>
    <b>Lista operacji za okres od 2026-06-01 do 2026-06-30</b><br>
    dla rachunków:
    <b>Kowalski - 11111111111111111111111111</b><br>
    <table>
      <tr class="head"><td>Waluta</td><td>Wpływy</td><td>Wydatki</td></tr>
      <tr><td>PLN</td><td>440,00</td><td>-125,50</td></tr>
    </table>
    <table>
      <tr class="head"><td>Data operacji</td><td>Opis operacji</td><td>Rachunek</td><td>Kategoria</td><td>Kwota</td></tr>
      <tr>
        <td class="data">2026-06-30</td>
        <td class="data">FIRMA TESTOWA SP Z OO, Dziecko<br>FIRMA TESTOWA SP Z OO           UL.PRZYKŁADOWA 1                   00-001 WARSZAWA PRZELEW ZEWNĘTRZNY PRZYCHODZĄCY<br>99888877776666555544443333</td>
        <td class="data">Kowalski<br>1111 ... 1111</td>
        <td class="data">Wpływy - inne</td>
        <td class="data"><nobr>440,00 PLN</nobr></td>
      </tr>
      <tr>
        <td class="data">2026-06-01</td>
        <td class="data">SKLEPIK TESTOWY WARSZAWA<br>PŁATNOŚĆ KARTĄ 1234xx5678</td>
        <td class="data">Kowalski<br>1111 ... 1111</td>
        <td class="data">Zakupy</td>
        <td class="data"><nobr>-125,50 PLN</nobr></td>
      </tr>
    </table>
  </BODY>
</HTML>
'''


def _build_mbank_pdf_bytes() -> bytes:
    """Buduje minimalny PDF o układzie tekstu jak realny wyciąg mBank.

    Uwaga: fitz.Story (HTML→PDF), nie insert_text — wbudowane fonty base-14
    nie mają polskich znaków (Ł→0xB7), Story osadza font unicode.
    """
    import fitz
    import os
    import tempfile
    lines = [
        "mBank S.A. Bankowość Detaliczna",
        "JAN TESTOWY KOWALSKI",
        "Listaoperacjizaokresod2026-06-01do2026-06-30",
        "dla rachunków:",
        "Kowalski - 11111111111111111111111111",
        "Waluta Wpływy Wydatki",
        "PLN 440,00 -125,50",
        "Operacje",
        "Dataoperacji Opisoperacji Rachunek Kategoria Kwota",
        "2026-06-30 FIRMA TESTOWA SP Z OO, Dziecko",
        "FIRMA TESTOWA SP Z OO UL.PRZYKŁADOWA 1 00-001",
        "WARSZAWA PRZELEW ZEWNĘTRZNY PRZYCHODZĄCY",
        "99888877776666555544443333",
        "Kowalski",
        "1111 ... 1111",
        "Wpływy - inne 440,00 PLN",
        "2026-06-01 SKLEPIK TESTOWY WARSZAWA",
        "PŁATNOŚĆ KARTĄ 1234xx5678",
        "Kowalski",
        "1111 ... 1111",
        "Zakupy -125,50 PLN",
    ]
    html = "".join(f"<p>{l}</p>" for l in lines)
    fd, path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    try:
        writer = fitz.DocumentWriter(path)
        story = fitz.Story(html)
        more = True
        while more:
            dev = writer.begin_page(fitz.paper_rect('a4'))
            more, _ = story.place(fitz.Rect(36, 36, 559, 806))
            story.draw(dev)
            writer.end_page()
        writer.close()
        with open(path, 'rb') as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def mf_user(app):
    """Użytkownik z kontem docelowym do importu jednokontowego."""
    with app.app_context():
        user = User(username="mf_user", email="mf@user.com", password_hash="a")
        acc = Account(user=user, name="mBank ROR", bank_name="mBank",
                      account_number="PL11111111111111111111111111")
        db.session.add_all([user, acc])
        db.session.commit()
        return user.token, acc.id


# --- Detekcja ---------------------------------------------------------------

def test_detect_ing_csv():
    bank, fmt = detect_bank_and_format(ING_CSV_SAMPLE.encode('utf-8'), 'wyciag.csv')
    assert (bank, fmt) == ('ing', 'csv')


def test_detect_mbank_csv():
    bank, fmt = detect_bank_and_format(MBANK_CSV_SAMPLE.encode('utf-8'), 'operacje.csv')
    assert (bank, fmt) == ('mbank', 'csv')


def test_detect_mbank_html():
    bank, fmt = detect_bank_and_format(MBANK_HTML_SAMPLE.encode('utf-8'), 'zestawienie.html')
    assert (bank, fmt) == ('mbank', 'html')


def test_detect_mbank_pdf():
    bank, fmt = detect_bank_and_format(_build_mbank_pdf_bytes(), 'wyciag.pdf')
    assert (bank, fmt) == ('mbank', 'pdf')


def test_detect_unknown_returns_none_pair():
    bank, fmt = detect_bank_and_format(b'to nie jest wyciag bankowy', 'plik.txt')
    assert bank is None and fmt is None


def test_detect_ing_pdf_not_fooled_by_mbank_contractor():
    """ING PDF, w którym KONTRAHENT transakcji zawiera 'mBank S.A.', musi być
    rozpoznany jako ING — detekcja po markerach strukturalnych, nie substringu."""
    import fitz
    import os
    import tempfile
    lines = [
        "Dokument nr: 0000000000_000000",
        "Lista transakcji",
        "Dane użytkownika Wybrane rachunki",
        "JAN TESTOWY KOWALSKI",
        "KONTO Testowe (PLN)",
        "10 1050 0099 7603 1234 5678 9123",
        "Zakres dat: 01.06.2026 - 30.06.2026",
        "30.06.2026 Przelew własny na mBank S.A. -10,00 PLN",
    ]
    html = "".join(f"<p>{l}</p>" for l in lines)
    fd, path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    try:
        writer = fitz.DocumentWriter(path)
        story = fitz.Story(html)
        more = True
        while more:
            dev = writer.begin_page(fitz.paper_rect('a4'))
            more, _ = story.place(fitz.Rect(36, 36, 559, 806))
            story.draw(dev)
            writer.end_page()
        writer.close()
        with open(path, 'rb') as f:
            raw = f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    bank, fmt = detect_bank_and_format(raw, 'lista.pdf')
    assert (bank, fmt) == ('ing', 'pdf')


# --- Parser mBank HTML ------------------------------------------------------

def test_parse_mbank_html_basic(app, mf_user):
    user_token, acc_id = mf_user
    with app.app_context():
        result = parse_mbank_html(MBANK_HTML_SAMPLE, user_token, main_account_id=acc_id)

    txs = result['transactions']
    assert len(txs) == 2
    assert all(t['account_id'] == acc_id for t in txs)
    assert result['skipped_count'] == 0


def test_parse_mbank_html_structured_title_and_contractor(app, mf_user):
    """HTML rozbija opis <br> na części: część 1 = czytelny tytuł (nie blob)."""
    user_token, acc_id = mf_user
    with app.app_context():
        txs = parse_mbank_html(MBANK_HTML_SAMPLE, user_token, main_account_id=acc_id)['transactions']

    assert txs[0]['title'] == "FIRMA TESTOWA SP Z OO, Dziecko"
    assert txs[1]['title'] == "SKLEPIK TESTOWY WARSZAWA"
    # pełne szczegóły zachowane w contractor (do analizy słów kluczowych)
    assert "PRZELEW ZEWNĘTRZNY" in (txs[0]['contractor'] or '')


def test_parse_mbank_html_amounts_and_counterparty(app, mf_user):
    user_token, acc_id = mf_user
    with app.app_context():
        txs = parse_mbank_html(MBANK_HTML_SAMPLE, user_token, main_account_id=acc_id)['transactions']

    assert txs[0]['amount'] == Decimal("440.00")
    assert txs[1]['amount'] == Decimal("-125.50")
    assert txs[0]['counterparty_account'] == "99888877776666555544443333"
    assert txs[1]['counterparty_account'] is None
    assert txs[0]['date'] == date(2026, 6, 30)


def test_parse_mbank_html_requires_account(app, mf_user):
    user_token, _ = mf_user
    with app.app_context():
        with pytest.raises(ValueError):
            parse_mbank_html(MBANK_HTML_SAMPLE, user_token, main_account_id=None)


def test_parse_mbank_html_date_range_extracted(app, mf_user):
    """Zakres dat z nagłówka — pod historię importów i wykrywanie nakładania."""
    user_token, acc_id = mf_user
    with app.app_context():
        result = parse_mbank_html(MBANK_HTML_SAMPLE, user_token, main_account_id=acc_id)

    assert result.get('period_start') == date(2026, 6, 1)
    assert result.get('period_end') == date(2026, 6, 30)


# --- Parser mBank PDF -------------------------------------------------------

def test_parse_mbank_pdf_basic(app, mf_user):
    user_token, acc_id = mf_user
    with app.app_context():
        result = parse_mbank_pdf(_build_mbank_pdf_bytes(), user_token, main_account_id=acc_id)

    txs = result['transactions']
    assert len(txs) == 2
    assert txs[0]['amount'] == Decimal("440.00")
    assert txs[1]['amount'] == Decimal("-125.50")
    assert txs[0]['counterparty_account'] == "99888877776666555544443333"
    assert txs[1]['counterparty_account'] is None
    assert txs[0]['date'] == date(2026, 6, 30)
    assert all(t['account_id'] == acc_id for t in txs)


def test_parse_mbank_pdf_polish_chars_preserved(app, mf_user):
    user_token, acc_id = mf_user
    with app.app_context():
        txs = parse_mbank_pdf(_build_mbank_pdf_bytes(), user_token, main_account_id=acc_id)['transactions']

    joined = " ".join((t['title'] or '') + " " + (t['contractor'] or '') for t in txs)
    assert "PŁATNOŚĆ" in joined or "PRZYCHODZĄCY" in joined


def test_parse_mbank_pdf_requires_account(app, mf_user):
    user_token, _ = mf_user
    with app.app_context():
        with pytest.raises(ValueError):
            parse_mbank_pdf(_build_mbank_pdf_bytes(), user_token, main_account_id=None)


def test_parse_mbank_pdf_date_on_own_line_title_fallback(app, mf_user):
    """Realny układ mBank PDF: data we WŁASNEJ linii — tytuł musi wtedy
    spaść na pierwszą linię szczegółów, nie być pusty."""
    import fitz
    import os
    import tempfile
    lines = [
        "mBank S.A. Bankowość Detaliczna",
        "Listaoperacjizaokresod2026-06-01do2026-06-30",
        "dla rachunków:",
        "Kowalski - 11111111111111111111111111",
        "Dataoperacji Opisoperacji Rachunek Kategoria Kwota",
        "2026-06-30",
        "FIRMA TESTOWA SP Z OO, Dziecko",
        "SZCZEGÓŁY PRZELEWU",
        "99888877776666555544443333",
        "Wpływy - inne 440,00 PLN",
    ]
    html = "".join(f"<p>{l}</p>" for l in lines)
    fd, path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    try:
        writer = fitz.DocumentWriter(path)
        story = fitz.Story(html)
        more = True
        while more:
            dev = writer.begin_page(fitz.paper_rect('a4'))
            more, _ = story.place(fitz.Rect(36, 36, 559, 806))
            story.draw(dev)
            writer.end_page()
        writer.close()
        with open(path, 'rb') as f:
            raw = f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    user_token, acc_id = mf_user
    with app.app_context():
        txs = parse_mbank_pdf(raw, user_token, main_account_id=acc_id)['transactions']

    assert len(txs) == 1
    assert txs[0]['title'] == "FIRMA TESTOWA SP Z OO, Dziecko"
    assert txs[0]['amount'] == Decimal("440.00")
