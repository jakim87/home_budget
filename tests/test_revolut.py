"""Import wyciągów Revolut (CSV) i parowanie wymiany walut między subkontami.

Revolut to jeden rachunek z subkontami walutowymi (wspólny IBAN litewski), a
eksport CSV nie ma numeru rachunku — konto wybiera użytkownik, a kolumna
'Waluta' pilnuje, żeby wyciąg EUR nie trafił na konto PLN.

Wymiana PLN→EUR to dwie nogi w dwóch plikach o identycznym znaczniku czasu.
Kwoty różnią się o kurs, więc parujemy je po dniu, znaku i tytule (który niesie
znacznik czasu co do sekundy), nie po kwocie.
"""
from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Account, Category, Transaction, TransactionStaging
from app.services.budget_service import save_transactions_to_staging
from app.services.statement_parsers import detect_bank_and_format, parse_revolut_csv

NAGLOWEK = 'Rodzaj,Produkt,Data rozpoczęcia,Data zrealizowania,Opis,Kwota,Opłata,Waluta,State,Saldo\n'

PLN_CSV = NAGLOWEK + (
    'Zasilenie,Bieżące,2026-05-07 19:28:23,2026-05-07 19:29:02,Zasilenie o *4971,2000.00,0.00,PLN,ZAKOŃCZONO,2000.00\n'
    'Wymiana,Bieżące,2026-05-07 19:29:20,2026-05-07 19:29:20,Wymiana na EUR,-2000.00,0.00,PLN,ZAKOŃCZONO,0.00\n'
    'Płatność kartą,Bieżące,2026-06-25 19:54:49,,Self Vending,-8.22,0.00,PLN,OCZEKUJĄCE,\n'
)

EUR_CSV = NAGLOWEK + (
    'Wymiana,Bieżące,2026-05-07 19:29:20,2026-05-07 19:29:20,Wymiana na EUR,469.98,0.00,EUR,ZAKOŃCZONO,688.36\n'
    'Wymiana,Bieżące,2026-05-23 17:48:57,2026-05-23 17:48:57,Wymiana na EUR,140.72,1.41,EUR,ZAKOŃCZONO,827.67\n'
    'Płatność kartą,Bieżące,2026-05-26 15:19:27,2026-05-27 19:10:15,My Cicero,-3.00,0.00,EUR,ZAKOŃCZONO,824.67\n'
    'Płatność kartą,Bieżące,2026-05-26 11:26:18,2026-05-27 19:10:16,My Cicero,-3.00,0.00,EUR,ZAKOŃCZONO,821.67\n'
)


@pytest.fixture
def revolut(app, test_user):
    pln = Account(name='Revolut PLN', bank_name='Revolut', user_token=test_user.token)
    eur = Account(name='Revolut EUR', bank_name='Revolut', user_token=test_user.token, currency='EUR')
    db.session.add_all([pln, eur, Category(name='Przelew wewnętrzny', type='transfer')])
    db.session.commit()
    return test_user.token, pln, eur


def _po_tytule(result):
    return {t['title']: t for t in result['transactions']}


# --- detekcja ---

def test_detekcja_csv_revolut():
    assert detect_bank_and_format(PLN_CSV.encode('utf-8'), 'x.csv') == ('revolut', 'csv')


# --- parser ---

def test_parser_data_realizacji_i_pomija_niezakonczone(revolut):
    token, pln, _ = revolut
    result = parse_revolut_csv(PLN_CSV, token, main_account_id=pln.id)

    assert result['skipped_count'] == 1  # OCZEKUJĄCE
    zasilenie = _po_tytule(result)['Zasilenie 2026-05-07 19:28:23']
    assert zasilenie['amount'] == Decimal('2000.00')
    assert zasilenie['contractor'] == 'Zasilenie o *4971'
    assert zasilenie['date'] == date(2026, 5, 7)


def test_parser_oplata_osobna_transakcja(revolut):
    token, _, eur = revolut
    tx = _po_tytule(parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id))

    assert tx['Wymiana 2026-05-23 17:48:57']['amount'] == Decimal('140.72')
    oplata = tx['Opłata: Wymiana 2026-05-23 17:48:57']
    assert oplata['amount'] == Decimal('-1.41')
    assert oplata['contractor'] == 'Revolut'


def test_parser_suma_zgadza_sie_z_saldem_revoluta(revolut):
    """Kwoty z opłatami muszą odtworzyć saldo końcowe z pliku — inaczej coś ginie."""
    token, _, eur = revolut
    result = parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id)
    saldo_poczatkowe = Decimal('688.36') - Decimal('469.98')
    assert saldo_poczatkowe + sum(t['amount'] for t in result['transactions']) == Decimal('821.67')


def test_dwie_identyczne_platnosci_tego_samego_dnia_nie_sa_duplikatem(revolut):
    """Dwa bilety po 3 EUR tego samego dnia — deduplikacja importu porównuje tytuł,
    więc bez znacznika czasu w tytule jeden by zniknął."""
    token, _, eur = revolut
    result = parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id)
    zapisane = save_transactions_to_staging(result['transactions'], user_token=token)
    assert sum(1 for s in zapisane if s.contractor == 'My Cicero') == 2


def test_waluta_wyciagu_musi_zgadzac_sie_z_kontem(revolut):
    token, pln, _ = revolut
    with pytest.raises(ValueError, match='EUR'):
        parse_revolut_csv(EUR_CSV, token, main_account_id=pln.id)


def test_parser_wymaga_konta(revolut):
    token, _, _ = revolut
    with pytest.raises(ValueError):
        parse_revolut_csv(PLN_CSV, token, main_account_id=None)


# --- wymiana walut jako przelew wewnętrzny ---

def test_wymiana_wskazuje_subkonto_w_drugiej_walucie(revolut):
    token, pln, eur = revolut
    wyplyw = _po_tytule(parse_revolut_csv(PLN_CSV, token, main_account_id=pln.id))['Wymiana 2026-05-07 19:29:20']
    wplyw = _po_tytule(parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id))['Wymiana 2026-05-07 19:29:20']
    assert wyplyw['transfer_account_id'] == eur.id
    assert wplyw['transfer_account_id'] == pln.id


def test_wymiana_bez_jednoznacznego_subkonta_zostaje_zwykla_operacja(revolut):
    """Dwa inne konta Revolut w drugiej walucie przy „Wymiana na EUR" z pliku EUR —
    nie wiadomo, skąd przyszły pieniądze, więc nie zgadujemy."""
    token, pln, eur = revolut
    db.session.add(Account(name='Revolut USD', bank_name='Revolut', user_token=token, currency='USD'))
    db.session.commit()
    wplyw = _po_tytule(parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id))['Wymiana 2026-05-07 19:29:20']
    assert wplyw.get('transfer_account_id') is None


def test_ponowna_analiza_nie_gubi_wymiany(revolut):
    from app.services.budget_service import reanalyze_all_staging
    token, pln, eur = revolut
    save_transactions_to_staging(parse_revolut_csv(PLN_CSV, token, main_account_id=pln.id)['transactions'], token)
    noga = db.session.query(TransactionStaging).filter_by(title='Wymiana 2026-05-07 19:29:20').one()
    przed = noga.proposed_contractor_id
    assert przed is not None

    reanalyze_all_staging(token)

    db.session.refresh(noga)
    assert noga.proposed_contractor_id == przed


def _zatwierdz(client, stg):
    resp = client.post(f'/api/staging/{stg.id}/approve',
                       json={'category': 'Przelew wewnętrzny', 'contractor_id': stg.proposed_contractor_id})
    assert resp.status_code in (200, 201), resp.get_json()


def test_wymiana_paruje_obie_nogi_w_roznych_walutach(logged_in_client, revolut):
    token, pln, eur = revolut
    save_transactions_to_staging(parse_revolut_csv(PLN_CSV, token, main_account_id=pln.id)['transactions'], token)
    save_transactions_to_staging(parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id)['transactions'], token)
    nogi = db.session.query(TransactionStaging).filter_by(title='Wymiana 2026-05-07 19:29:20').all()
    assert len(nogi) == 2

    stany = {r['id']: r.get('transfer_pair') for r in logged_in_client.get('/api/staging/pending').get_json()}
    assert all(stany[n.id] == 'staging' for n in nogi)

    for n in nogi:
        _zatwierdz(logged_in_client, n)

    wyplyw = db.session.query(Transaction).filter_by(account_id=pln.id, title='Wymiana 2026-05-07 19:29:20').one()
    wplyw = db.session.query(Transaction).filter_by(account_id=eur.id, title='Wymiana 2026-05-07 19:29:20').one()
    assert wyplyw.linked_transaction_id == wplyw.id
    assert wplyw.linked_transaction_id == wyplyw.id
    # Bez luster: każde konto ma dokładnie swoją nogę z wyciągu.
    assert db.session.get(Account, pln.id).balance == Decimal('-2000.00')
    assert db.session.get(Account, eur.id).balance == Decimal('469.98')


def test_edycja_kwoty_wymiany_nie_rusza_nogi_w_drugiej_walucie(logged_in_client, revolut):
    """Kwoty nóg wymiany dzieli kurs — poprawka jednej nie może przepisać drugiej."""
    token, pln, eur = revolut
    save_transactions_to_staging(parse_revolut_csv(PLN_CSV, token, main_account_id=pln.id)['transactions'], token)
    save_transactions_to_staging(parse_revolut_csv(EUR_CSV, token, main_account_id=eur.id)['transactions'], token)
    for n in db.session.query(TransactionStaging).filter_by(title='Wymiana 2026-05-07 19:29:20').all():
        _zatwierdz(logged_in_client, n)
    wyplyw = db.session.query(Transaction).filter_by(account_id=pln.id, title='Wymiana 2026-05-07 19:29:20').one()

    resp = logged_in_client.put(f'/api/transactions/{wyplyw.id}', json={'amount': '2001.00'})
    assert resp.status_code == 200

    db.session.expire_all()
    wplyw = db.session.query(Transaction).filter_by(account_id=eur.id, title='Wymiana 2026-05-07 19:29:20').one()
    # Edytowana noga zachowuje kierunek (wypływ), druga zostaje co do grosza.
    assert db.session.get(Transaction, wyplyw.id).amount == Decimal('-2001.00')
    assert wplyw.amount == Decimal('469.98')
    assert db.session.get(Account, pln.id).balance == Decimal('-2001.00')
    assert db.session.get(Account, eur.id).balance == Decimal('469.98')
    assert wplyw.linked_transaction_id == wyplyw.id
