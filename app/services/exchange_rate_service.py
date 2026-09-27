"""Kursy walut z NBP (tabela A, kursy średnie) — do wyceny sald kont walutowych.

Pobiera je wyłącznie `flask fetch-rates` z timera; żądania użytkowników czytają
kursy z bazy, więc awaria API NBP nie blokuje aplikacji.
"""
import json
import logging
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func

from app import db
from app.models import ExchangeRate

logger = logging.getLogger(__name__)

NBP_URL = 'https://api.nbp.pl/api/exchangerates/tables/a/{od}/{do}/?format=json'
# Pierwsza tabela A dostępna w API. Pełna historia to ~100 zapytań jednorazowo,
# a dzięki niej konto w dowolnej walucie od razu ma kursy dla całej swojej historii.
HISTORY_START = date(2002, 1, 2)
# NBP przyjmuje zakres najwyżej 93 dni.
_ZAKRES_DNI = 90


def _pobierz_tabele(od: date, do: date) -> list:
    """Tabele A z zakresu dat. Zakres bez dnia roboczego NBP zgłasza jako 404."""
    url = NBP_URL.format(od=od.isoformat(), do=do.isoformat())
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read(), parse_float=Decimal)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def fetch_rates(today: date | None = None) -> int:
    """Dopisuje kursy od dnia po ostatnim zapisanym do dziś. Zwraca liczbę nowych wierszy.

    Każda porcja jest zatwierdzana osobno: awaria w połowie historii zostawia to,
    co już przyszło, a kolejne uruchomienie zaczyna od miejsca przerwania.
    """
    today = today or date.today()
    ostatni = db.session.query(func.max(ExchangeRate.date)).scalar()
    od = ostatni + timedelta(days=1) if ostatni else HISTORY_START
    dodane = 0
    try:
        while od <= today:
            do = min(od + timedelta(days=_ZAKRES_DNI - 1), today)
            for tabela in _pobierz_tabele(od, do):
                dzien = date.fromisoformat(tabela['effectiveDate'])
                # Stare tabele (2002) mają 'country' zamiast 'currency' i potrafią
                # wymienić tę samą walutę dwa razy (EUR jako RFN i UGW).
                kursy = {r['code']: r for r in tabela['rates']}
                for kod, r in kursy.items():
                    db.session.add(ExchangeRate(currency=kod, currency_name=r.get('currency') or r.get('country', kod),
                                                date=dzien, rate=Decimal(str(r['mid']))))
                    dodane += 1
            db.session.commit()
            od = do + timedelta(days=1)
    except Exception:
        db.session.rollback()
        logger.exception("Pobieranie kursów NBP przerwane na zakresie od %s", od)
        raise
    logger.info("Pobrano %d kursów NBP (do %s)", dodane, today)
    return dodane


def is_known_currency(code: str) -> bool:
    """Czy waluta jest w najnowszej tabeli — wycofane (np. ATS sprzed euro) nie mają
    dzisiejszego kursu, więc konto w nich nigdy nie dałoby się wycenić."""
    ostatni = db.session.query(func.max(ExchangeRate.date)).scalar_subquery()
    return db.session.query(ExchangeRate.id).filter(
        ExchangeRate.currency == code, ExchangeRate.date == ostatni).first() is not None


def latest_rates() -> dict:
    """Najnowsza tabela: {kod: {name, rate, date}} dla wszystkich walut tabeli A."""
    ostatni = db.session.query(func.max(ExchangeRate.date)).scalar()
    if not ostatni:
        return {}
    return {
        r.currency: {'name': r.currency_name, 'rate': float(r.rate), 'date': ostatni.isoformat()}
        for r in db.session.query(ExchangeRate).filter_by(date=ostatni)
    }


def monthly_rates(currencies: set[str], since: date) -> dict:
    """{kod: {'RRRR-MM': kurs}} — kurs na koniec miesiąca, czyli ostatni opublikowany w nim.

    Miesiąc bez żadnej tabeli nie ma wpisu — w praktyce tylko przed początkiem
    historii, bo NBP publikuje tabelę w każdym dniu roboczym.

    ponytail: przebieg po wszystkich dziennych kursach od `since` (~250/rok na walutę);
    przy wolnym /api/init zastąpić agregacją w SQL albo tabelą kursów miesięcznych.
    """
    wynik: dict = {}
    if not currencies:
        return wynik
    wiersze = (
        db.session.query(ExchangeRate.currency, ExchangeRate.date, ExchangeRate.rate)
        .filter(ExchangeRate.currency.in_(currencies), ExchangeRate.date >= since.replace(day=1))
        .order_by(ExchangeRate.date)
    )
    for kod, dzien, kurs in wiersze:
        wynik.setdefault(kod, {})[dzien.strftime('%Y-%m')] = float(kurs)
    return wynik
