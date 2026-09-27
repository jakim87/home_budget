"""Kursy walut NBP (tabela A) i waluta konta.

Kursy służą wyłącznie do wyceny: saldo konta walutowego razy kurs daje jego
udział w Net Worth. Nie przewalutowujemy transakcji — stąd też reguła, że
przelew wewnętrzny między kontami w różnych walutach nie dostaje lustra
(kwota w PLN wylądowałaby na koncie w EUR jako euro).
"""
import urllib.error
from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Account, Category, Contractor, ExchangeRate, Transaction, TransactionStaging
from app.services import exchange_rate_service as ers
from app.services.account_service import create_account
from app.services.budget_service import create_transaction


def _tabela(dzien, **kursy):
    return {'effectiveDate': dzien, 'rates': [
        {'code': kod, 'currency': f'waluta {kod}', 'mid': Decimal(str(mid))} for kod, mid in kursy.items()
    ]}


@pytest.fixture
def nbp(monkeypatch):
    """Atrapa NBP: zwraca tabele z podanego słownika, zapisuje odpytane zakresy."""
    stan = {'tabele': [], 'zapytania': []}

    def pobierz(od, do):
        stan['zapytania'].append((od, do))
        return [t for t in stan['tabele'] if od.isoformat() <= t['effectiveDate'] <= do.isoformat()]

    monkeypatch.setattr(ers, '_pobierz_tabele', pobierz)
    return stan


# --- pobieranie ---

def test_pierwsze_pobranie_dociaga_historie_porcjami(app, nbp):
    nbp['tabele'] = [_tabela('2002-01-02', EUR=3.5), _tabela('2026-09-25', EUR=4.39)]

    ers.fetch_rates(today=date(2026, 9, 27))

    # NBP przyjmuje zakres najwyżej 93 dni — cała historia musi przyjść w porcjach.
    assert nbp['zapytania'][0][0] == ers.HISTORY_START
    assert nbp['zapytania'][-1][1] == date(2026, 9, 27)
    assert all((do - od).days < 93 for od, do in nbp['zapytania'])
    assert db.session.query(ExchangeRate).count() == 2


def test_kolejne_pobranie_zaczyna_od_dnia_po_ostatnim_kursie(app, nbp):
    nbp['tabele'] = [_tabela('2026-09-24', EUR=4.38, USD=3.85), _tabela('2026-09-25', EUR=4.39, USD=3.86)]
    db.session.add(ExchangeRate(currency='EUR', currency_name='euro', date=date(2026, 9, 24), rate=Decimal('4.38')))
    db.session.commit()

    ers.fetch_rates(today=date(2026, 9, 27))

    assert nbp['zapytania'] == [(date(2026, 9, 25), date(2026, 9, 27))]
    assert db.session.query(ExchangeRate).filter_by(date=date(2026, 9, 25)).count() == 2


def test_ponowne_pobranie_nie_duplikuje(app, nbp):
    nbp['tabele'] = [_tabela('2026-09-25', EUR=4.39)]
    ers.fetch_rates(today=date(2026, 9, 27))
    ers.fetch_rates(today=date(2026, 9, 27))
    assert db.session.query(ExchangeRate).count() == 1


def test_kurs_zapisany_dokladnie(app, nbp):
    """Forint ma 6 miejsc po przecinku — zaokrąglenie do 4 zmieniłoby wycenę o kilka %."""
    nbp['tabele'] = [_tabela('2026-09-25', HUF='0.011987')]
    ers.fetch_rates(today=date(2026, 9, 27))
    assert db.session.query(ExchangeRate).one().rate == Decimal('0.011987')


def test_stary_format_tabeli_nbp(app, nbp):
    """Tabele z początku historii mają 'country' zamiast 'currency', a EUR bywa w nich
    dwa razy (RFN i UGW) — duplikat złamałby unikalność (waluta, dzień)."""
    nbp['tabele'] = [{'effectiveDate': '2002-01-02', 'rates': [
        {'country': 'RFN', 'code': 'EUR', 'mid': Decimal('3.5496')},
        {'country': 'UGW', 'code': 'EUR', 'mid': Decimal('3.5496')},
    ]}]
    ers.fetch_rates(today=date(2002, 1, 3))
    kurs = db.session.query(ExchangeRate).one()
    assert (kurs.currency, kurs.rate) == ('EUR', Decimal('3.5496'))


def test_404_z_nbp_to_brak_tabel_nie_blad(app, monkeypatch):
    """Zakres bez dnia roboczego (weekend, święta) NBP zgłasza jako 404."""
    def urlopen(*a, **kw):
        raise urllib.error.HTTPError('u', 404, 'Not Found', {}, None)
    monkeypatch.setattr(ers.urllib.request, 'urlopen', urlopen)
    assert ers._pobierz_tabele(date(2026, 9, 26), date(2026, 9, 27)) == []


def test_blad_nbp_zachowuje_pobrane_porcje(app, monkeypatch):
    """Awaria w połowie historii nie kasuje tego, co już przyszło — kolejne uruchomienie dokończy."""
    wywolania = []

    def pobierz(od, do):
        wywolania.append(od)
        if len(wywolania) == 2:
            raise urllib.error.URLError('timeout')
        return [_tabela(od.isoformat(), EUR=4.0)]

    monkeypatch.setattr(ers, '_pobierz_tabele', pobierz)
    with pytest.raises(urllib.error.URLError):
        ers.fetch_rates(today=date(2026, 9, 27))
    assert db.session.query(ExchangeRate).count() == 1


def test_komenda_fetch_rates(app, nbp):
    nbp['tabele'] = [_tabela('2026-09-25', EUR=4.39)]
    wynik = app.test_cli_runner().invoke(args=['fetch-rates'])
    assert wynik.exit_code == 0, wynik.output
    assert db.session.query(ExchangeRate).count() == 1


# --- waluta konta ---

def _kurs(kod, dzien, rate, nazwa=None):
    db.session.add(ExchangeRate(currency=kod, currency_name=nazwa or kod.lower(), date=dzien, rate=Decimal(rate)))


def test_konto_domyslnie_w_pln(app, test_user):
    acc = create_account(test_user.token, {'name': 'Osobiste', 'bank_name': 'B'})
    assert acc.currency == 'PLN'


def test_konto_w_walucie_z_tabeli_nbp(app, test_user):
    _kurs('TRY', date(2026, 9, 25), '0.1180')
    db.session.commit()
    acc = create_account(test_user.token, {'name': 'Lira', 'bank_name': 'B', 'currency': 'try'})
    assert acc.currency == 'TRY'


def test_waluta_spoza_tabeli_odrzucona(app, test_user):
    with pytest.raises(ValueError):
        create_account(test_user.token, {'name': 'X', 'bank_name': 'B', 'currency': 'XYZ'})


def test_waluta_wycofana_odrzucona(app, test_user):
    _kurs('ATS', date(2002, 1, 2), '0.258')
    _kurs('EUR', date(2026, 9, 25), '4.39')
    db.session.commit()
    with pytest.raises(ValueError):
        create_account(test_user.token, {'name': 'X', 'bank_name': 'B', 'currency': 'ATS'})


def test_zmiana_waluty_konta_przez_api(logged_in_client, test_user):
    _kurs('EUR', date(2026, 9, 25), '4.39')
    acc = Account(name='Revolut', bank_name='R', user_token=test_user.token, balance=Decimal('100.00'))
    db.session.add(acc)
    db.session.commit()

    resp = logged_in_client.put(f'/api/accounts/{acc.id}', json={'currency': 'EUR'})

    assert resp.status_code == 200
    assert resp.get_json()['currency'] == 'EUR'
    db.session.refresh(acc)
    assert acc.currency == 'EUR'
    assert acc.balance == Decimal('100.00')  # zmiana waluty to korekta etykiety, nie przeliczenie


# --- /api/init ---

def test_init_podaje_kursy(logged_in_client, test_user):
    _kurs('EUR', date(2026, 7, 31), '4.25', 'euro')
    _kurs('EUR', date(2026, 8, 28), '4.30', 'euro')  # piątek — ostatni dzień roboczy sierpnia
    _kurs('EUR', date(2026, 9, 25), '4.39', 'euro')
    _kurs('USD', date(2026, 9, 25), '3.86', 'dolar amerykański')
    acc = Account(name='Euro', bank_name='R', user_token=test_user.token, currency='EUR')
    db.session.add(acc)
    db.session.commit()
    db.session.add(Transaction(user_token=test_user.token, account_id=acc.id, amount=Decimal('10'),
                               title='t', date=date(2026, 8, 5)))
    db.session.commit()

    data = logged_in_client.get('/api/init').get_json()

    assert data['accounts'][0]['currency'] == 'EUR'
    # Najnowsza tabela — wszystkie waluty, bo zasila też listę wyboru waluty konta.
    assert data['currencies']['USD'] == {'name': 'dolar amerykański', 'rate': 3.86, 'date': '2026-09-25'}
    # Kurs na koniec miesiąca = ostatni opublikowany w tym miesiącu lub wcześniej.
    assert data['monthly_rates']['EUR']['2026-08'] == 4.30
    assert data['monthly_rates']['EUR']['2026-09'] == 4.39
    assert 'USD' not in data['monthly_rates']  # tylko waluty kont użytkownika


# --- przelewy między walutami ---

@pytest.fixture
def pln_i_eur(app, test_user):
    pln = Account(name='PLN', bank_name='B', balance=Decimal('10000.00'), user_token=test_user.token)
    eur = Account(name='EUR', bank_name='B', balance=Decimal('0.00'), user_token=test_user.token, currency='EUR')
    cat = Category(name='Przelew wewnętrzny', type='transfer')
    db.session.add_all([pln, eur, cat])
    db.session.commit()
    do_eur = Contractor(name='Moje konto: EUR', user_token=test_user.token,
                        default_category_id=cat.id, linked_account_id=eur.id)
    db.session.add(do_eur)
    db.session.commit()
    return test_user.token, pln, eur, cat, do_eur


def test_przelew_na_konto_w_innej_walucie_bez_lustra(pln_i_eur):
    """4300 PLN wysłane na konto EUR nie może dopisać 4300 EUR."""
    token, pln, eur, cat, do_eur = pln_i_eur

    create_transaction(token, pln.id, Decimal('4300.00'), 'Wymiana', date(2026, 9, 1),
                       category_id=cat.id, contractor_id=do_eur.id)

    assert db.session.get(Account, pln.id).balance == Decimal('5700.00')
    assert db.session.get(Account, eur.id).balance == Decimal('0.00')
    assert db.session.query(Transaction).filter_by(account_id=eur.id).count() == 0


def test_przelew_miedzy_walutami_nie_paruje_sie_po_kwocie(pln_i_eur):
    """Zbieżność kwot między walutami jest przypadkowa — wiązanie nóg byłoby fałszywe."""
    token, pln, eur, cat, do_eur = pln_i_eur
    z_pln = Contractor(name='Moje konto: PLN', user_token=token, default_category_id=cat.id,
                       linked_account_id=pln.id)
    db.session.add(z_pln)
    db.session.commit()
    wplyw = Transaction(user_token=token, account_id=eur.id, amount=Decimal('1000.00'),
                        title='Wpływ', date=date(2026, 9, 1), category_id=cat.id,
                        contractor_id=z_pln.id, origin='import')
    db.session.add(wplyw)
    db.session.commit()

    tx = create_transaction(token, pln.id, Decimal('1000.00'), 'Wymiana', date(2026, 9, 1),
                            category_id=cat.id, contractor_id=do_eur.id)

    assert tx.linked_transaction_id is None
    assert db.session.get(Transaction, wplyw.id).linked_transaction_id is None


def test_poczekalnia_przelew_miedzy_walutami_to_missing(logged_in_client, pln_i_eur):
    """Zatwierdzenie nie dołoży lustra, więc plakietka 'mirror' kłamałaby."""
    token, pln, _, cat, do_eur = pln_i_eur
    stg = TransactionStaging(user_token=token, account_id=pln.id, amount=Decimal('-4300.00'),
                             title='Wymiana', date=date(2026, 9, 1), proposed_category_id=cat.id,
                             proposed_contractor_id=do_eur.id, status='pending')
    db.session.add(stg)
    db.session.commit()

    wiersze = {r['id']: r for r in logged_in_client.get('/api/staging/pending').get_json()}
    assert wiersze[stg.id]['transfer_pair'] == 'missing'
