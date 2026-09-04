"""Planowanie budżetu miesięcznego: plan per kategoria zestawiony z wykonaniem (#96).

Nazwa modułu celowo różni się od `budget_service` — tamten trzyma CRUD transakcji
i parsery wyciągów, mimo mylącej nazwy nie ma nic wspólnego z planowaniem.

Dwie rzeczy różnią ten moduł od Raportów i trzeba je czytać razem z `docs/`:

1. **Jest świadomy podziałów transakcji.** Raporty liczą po kategorii rodzica; tutaj
   dokładność per kategoria jest produktem, więc transakcja rozbita na kategorie
   liczy się do nich, a nie do rodzica.
2. **Rozdziela wykonane od zarezerwowanego.** Transakcje cykliczne i zaplanowane
   z datą w przyszłości zajmują budżet, zanim się wykonają — inaczej aplikacja
   ostrzegałaby o przekroczeniu dopiero po fakcie.
"""
import logging
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy.orm import selectinload

from app import db
from app.models import (Budget, PlannedTransaction, RecurringTransaction,
                        Transaction)
from app.services.category_service import find_owned, list_active
from app.services.recurring_service import get_recurring_preview

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')
GROSZ = Decimal('0.01')

# Przelew między własnymi kontami nie jest ani przychodem, ani wydatkiem, więc nie
# podlega planowaniu. Kategorie techniczne ("Uzgadnianie salda") też odpadają.
TYPY_PLANOWALNE = ('income', 'expense')

# Progi uczciwości sugestii. Poniżej MIN_MIESIECY aplikacja mówi wprost, że nie wie —
# mediana z dwóch obserwacji to nie wzorzec. Porównanie rok do roku wymaga pełnego
# roku danych, inaczej porównujemy z miesiącem, którego w historii nie ma.
MIN_MIESIECY_HISTORII = 3
PROG_ROK_TEMU = 12


# --- wykonanie ---

def _sumy_miesieczne(user_token: str, od: date | None, do: date | None) -> dict:
    """Kwoty per (rok, miesiąc, kategoria) — ZE ZNAKIEM, świadome podziałów.

    Reguła podziałów (R1 z planu): w bazie kwoty podziałów są dodatnie, a transakcja
    ma znak, więc podział dziedziczy znak rodzica. Reszta nieopisana podziałami
    (`abs(rodzic) − suma podziałów`) zostaje na kategorii rodzica — dzięki temu suma
    po wszystkich kategoriach zawsze równa się sumie transakcji i żadna złotówka nie
    znika po cichu.

    ponytail: liczone w Pythonie, nie w SQL — przy kilkudziesięciu tysiącach transakcji
    to nadal milisekundy, a wersja SQL-owa (UNION ALL + sign()) różni się między SQLite
    a PostgreSQL. Przepisać, gdy historia urośnie na tyle, że to zacznie być widoczne.
    """
    q = (db.session.query(Transaction)
         .options(selectinload(Transaction.splits))
         .filter(Transaction.user_token == user_token))
    if od is not None:
        q = q.filter(Transaction.date >= od)
    if do is not None:
        q = q.filter(Transaction.date <= do)

    sumy = defaultdict(lambda: ZERO)
    for t in q.all():
        znak = -1 if t.amount < 0 else 1
        opisane = ZERO
        for s in t.splits:
            if s.category_id is None:
                continue
            kwota = abs(s.amount)
            opisane += kwota
            sumy[(t.date.year, t.date.month, s.category_id)] += znak * kwota

        # Nadmiar podziałów ponad kwotę rodzica jest stanem, którego formularz nie
        # dopuszcza; gdyby powstał inną drogą, nie odejmujemy go od rodzica.
        reszta = abs(t.amount) - opisane
        if reszta > 0 and t.category_id is not None:
            sumy[(t.date.year, t.date.month, t.category_id)] += znak * reszta

    return dict(sumy)


def wykonanie_per_kategoria(user_token: str, year: int, month: int) -> dict:
    """Faktycznie zaksięgowane kwoty w miesiącu, per kategoria (ze znakiem)."""
    od, do = _granice_miesiaca(year, month)
    return {cat_id: kwota
            for (_, _, cat_id), kwota in _sumy_miesieczne(user_token, od, do).items()}


# --- rezerwacje ---

def rezerwacje_per_kategoria(user_token: str, year: int, month: int) -> dict:
    """Kwoty zajęte przez harmonogram, których jeszcze nie zaksięgowano (ze znakiem).

    Liczymy wyłącznie wystąpienia od dziś w przód. Wystąpienie z przeszłości albo już
    ma swoją transakcję (i policzyłoby się drugi raz), albo jest zaległością
    harmonogramu — a zaległość to problem `flask process-scheduled`, nie budżetu.
    """
    dzis = date.today()
    pierwszy, ostatni = _granice_miesiaca(year, month)
    rez = defaultdict(lambda: ZERO)

    harmonogramy = {rt.id: rt for rt in db.session.query(RecurringTransaction)
                    .filter_by(user_token=user_token).all()}
    for proj in get_recurring_preview(user_token, year, month):
        if date.fromisoformat(proj['date']) < dzis:
            continue
        rt = harmonogramy.get(proj['recurring_id'])
        if rt is not None and rt.category_id is not None:
            rez[rt.category_id] += rt.amount

    planowane = (db.session.query(PlannedTransaction)
                 .filter(PlannedTransaction.user_token == user_token,
                         PlannedTransaction.status == 'pending',
                         PlannedTransaction.execution_date >= max(dzis, pierwszy),
                         PlannedTransaction.execution_date <= ostatni)
                 .all())
    for p in planowane:
        if p.category_id is not None:
            rez[p.category_id] += p.amount

    return dict(rez)


# --- plan (CRUD) ---

def ustaw_plan(user_token: str, year: int, month: int, category_id: int, amount) -> Budget:
    """Zapisuje albo nadpisuje plan dla kategorii w miesiącu."""
    _sprawdz_okres(year, month)
    kategoria = _kategoria_planowalna(user_token, category_id)
    kwota = Decimal(str(amount)).quantize(GROSZ)
    if kwota < 0:
        raise ValueError("Kwota planu nie może być ujemna.")

    try:
        plan = db.session.query(Budget).filter_by(
            user_token=user_token, year=year, month=month, category_id=category_id
        ).first()
        if plan is None:
            plan = Budget(user_token=user_token, year=year, month=month,
                          category_id=category_id, amount=kwota)
            db.session.add(plan)
        else:
            plan.amount = kwota
        db.session.commit()
        logger.info("Plan budżetu %s-%02d dla kategorii %s = %s",
                    year, month, kategoria.name, kwota)
        return plan
    except Exception:
        db.session.rollback()
        logger.exception("Nie udało się zapisać planu budżetu")
        raise


def usun_plan(user_token: str, year: int, month: int, category_id: int) -> None:
    """Kasuje plan. Brak planu nie jest błędem — efekt końcowy jest ten sam."""
    _sprawdz_okres(year, month)
    try:
        plan = db.session.query(Budget).filter_by(
            user_token=user_token, year=year, month=month, category_id=category_id
        ).first()
        if plan is not None:
            db.session.delete(plan)
            db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Nie udało się usunąć planu budżetu")
        raise


def lista_budzetu(user_token: str, year: int, month: int) -> dict:
    """Komplet danych zakładki Budżet: wiersze per kategoria + agregat planu."""
    _sprawdz_okres(year, month)
    kategorie = [c for c in list_active(user_token) if c.type in TYPY_PLANOWALNE]
    plany = {b.category_id: b.amount for b in db.session.query(Budget).filter_by(
        user_token=user_token, year=year, month=month).all()}
    wykonane = wykonanie_per_kategoria(user_token, year, month)
    zarezerwowane = rezerwacje_per_kategoria(user_token, year, month)
    sugestie = _sugestie(user_token, year, month, [c.id for c in kategorie])

    pozycje = [{
        'category_id': c.id,
        'category_name': c.name,
        'category_type': c.type,
        'plan': plany.get(c.id),
        # Kwoty prezentowane dodatnio: dla wydatku "wydano tyle z planu", dla
        # przychodu "wpłynęło tyle z planu". Kierunek niesie category_type.
        'wykonane': abs(wykonane.get(c.id, ZERO)),
        'zarezerwowane': abs(zarezerwowane.get(c.id, ZERO)),
        'sugestia': sugestie.get(c.id),
    } for c in kategorie]

    przychody = sum((p['plan'] for p in pozycje
                     if p['category_type'] == 'income' and p['plan'] is not None), ZERO)
    wydatki = sum((p['plan'] for p in pozycje
                   if p['category_type'] == 'expense' and p['plan'] is not None), ZERO)

    return {
        'year': year,
        'month': month,
        'pozycje': pozycje,
        'planowane_przychody': przychody,
        'planowane_wydatki': wydatki,
        # Ujemny bilans jest dozwolony (D2) — aplikacja informuje, nie blokuje.
        'bilans_planu': przychody - wydatki,
    }


# --- sugestie ---

def zaproponuj_plan(user_token: str, year: int, month: int, category_id: int) -> dict:
    """Podpowiedź kwoty dla jednej kategorii, oparta o jej własną historię."""
    _sprawdz_okres(year, month)
    _kategoria_planowalna(user_token, category_id)
    return _sugestie(user_token, year, month, [category_id])[category_id]


def _sugestie(user_token: str, year: int, month: int, category_ids: list) -> dict:
    """Podpowiedzi dla wielu kategorii z jednego przebiegu po historii.

    Podstawą jest MEDIANA, nie średnia: wydatki domowe są skośne i jedna naprawa auta
    zawyża średnią do kwoty, której nikt nie ustawi jako limitu. Zakres min–max jedzie
    obok, żeby nie ukryć faktu, że taki miesiąc się zdarza.

    Historię stanowią miesiące, w których kategoria FAKTYCZNIE wystąpiła — miesiące
    bez ani jednej transakcji nie są zerami do uśrednienia, tylko brakiem danych.
    """
    poprzedni_dzien = date(year, month, 1) - timedelta(days=1)
    per_kategoria = defaultdict(dict)
    for (y, m, cat_id), kwota in _sumy_miesieczne(user_token, None, poprzedni_dzien).items():
        if kwota != 0:
            per_kategoria[cat_id][(y, m)] = abs(kwota)

    wynik = {}
    for cat_id in category_ids:
        miesiace = per_kategoria.get(cat_id, {})
        n = len(miesiace)
        if n < MIN_MIESIECY_HISTORII:
            wynik[cat_id] = {
                'kwota': None,
                'podstawa': f"Za mało danych ({n} mies. historii) — ustaw ręcznie",
                'zakres_min': None, 'zakres_max': None,
                'liczba_miesiecy': n, 'rok_temu': None,
            }
            continue

        wartosci = sorted(miesiace.values())
        wynik[cat_id] = {
            'kwota': median(wartosci).quantize(GROSZ),
            # Sformułowane jako fakt o przeszłości, nie porada (D11) — aplikacja nie
            # zastępuje doradcy finansowego i nie udaje, że wie, ile POWINNO się wydać.
            'podstawa': f"Mediana z {n} mies. historii",
            'zakres_min': wartosci[0],
            'zakres_max': wartosci[-1],
            'liczba_miesiecy': n,
            'rok_temu': miesiace.get((year - 1, month)) if n >= PROG_ROK_TEMU else None,
        }
    return wynik


# --- pomocnicze ---

def _granice_miesiaca(year: int, month: int) -> tuple:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _sprawdz_okres(year: int, month: int) -> None:
    if not 1 <= month <= 12:
        raise ValueError("Miesiąc musi być z zakresu 1-12.")
    if not 1900 <= year <= 2999:
        raise ValueError("Rok poza dopuszczalnym zakresem.")


def _kategoria_planowalna(user_token: str, category_id: int):
    """Kategoria widoczna dla użytkownika i nadająca się do planowania.

    `find_owned` jest jedyną barierą przed podpięciem cudzej prywatnej kategorii —
    blueprint jej nie doda.
    """
    kategoria = find_owned(user_token, category_id)
    if kategoria is None:
        raise ValueError("Kategoria nie istnieje, jest nieaktywna lub brak uprawnień.")
    if kategoria.type not in TYPY_PLANOWALNE:
        raise ValueError("Planować można wyłącznie kategorie przychodów i wydatków.")
    return kategoria
