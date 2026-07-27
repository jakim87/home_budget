"""Parser PDF dla ING (#106) — 'Lista transakcji', zwykle wielokontowa.

Bloki testowe odzwierciedlają REALNE kształty znalezione w prawdziwym pliku
(rozpoznanie w sesji, plik poza repo): płatność kartą, zlecenie stałe
(ST.ZLEC), przelew z zaokrągleniem walutowym (dodatkowa 'fałszywa' kwota PLN
przed właściwą), zwykły przelew (PRZELEW), oraz obie strony przelewu
wewnętrznego pokazane w tym samym pliku wielokontowym. Wszystkie dane
zmyślone.
"""
import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Account, User
from app.services.statement_parsers import (
    _extract_ing_pdf_accounts,
    _extract_ing_pdf_period,
    parse_ing_pdf,
)


def _build_ing_pdf_bytes(lines: list[str]) -> bytes:
    """Buduje minimalny PDF o układzie tekstu jak realny wyciąg ING —
    fitz.Story (HTML→PDF) osadza font unicode, więc polskie znaki przetrwają
    ekstrakcję (w przeciwieństwie do insert_text z fontami base-14)."""
    import fitz
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


HEADER_LINES = [
    "Dokument nr: 0000000000_000000",
    "Wygenerowany dnia: 01.07.2026, 12:00",
    "Lista transakcji",
    "Dane użytkownika",
    "Wybrane rachunki",
    "JAN TESTOWY KOWALSKI",
    "UL. TESTOWA 1",
    "00-001 WARSZAWA",
    "KONTO GŁÓWNE Direct (PLN)",
    "Wakacje testowe (PLN)",
    "11111111111111111111111111",
    "22222222222222222222222222",
    "Zastosowane kryteria wyboru",
    "Podsumowanie",
    "Zakres dat: 01.06.2026 - 30.06.2026",
    "Typy transakcji: Wszystkie",
    "Liczba transakcji: 4",
    "Data transakcji",
    "/data księgow.",
    "Dane kontrahenta",
    "Tytuł",
    "Szczegóły / nr transakcji",
    "Kwota",
    "Konto i saldo",
    "po transakcji",
]

CARD_PAYMENT_BLOCK = [
    "30.06.2026",
    "02.07.2026",
    "SKLEP TESTOWY 01 WARSZAWA",
    "9999999/00000",
    "Płatność kartą",
    "30.06.2026",
    "Nr karty 1234xx5678",
    "TR.KART",
    "Nr tr.: 100000000000001",
    "-25,50 PLN",
    "KONTO GŁÓWNE",
    "Direct",
    "9 974,50 PLN",
]

STANDING_ORDER_BLOCK = [
    "30.06.2026",
    "30.06.2026",
    "Jan Kowalski",
    "33333333333333333333333333",
    "Testowy Bank S.A.",
    "Fundusz testowy",
    "ST.ZLEC",
    "Nr tr.: 100000000000002",
    "-500,00 PLN",
    "KONTO GŁÓWNE",
    "Direct",
    "9 474,50 PLN",
]

FOREIGN_CURRENCY_ROUNDUP_BLOCK = [
    "28.06.2026",
    "28.06.2026",
    "SKLEP ZAGRANICZNY GMBH",
    "BERLIN NIEMCY",
    "Testowy Bank Zagraniczny",
    "przelew Wakacje testowe",
    "Płatność kartą",
    "26.06.2026",
    "10,00 EUR",
    "Kwota: 42,98 PLN",
    "Nr tr.: 100000000000003",
    "2,00 PLN",
    "Wakacje testowe",
    "102,00 PLN",
]

FOREIGN_CURRENCY_CARD_PAYMENT_BLOCK = [
    "26.06.2026",
    "28.06.2026",
    "Sklep Zagraniczny EUR Berlin",
    "1234567/89012",
    "Płatność kartą",
    "26.06.2026",
    "10,00 EUR",
    "Nr karty 1234xx5678",
    "TR.KART",
    "Nr tr.: 100000000000007",
    "-42,98 PLN",
    "kwota płatności:",
    "-10,00 EUR",
    "KONTO GŁÓWNE",
    "Direct",
    "14 431,43 PLN",
]

PLAIN_PRZELEW_BLOCK = [
    "29.06.2026",
    "29.06.2026",
    "ANNA TESTOWA",
    "UL. PRZYKŁADOWA 2",
    "00-002 KRAKÓW",
    "44444444444444444444444444",
    "Testowy Bank S.A.",
    "Zwrot za zakupy",
    "PRZELEW",
    "Nr tr.: 100000000000004",
    "15,00 PLN",
    "KONTO GŁÓWNE",
    "Direct",
    "9 989,50 PLN",
]

# Obie strony JEDNEGO przelewu wewnętrznego (KONTO GŁÓWNE -> Wakacje testowe),
# pokazane w tym samym pliku wielokontowym — jak w realnym eksporcie "all_accounts".
INTERNAL_TRANSFER_INFLOW_BLOCK = [
    "27.06.2026",
    "27.06.2026",
    "JAN TESTOWY KOWALSKI",
    "UL. TESTOWA 1",
    "00-001 WARSZAWA",
    "11111111111111111111111111",
    "Testowy Bank S.A.",
    "Wakacje testowe",
    "ST.ZLEC",
    "Nr tr.: 100000000000005",
    "300,00 PLN",
    "Wakacje testowe",
    "300,00 PLN",
]
INTERNAL_TRANSFER_OUTFLOW_BLOCK = [
    "27.06.2026",
    "27.06.2026",
    "Jan Kowalski",
    "22222222222222222222222222",
    "Testowy Bank S.A.",
    "Wakacje testowe",
    "ST.ZLEC",
    "Nr tr.: 100000000000005",
    "-300,00 PLN",
    "KONTO GŁÓWNE",
    "Direct",
    "9 674,50 PLN",
]

FOOTER_LINES = [
    "Dokument ma charakter informacyjny, nie stanowi dowodu księgowego.",
    "Strona: 1 z 1. Lista transakcji",
]


def _full_pdf(*blocks) -> bytes:
    lines = list(HEADER_LINES)
    for b in blocks:
        lines.extend(b)
    lines.extend(FOOTER_LINES)
    return _build_ing_pdf_bytes(lines)


@pytest.fixture
def ing_pdf_user(app):
    """Konta z numerami zgodnymi z HEADER_LINES (KONTO GŁÓWNE, Wakacje testowe)."""
    user = User(username="ing_pdf_user", email="ipdf@test.com", password_hash="a")
    db.session.add(user)
    db.session.commit()
    main_acc = Account(name="Moje Konto Główne", bank_name="ING", user_token=user.token,
                       account_number="11 1111 1111 1111 1111 1111 1111")
    wakacje_acc = Account(name="Wakacje testowe", bank_name="ING", user_token=user.token,
                          account_number="22 2222 2222 2222 2222 2222 2222")
    db.session.add_all([main_acc, wakacje_acc])
    db.session.commit()
    return user.token, main_acc.id, wakacje_acc.id


# --- Pomocnicze: nagłówek (okres, konta) ------------------------------------

def test_extract_ing_pdf_period():
    text = "\n".join(HEADER_LINES)
    start, end = _extract_ing_pdf_period(text)
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 30)


def test_extract_ing_pdf_accounts_pairs_labels_with_ibans():
    entries = _extract_ing_pdf_accounts(HEADER_LINES)
    assert entries == [
        ("KONTO GŁÓWNE Direct", "11111111111111111111111111"),
        ("Wakacje testowe", "22222222222222222222222222"),
    ]


# --- Parser: kształty bloków -------------------------------------------------

def test_parse_ing_pdf_card_payment(app, ing_pdf_user):
    token, main_id, _ = ing_pdf_user
    raw = _full_pdf(CARD_PAYMENT_BLOCK)
    result = parse_ing_pdf(raw, token)

    txs = result['transactions']
    assert len(txs) == 1
    assert txs[0]['date'] == date(2026, 6, 30)
    assert txs[0]['amount'] == Decimal('-25.50')
    assert txs[0]['account_id'] == main_id
    assert txs[0]['title'] == 'SKLEP TESTOWY 01 WARSZAWA'


def test_parse_ing_pdf_standing_order(app, ing_pdf_user):
    token, main_id, _ = ing_pdf_user
    raw = _full_pdf(STANDING_ORDER_BLOCK)
    txs = parse_ing_pdf(raw, token)['transactions']

    assert len(txs) == 1
    assert txs[0]['amount'] == Decimal('-500.00')
    assert txs[0]['account_id'] == main_id
    assert txs[0]['counterparty_account'] == '33333333333333333333333333'


def test_parse_ing_pdf_foreign_currency_takes_last_two_amounts_not_first(app, ing_pdf_user):
    """Kluczowy test odporności: blok ma TRZY dopasowania 'X,XX PLN'
    ('Kwota: 42,98 PLN' to fałszywa referencja przeliczenia waluty) — kwota
    transakcji i saldo muszą być brane OD KOŃCA (przedostatnie/ostatnie),
    nie od początku, inaczej złapalibyśmy błędną wartość 42,98."""
    token, main_id, wakacje_id = ing_pdf_user
    raw = _full_pdf(FOREIGN_CURRENCY_ROUNDUP_BLOCK)
    txs = parse_ing_pdf(raw, token)['transactions']

    assert len(txs) == 1
    assert txs[0]['amount'] == Decimal('2.00')
    assert txs[0]['account_id'] == wakacje_id


def test_parse_ing_pdf_foreign_currency_card_payment_skips_kwota_platnosci_label(app, ing_pdf_user):
    """Płatność kartą w walucie obcej wstawia między kwotą PLN a etykietą konta
    parę linii 'kwota płatności:' + kwota w walucie oryginalnej — muszą być
    pominięte przy budowaniu etykiety konta, inaczej dopasowanie konta zawodzi
    (odkryte w złotym teście na realnym pliku — #106)."""
    token, main_id, _ = ing_pdf_user
    raw = _full_pdf(FOREIGN_CURRENCY_CARD_PAYMENT_BLOCK)
    txs = parse_ing_pdf(raw, token)['transactions']

    assert len(txs) == 1
    assert txs[0]['amount'] == Decimal('-42.98')
    assert txs[0]['account_id'] == main_id


def test_parse_ing_pdf_plain_przelew(app, ing_pdf_user):
    token, main_id, _ = ing_pdf_user
    raw = _full_pdf(PLAIN_PRZELEW_BLOCK)
    txs = parse_ing_pdf(raw, token)['transactions']

    assert len(txs) == 1
    assert txs[0]['amount'] == Decimal('15.00')
    assert txs[0]['account_id'] == main_id


def test_parse_ing_pdf_skips_inflow_side_of_internal_transfer(app, ing_pdf_user):
    """Obie strony przelewu wewnętrznego w tym samym pliku — strona dodatnia
    (wpływ) jest pomijana, tak jak w parserze CSV; lustro powstanie przy
    zatwierdzeniu strony wypływu."""
    token, main_id, wakacje_id = ing_pdf_user
    raw = _full_pdf(INTERNAL_TRANSFER_INFLOW_BLOCK, INTERNAL_TRANSFER_OUTFLOW_BLOCK)
    result = parse_ing_pdf(raw, token)

    txs = result['transactions']
    assert len(txs) == 1
    assert txs[0]['amount'] == Decimal('-300.00')
    assert txs[0]['account_id'] == main_id
    assert result['skipped_count'] == 1


def test_parse_ing_pdf_skips_unknown_subaccount(app, ing_pdf_user):
    """Podkonto/cel spoza słownika apki nie jest zgadywane — pomijane."""
    token, main_id, _ = ing_pdf_user
    unknown_sub_block = [
        "26.06.2026",
        "26.06.2026",
        "JAN TESTOWY KOWALSKI",
        "UL. TESTOWA 1",
        "00-001 WARSZAWA",
        "11111111111111111111111111",
        "Testowy Bank S.A.",
        "przelew iPad",
        "Płatność kartą",
        "24.06.2026",
        "Nr karty 1234xx5678",
        "TR.KART",
        "Nr tr.: 100000000000006",
        "3,00 PLN",
        "iPad cel",
        "50,00 PLN",
    ]
    raw = _full_pdf(unknown_sub_block)
    result = parse_ing_pdf(raw, token)
    assert result['transactions'] == []
    assert result['skipped_count'] == 1


def test_parse_ing_pdf_multiple_blocks_all_parsed(app, ing_pdf_user):
    token, main_id, wakacje_id = ing_pdf_user
    raw = _full_pdf(CARD_PAYMENT_BLOCK, STANDING_ORDER_BLOCK, PLAIN_PRZELEW_BLOCK)
    txs = parse_ing_pdf(raw, token)['transactions']
    assert len(txs) == 3
    assert [t['amount'] for t in txs] == [Decimal('-25.50'), Decimal('-500.00'), Decimal('15.00')]


def test_parse_ing_pdf_period_returned(app, ing_pdf_user):
    token, _, _ = ing_pdf_user
    raw = _full_pdf(CARD_PAYMENT_BLOCK)
    result = parse_ing_pdf(raw, token)
    assert result['period_start'] == date(2026, 6, 1)
    assert result['period_end'] == date(2026, 6, 30)


def test_parse_ing_pdf_single_account_mode_requires_main_account_id(app):
    """Plik bez sekcji 'Wybrane rachunki' (jednokontowy) — wymaga wskazania konta."""
    user = User(username="ing_pdf_single_user", email="ipdfs@test.com", password_hash="a")
    db.session.add(user)
    db.session.commit()

    single_header = [
        "Dokument nr: 0000000000_000000",
        "Lista transakcji",
        "Zakres dat: 01.06.2026 - 30.06.2026",
        "Data transakcji",
    ]
    lines = single_header + CARD_PAYMENT_BLOCK + FOOTER_LINES
    raw = _build_ing_pdf_bytes(lines)

    with pytest.raises(ValueError):
        parse_ing_pdf(raw, user.token, main_account_id=None)
