"""Testy planowania budzetu miesiecznego (#96).

Kolejnosc wg planu docs/plan_budzet_miesieczny.md: RED przed implementacja.
Najgrozniejszy blad w tym module to podwojne liczenie transakcji cyklicznej
(raz jako projekcja, raz jako wykonana) i ciche gubienie kwot przy podzialach —
oba maja tu wlasny test.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import db
from app.models import (Account, Category, Frequency, RecurringTransaction,
                        Transaction, TransactionSplit)
from app.services import budget_plan_service as bps


@pytest.fixture
def konto(app, test_user_token):
    a = Account(name="Bieżące", bank_name="ING", balance=Decimal("0.00"),
                user_token=test_user_token)
    db.session.add(a)
    db.session.commit()
    return a


@pytest.fixture
def kategorie(app, test_user_token):
    """Komplet typow: wydatek, przychod, przelew wewnetrzny."""
    kat = {
        'jedzenie': Category(name="Jedzenie", type="expense", user_token=test_user_token),
        'remont': Category(name="Remont", type="expense", user_token=test_user_token),
        'ogrod': Category(name="Ogród", type="expense", user_token=test_user_token),
        'pensja': Category(name="Wynagrodzenie", type="income", user_token=test_user_token),
        'przelew': Category(name="Przelew własny", type="transfer", user_token=test_user_token),
    }
    db.session.add_all(kat.values())
    db.session.commit()
    return kat


def _tx(user_token, konto, kategoria, kwota, dzien, splity=None):
    t = Transaction(date=dzien, title="test", amount=Decimal(kwota),
                    account_id=konto.id, user_token=user_token,
                    category_id=kategoria.id if kategoria else None)
    for kat_split, kwota_split in (splity or []):
        t.splits.append(TransactionSplit(amount=Decimal(kwota_split),
                                         category_id=kat_split.id))
    db.session.add(t)
    db.session.commit()
    return t


# --- D4 / R1: podzialy ---

def test_podzialy_licza_sie_do_swoich_kategorii_nie_rodzica(app, test_user_token, konto, kategorie):
    """Wydatek 300 zl rozbity w calosci na Remont 200 + Ogrod 100.

    Kategoria rodzica (Jedzenie) ma dostac 0 — rozbicie zastepuje ja calkowicie.
    Podzialy sa w bazie DODATNIE, wiec musza odziedziczyc znak rodzica.
    """
    _tx(test_user_token, konto, kategorie['jedzenie'], "-300.00", date(2026, 5, 10),
        splity=[(kategorie['remont'], "200.00"), (kategorie['ogrod'], "100.00")])

    wyk = bps.wykonanie_per_kategoria(test_user_token, 2026, 5)

    assert wyk.get(kategorie['remont'].id) == Decimal("-200.00")
    assert wyk.get(kategorie['ogrod'].id) == Decimal("-100.00")
    assert wyk.get(kategorie['jedzenie'].id, Decimal("0")) == Decimal("0")


def test_reszta_niepodzielona_zostaje_na_kategorii_rodzica(app, test_user_token, konto, kategorie):
    """Podzial niepelny (300 zl, opisane tylko 200) — 100 zl nie moze wyparowac.

    Niezmiennik: suma po wszystkich kategoriach == suma kwot transakcji.
    """
    _tx(test_user_token, konto, kategorie['jedzenie'], "-300.00", date(2026, 5, 10),
        splity=[(kategorie['remont'], "200.00")])

    wyk = bps.wykonanie_per_kategoria(test_user_token, 2026, 5)

    assert wyk.get(kategorie['remont'].id) == Decimal("-200.00")
    assert wyk.get(kategorie['jedzenie'].id) == Decimal("-100.00")
    assert sum(wyk.values()) == Decimal("-300.00")


def test_transakcja_bez_podzialow_liczy_sie_normalnie(app, test_user_token, konto, kategorie):
    _tx(test_user_token, konto, kategorie['jedzenie'], "-150.50", date(2026, 5, 3))
    _tx(test_user_token, konto, kategorie['pensja'], "8000.00", date(2026, 5, 5))

    wyk = bps.wykonanie_per_kategoria(test_user_token, 2026, 5)

    assert wyk[kategorie['jedzenie'].id] == Decimal("-150.50")
    assert wyk[kategorie['pensja'].id] == Decimal("8000.00")


def test_wykonanie_nie_wychodzi_poza_miesiac(app, test_user_token, konto, kategorie):
    _tx(test_user_token, konto, kategorie['jedzenie'], "-100.00", date(2026, 4, 30))
    _tx(test_user_token, konto, kategorie['jedzenie'], "-200.00", date(2026, 5, 1))
    _tx(test_user_token, konto, kategorie['jedzenie'], "-400.00", date(2026, 6, 1))

    assert bps.wykonanie_per_kategoria(test_user_token, 2026, 5) == {
        kategorie['jedzenie'].id: Decimal("-200.00")
    }


# --- D9: transfery poza planowaniem ---

def test_nie_da_sie_zaplanowac_kategorii_transferowej(app, test_user_token, kategorie):
    with pytest.raises(ValueError):
        bps.ustaw_plan(test_user_token, 2026, 5, kategorie['przelew'].id, Decimal("500.00"))


def test_transfer_nie_pojawia_sie_na_liscie_budzetu(app, test_user_token, konto, kategorie):
    _tx(test_user_token, konto, kategorie['przelew'], "-1000.00", date(2026, 5, 7))

    lista = bps.lista_budzetu(test_user_token, 2026, 5)
    idki = {p['category_id'] for p in lista['pozycje']}

    assert kategorie['przelew'].id not in idki


# --- D3: rezerwacje z harmonogramu ---

def test_cykliczna_w_przyszlosci_rezerwuje_a_nie_wykonuje(app, test_user_token, konto, kategorie):
    dzis = date.today()
    przyszla = dzis + timedelta(days=3)
    db.session.add(RecurringTransaction(
        user_token=test_user_token, account_id=konto.id, category_id=kategorie['jedzenie'].id,
        title="Abonament", amount=Decimal("-99.00"), frequency=Frequency.MONTHLY,
        interval=1, day_of_month=przyszla.day, start_date=przyszla, next_run_date=przyszla))
    db.session.commit()

    y, m = przyszla.year, przyszla.month
    rez = bps.rezerwacje_per_kategoria(test_user_token, y, m)
    wyk = bps.wykonanie_per_kategoria(test_user_token, y, m)

    assert rez.get(kategorie['jedzenie'].id) == Decimal("-99.00")
    assert wyk.get(kategorie['jedzenie'].id, Decimal("0")) == Decimal("0")


def test_cykliczna_juz_wykonana_nie_liczy_sie_podwojnie(app, test_user_token, konto, kategorie):
    """Harmonogram wykonal sie na poczatku miesiaca: jest transakcja, a next_run_date
    przesunal sie na kolejny miesiac. Rezerwacja w tym miesiacu ma byc zerowa."""
    dzis = date.today()
    wykonana = dzis - timedelta(days=2)
    nastepna = dzis + timedelta(days=28)
    rt = RecurringTransaction(
        user_token=test_user_token, account_id=konto.id, category_id=kategorie['jedzenie'].id,
        title="Abonament", amount=Decimal("-99.00"), frequency=Frequency.MONTHLY,
        interval=1, day_of_month=wykonana.day, start_date=wykonana, next_run_date=nastepna)
    db.session.add(rt)
    db.session.commit()
    _tx(test_user_token, konto, kategorie['jedzenie'], "-99.00", wykonana)

    y, m = dzis.year, dzis.month
    assert bps.rezerwacje_per_kategoria(test_user_token, y, m).get(
        kategorie['jedzenie'].id, Decimal("0")) == Decimal("0")
    assert bps.wykonanie_per_kategoria(test_user_token, y, m)[
        kategorie['jedzenie'].id] == Decimal("-99.00")


# --- D2: bilans planu ---

def test_bilans_planu_ujemny_gdy_wydatki_przekraczaja_przychody(app, test_user_token, kategorie):
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['pensja'].id, Decimal("5000.00"))
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("4000.00"))
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['remont'].id, Decimal("2000.00"))

    lista = bps.lista_budzetu(test_user_token, 2026, 5)

    assert lista['planowane_przychody'] == Decimal("5000.00")
    assert lista['planowane_wydatki'] == Decimal("6000.00")
    assert lista['bilans_planu'] == Decimal("-1000.00")


def test_ustaw_plan_nadpisuje_zamiast_dublowac(app, test_user_token, kategorie):
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("1000.00"))
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("1200.00"))

    pozycje = [p for p in bps.lista_budzetu(test_user_token, 2026, 5)['pozycje']
               if p['category_id'] == kategorie['jedzenie'].id]

    assert len(pozycje) == 1
    assert pozycje[0]['plan'] == Decimal("1200.00")


def test_usun_plan_zostawia_kategorie_bez_planu(app, test_user_token, kategorie):
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("1000.00"))
    bps.usun_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id)

    pozycja = next(p for p in bps.lista_budzetu(test_user_token, 2026, 5)['pozycje']
                   if p['category_id'] == kategorie['jedzenie'].id)

    assert pozycja['plan'] is None


def test_nie_da_sie_zaplanowac_cudzej_kategorii(app, test_user_token, other_user):
    cudza = Category(name="Cudza", type="expense", user_token=other_user.token)
    db.session.add(cudza)
    db.session.commit()

    with pytest.raises(ValueError):
        bps.ustaw_plan(test_user_token, 2026, 5, cudza.id, Decimal("100.00"))


# --- D7/D8: sugestie ---

def test_sugestia_to_mediana_nie_srednia(app, test_user_token, konto, kategorie):
    """400, 380, 420, 3200, 390, 410 -> mediana 405 (srednia dalaby 866)."""
    kwoty = ["-400.00", "-380.00", "-420.00", "-3200.00", "-390.00", "-410.00"]
    for i, kwota in enumerate(kwoty):
        _tx(test_user_token, konto, kategorie['jedzenie'], kwota, date(2025, 12 - i, 15))

    s = bps.zaproponuj_plan(test_user_token, 2026, 6, kategorie['jedzenie'].id)

    assert s['kwota'] == Decimal("405.00")
    assert s['zakres_min'] == Decimal("380.00")
    assert s['zakres_max'] == Decimal("3200.00")
    assert s['liczba_miesiecy'] == 6


def test_ponizej_trzech_miesiecy_brak_sugestii_z_powodem(app, test_user_token, konto, kategorie):
    _tx(test_user_token, konto, kategorie['jedzenie'], "-400.00", date(2026, 4, 10))
    _tx(test_user_token, konto, kategorie['jedzenie'], "-420.00", date(2026, 5, 10))

    s = bps.zaproponuj_plan(test_user_token, 2026, 6, kategorie['jedzenie'].id)

    assert s['kwota'] is None
    assert s['liczba_miesiecy'] == 2
    assert 'za mało danych' in s['podstawa'].lower()


def test_sugestia_uwzglednia_podzialy(app, test_user_token, konto, kategorie):
    """Kategoria Remont wystepuje WYLACZNIE w podzialach — sugestia musi ja widziec."""
    for miesiac in (1, 2, 3, 4):
        _tx(test_user_token, konto, kategorie['jedzenie'], "-500.00", date(2026, miesiac, 10),
            splity=[(kategorie['remont'], "500.00")])

    s = bps.zaproponuj_plan(test_user_token, 2026, 6, kategorie['remont'].id)

    assert s['liczba_miesiecy'] >= 4
    assert s['kwota'] == Decimal("500.00")


def test_rok_temu_dopiero_od_dwunastu_miesiecy(app, test_user_token, konto, kategorie):
    """Ponizej 12 miesiecy historii nie pokazujemy porownania rok do roku."""
    for i in range(6):
        _tx(test_user_token, konto, kategorie['jedzenie'], "-400.00", date(2026, i + 1, 10))

    assert bps.zaproponuj_plan(test_user_token, 2026, 8, kategorie['jedzenie'].id)['rok_temu'] is None


def test_rok_temu_pokazany_przy_dluzszej_historii(app, test_user_token, konto, kategorie):
    for i in range(15):
        rok, mies = (2025, i + 1) if i < 12 else (2026, i - 11)
        kwota = "-900.00" if (rok, mies) == (2025, 12) else "-400.00"
        _tx(test_user_token, konto, kategorie['jedzenie'], kwota, date(rok, mies, 10))

    s = bps.zaproponuj_plan(test_user_token, 2026, 12, kategorie['jedzenie'].id)

    assert s['rok_temu'] == Decimal("900.00")


def test_sugestia_nie_widzi_cudzych_transakcji(app, test_user_token, other_user, kategorie):
    """Kategoria jest wlasna, ale historia obcego uzytkownika nie moze do niej wplywac."""
    obce_konto = Account(name="Obce", bank_name="X", balance=Decimal("0.00"),
                         user_token=other_user.token)
    db.session.add(obce_konto)
    db.session.commit()
    for miesiac in (1, 2, 3, 4, 5):
        _tx(other_user.token, obce_konto, kategorie['jedzenie'], "-999.00", date(2026, miesiac, 10))

    s = bps.zaproponuj_plan(test_user_token, 2026, 6, kategorie['jedzenie'].id)

    assert s['kwota'] is None


# --- lista budzetu: sklejenie calosci ---

def test_lista_budzetu_zestawia_plan_wykonanie_i_rezerwacje(app, test_user_token, konto, kategorie):
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("1500.00"))
    _tx(test_user_token, konto, kategorie['jedzenie'], "-600.00", date(2026, 5, 4))

    pozycja = next(p for p in bps.lista_budzetu(test_user_token, 2026, 5)['pozycje']
                   if p['category_id'] == kategorie['jedzenie'].id)

    assert pozycja['plan'] == Decimal("1500.00")
    assert pozycja['wykonane'] == Decimal("600.00")   # kwota dodatnia: "wydano tyle z planu"
    assert pozycja['zarezerwowane'] == Decimal("0.00")
    assert pozycja['category_type'] == 'expense'


# --- trasy HTTP ---

def test_get_budzetu_zwraca_plan_wykonanie_i_sugestie(logged_in_client, test_user_token,
                                                      konto, kategorie):
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("1500.00"))
    _tx(test_user_token, konto, kategorie['jedzenie'], "-600.00", date(2026, 5, 4))

    dane = logged_in_client.get('/api/budgets/2026/5').get_json()
    pozycja = next(p for p in dane['pozycje'] if p['category_id'] == kategorie['jedzenie'].id)

    assert pozycja['plan'] == 1500.0
    assert pozycja['wykonane'] == 600.0
    assert pozycja['sugestia']['kwota'] is None       # brak historii -> brak podpowiedzi
    assert dane['bilans_planu'] == -1500.0


def test_put_zapisuje_plan_i_get_go_widzi(logged_in_client, kategorie):
    resp = logged_in_client.put(f'/api/budgets/2026/5/{kategorie["jedzenie"].id}',
                                json={'amount': '1234.50'})
    assert resp.status_code == 200

    dane = logged_in_client.get('/api/budgets/2026/5').get_json()
    pozycja = next(p for p in dane['pozycje'] if p['category_id'] == kategorie['jedzenie'].id)
    assert pozycja['plan'] == 1234.5


def test_delete_kasuje_plan(logged_in_client, test_user_token, kategorie):
    bps.ustaw_plan(test_user_token, 2026, 5, kategorie['jedzenie'].id, Decimal("100.00"))

    resp = logged_in_client.delete(f'/api/budgets/2026/5/{kategorie["jedzenie"].id}')

    assert resp.status_code == 200
    pozycja = next(p for p in bps.lista_budzetu(test_user_token, 2026, 5)['pozycje']
                   if p['category_id'] == kategorie['jedzenie'].id)
    assert pozycja['plan'] is None


@pytest.mark.parametrize('kwota', ['-1', 'abc', '999999999999'])
def test_put_odrzuca_bledna_kwote(logged_in_client, kategorie, kwota):
    resp = logged_in_client.put(f'/api/budgets/2026/5/{kategorie["jedzenie"].id}',
                                json={'amount': kwota})
    assert resp.status_code == 400


def test_put_odrzuca_kategorie_transferowa(logged_in_client, kategorie):
    resp = logged_in_client.put(f'/api/budgets/2026/5/{kategorie["przelew"].id}',
                                json={'amount': '500.00'})
    assert resp.status_code == 400


@pytest.mark.parametrize('miesiac', [0, 13])
def test_bledny_miesiac_daje_400(logged_in_client, miesiac):
    assert logged_in_client.get(f'/api/budgets/2026/{miesiac}').status_code == 400
