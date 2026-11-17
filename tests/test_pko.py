"""Import historii rachunku PKO BP w CSV.

Eksport z serwisu internetowego (windows-1250, przecinek, wszystko w cudzysłowach):
sześć nazwanych kolumn i do pięciu nienazwanych z polami opisu w postaci
„Etykieta: wartość”. Plik nie ma numeru własnego rachunku — „Rachunek
odbiorcy/nadawcy” to zawsze druga strona — więc konto wybiera użytkownik.

„Data operacji” to w praktyce dzień zaksięgowania, a „Data waluty” — dzień
transakcji (przy kartach równa „Data wykonania operacji”); bierzemy tę drugą.

Wszystkie dane zmyślone.
"""
import io
from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Account, TransactionStaging
from app.services.statement_parsers import BrakKontaError, detect_bank_and_format, parse_pko_csv

NAGLOWEK = '"Data operacji","Data waluty","Typ transakcji","Kwota","Waluta","Saldo po transakcji","Opis transakcji","","","",""\n'

PKO_CSV = NAGLOWEK + (
    # karta: kontrahent z lokalizacji, tytuł z typu (w „Tytuł” jest numer referencyjny)
    '"2026-11-12","2026-11-10","Płatność kartą","-9.00","PLN","+1000.00","Tytuł:  74410496314031574787474 ",'
    '"Lokalizacja: Adres: KAWIARNIA TESTOWA K123 Miasto: Warszawa Kraj: POLSKA","Data wykonania operacji: 2026-11-10",'
    '"Oryginalna kwota operacji: 9.00","Numer karty: 425125******0000"\n'
    # BLIK na telefon wychodzący — mimo „przychodz.” w typie; numery telefonów wycięte z tytułu
    '"2026-11-13","2026-11-13","Przelew na telefon przychodz. wew.","-25.50","PLN","+1009.00",'
    '"Rachunek odbiorcy: 11 1111 1111 1111 1111 1111 1111","Nazwa odbiorcy: JAN TESTOWY",'
    '"Tytuł: KAWA I CIASTKO  OD: 48500000001 DO: 485*****002","Referencje własne zleceniodawcy: 123456789",""\n'
    # wpływ z adresem nadawcy
    '"2026-10-28","2026-10-28","Przelew na konto","+5000.00","PLN","+6000.00",'
    '"Rachunek nadawcy: 22 2222 2222 2222 2222 2222 2222","Nazwa nadawcy: FIRMA TESTOWA SP. Z O.O.",'
    '"Adres nadawcy: UL. TESTOWA 1 00-001 WARSZAWA","Tytuł: Wynagrodzenie za październik 2026",""\n'
    # płatność w internecie kodem BLIK
    '"2026-10-30","2026-10-29","Płatność web - kod mobilny","-120.00","PLN","+880.00","Tytuł: 00000095289812831  ",'
    '"Numer telefonu: 48500000001","Lokalizacja: Adres: sklep.example.pl","\'Operacja: 00000095289812831",'
    '"Numer referencyjny: 00000095289812831"\n'
    # przelew bez tytułu → typ transakcji
    '"2026-10-29","2026-10-29","Przelew z rachunku","-300.00","PLN","+1000.00",'
    '"Rachunek odbiorcy: 33 3333 3333 3333 3333 3333 3333","Nazwa odbiorcy: ANNA TESTOWA","Tytuł:   ","",""\n'
)


@pytest.fixture
def pko(app, test_user):
    konto = Account(name='PKO osobiste', bank_name='PKO BP', user_token=test_user.token)
    db.session.add(konto)
    db.session.commit()
    return test_user.token, konto


def _po_typie(result):
    return {t['title']: t for t in result['transactions']}


# --- detekcja ---

def test_detekcja_pko_csv_w_windows_1250():
    assert detect_bank_and_format(PKO_CSV.encode('windows-1250'), 'x.csv') == ('pko', 'csv')


# --- parser ---

def test_platnosc_karta_kontrahent_z_lokalizacji_data_waluty(pko):
    token, konto = pko
    t = _po_typie(parse_pko_csv(PKO_CSV, token, main_account_id=konto.id))['Płatność kartą']

    assert t['amount'] == Decimal('-9.00')
    assert t['date'] == date(2026, 11, 10)  # Data waluty, nie Data operacji
    assert t['contractor'] == 'KAWIARNIA TESTOWA K123'
    assert t['counterparty_account'] is None
    assert t['account_id'] == konto.id


def test_przelew_na_telefon_znak_z_kwoty_i_tytul_bez_numerow_telefonow(pko):
    token, konto = pko
    t = _po_typie(parse_pko_csv(PKO_CSV, token, main_account_id=konto.id))['KAWA I CIASTKO']

    assert t['amount'] == Decimal('-25.50')
    assert t['contractor'] == 'JAN TESTOWY'
    assert t['counterparty_account'] == '11111111111111111111111111'


def test_wplyw_kontrahent_i_rachunek_nadawcy(pko):
    token, konto = pko
    t = _po_typie(parse_pko_csv(PKO_CSV, token, main_account_id=konto.id))['Wynagrodzenie za październik 2026']

    assert t['amount'] == Decimal('5000.00')
    assert t['contractor'] == 'FIRMA TESTOWA SP. Z O.O.'
    assert t['counterparty_account'] == '22222222222222222222222222'


def test_platnosc_web_i_przelew_bez_tytulu(pko):
    token, konto = pko
    po_typie = _po_typie(parse_pko_csv(PKO_CSV, token, main_account_id=konto.id))

    assert po_typie['Płatność web - kod mobilny']['contractor'] == 'sklep.example.pl'
    assert po_typie['Przelew z rachunku']['contractor'] == 'ANNA TESTOWA'


def test_wynik_okres_i_brak_numeru_rachunku(pko):
    token, konto = pko
    result = parse_pko_csv(PKO_CSV, token, main_account_id=konto.id)

    assert len(result['transactions']) == 5
    assert result['skipped_count'] == 0
    assert (result['period_start'], result['period_end']) == (date(2026, 10, 28), date(2026, 11, 13))
    assert result['statement_ibans'] == []
    assert all(t['bank_category'] is None for t in result['transactions'])


def test_parser_wymaga_konta(pko):
    token, _ = pko
    with pytest.raises(BrakKontaError):
        parse_pko_csv(PKO_CSV, token)


def test_waluta_wyciagu_musi_zgadzac_sie_z_kontem(pko):
    token, _ = pko
    eur = Account(name='PKO EUR', bank_name='PKO BP', user_token=token, currency='EUR')
    db.session.add(eur)
    db.session.commit()
    with pytest.raises(ValueError, match='PLN'):
        parse_pko_csv(PKO_CSV, token, main_account_id=eur.id)


def test_cudze_konto_odrzucone(pko, other_user):
    token, _ = pko
    obce = Account(name='Obce', bank_name='PKO BP', user_token=other_user.token)
    db.session.add(obce)
    db.session.commit()
    with pytest.raises(ValueError):
        parse_pko_csv(PKO_CSV, token, main_account_id=obce.id)


def test_wiersz_z_bledna_kwota_pominiety(pko):
    token, konto = pko
    zly = NAGLOWEK + '"2026-11-12","2026-11-10","Płatność kartą","abc","PLN","+1.00","Tytuł: x","","","",""\n'
    result = parse_pko_csv(zly, token, main_account_id=konto.id)
    assert result['transactions'] == []
    assert result['skipped_count'] == 1


# --- przez endpoint ---

def test_import_auto_do_poczekalni(logged_in_client, pko):
    _, konto = pko
    resp = logged_in_client.post('/api/import/auto',
                                 data={'file': (io.BytesIO(PKO_CSV.encode('windows-1250')), 'pko.csv'),
                                       'account_id': konto.id},
                                 content_type='multipart/form-data')
    assert resp.status_code == 201
    wiersze = db.session.query(TransactionStaging).filter_by(account_id=konto.id).all()
    assert len(wiersze) == 5
    assert sum(w.amount for w in wiersze) == Decimal('4545.50')


def test_import_auto_bez_konta_prosi_o_konto(logged_in_client, pko):
    resp = logged_in_client.post('/api/import/auto',
                                 data={'file': (io.BytesIO(PKO_CSV.encode('windows-1250')), 'pko.csv')},
                                 content_type='multipart/form-data')
    assert resp.status_code == 400
    assert resp.get_json()['needs_account'] is True
    assert db.session.query(TransactionStaging).count() == 0
