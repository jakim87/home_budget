"""Komunikat o zmianie dokumentów prawnych (regulamin, polityka prywatności).

Baner po zalogowaniu pokazuje się, gdy data ostatniej zmiany dokumentów jest
nowsza niż ta, którą użytkownik potwierdził. To jedyne miejsce z tą datą —
strony `/regulamin` i `/polityka-prywatnosci` formatują ją z tej samej stałej.
"""
import logging
from datetime import date, datetime, timezone

from flask import current_app

from app import db
from app.models import User

logger = logging.getLogger(__name__)

# Dziennik zmian dokumentów, od najnowszej. Przy każdej istotnej zmianie treści
# regulamin.html / polityka_prywatnosci.html dopisz NA GÓRZE wpis: `data` to dzień
# publikacji, `od` - dzień wejścia w życie (regulamin § 8: co najmniej 7 dni po
# publikacji; dla zmian, które tylko doprecyzowują opis, może być równy `data`),
# `punkty` - krótkie streszczenie po ludzku. Baner po zalogowaniu pokazuje
# użytkownikowi wpisy nowsze niż te, które potwierdził.
ZMIANY_DOKUMENTOW = (
    {'data': date(2026, 11, 20), 'od': date(2026, 11, 27), 'punkty': (
        'Regulamin: zmiany ogłaszamy z wyprzedzeniem co najmniej 7 dni, nie działają wstecz, '
        'a przed ich wejściem w życie możesz zrezygnować z korzystania z Aplikacji i usunąć konto',
        'Regulamin: zmienić go możemy tylko z podanych przyczyn (zmiana funkcji Aplikacji lub przepisów prawa)',
        'Aplikacja po zalogowaniu pokazuje streszczenie zmian dokumentów',
        'Polityka prywatności: zapisujemy datę i godzinę, kiedy potwierdzasz komunikat o zmianie dokumentów, '
        'żeby wykazać, że zmiana została Ci zakomunikowana',
    )},
    {'data': date(2026, 11, 19), 'od': date(2026, 11, 19), 'punkty': (
        'Polityka prywatności: dokładniej opisaliśmy logi serwera i kopie zapasowe',
        'Polityka prywatności: interfejs nie ładuje już zasobów z zewnętrznych sieci CDN, '
        'więc Twój adres IP nie trafia do ich operatorów',
        'Regulamin i polityka: uporządkowaliśmy opis licencji (BSL) i usunęliśmy wzmianki o niekomercyjności',
    )},
    {'data': date(2026, 10, 6), 'od': date(2026, 10, 6), 'punkty': (
        'Regulamin i polityka: usunięta transakcja znika od razu i na stałe, bez archiwum',
    )},
)

# Data publikacji ostatniej zmiany treści dokumentów - pochodzi z dziennika wyżej.
# Podbicie pokazuje baner wszystkim, którzy potwierdzili wcześniejszą datę.
DOCS_LAST_UPDATED_DATE = ZMIANY_DOKUMENTOW[0]['data']

_MIESIACE = ('stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca',
             'sierpnia', 'września', 'października', 'listopada', 'grudnia')


def format_pl(d: date) -> str:
    return f"{d.day} {_MIESIACE[d.month - 1]} {d.year}"


def obowiazuje_od(dzis: date | None = None) -> str | None:
    """Data wejścia w życie najnowszych zmian, dopóki jest w przyszłości (do strony dokumentów)."""
    od = ZMIANY_DOKUMENTOW[0]['od']
    return format_pl(od) if od > (dzis or date.today()) else None


def _zmiany_po(ack: date | None) -> list[dict]:
    return [
        {'date': format_pl(z['data']),
         'od': format_pl(z['od']) if z['od'] != z['data'] else None,
         'punkty': list(z['punkty'])}
        for z in ZMIANY_DOKUMENTOW if ack is None or z['data'] > ack
    ]


def _is_demo(user: User) -> bool:
    return user.username == current_app.config.get('DEMO_USERNAME')


def _get_user(user_token: str) -> User:
    user = db.session.query(User).filter_by(token=user_token).first()
    if user is None:
        raise ValueError("Nie znaleziono użytkownika.")
    return user


def notice_state(user_token: str) -> dict:
    """Stan banera dla /api/init. Konto demo nigdy go nie widzi (nie ma czego zapisać)."""
    user = _get_user(user_token)
    pokaz = (not _is_demo(user)
             and (user.legal_docs_ack is None or user.legal_docs_ack < DOCS_LAST_UPDATED_DATE))
    return {'show': pokaz, 'updated': format_pl(DOCS_LAST_UPDATED_DATE),
            'changes': _zmiany_po(user.legal_docs_ack) if pokaz else []}


def lista_potwierdzen(tylko_bez_potwierdzenia: bool = False) -> list[dict]:
    """Stan potwierdzenia aktualnej wersji dokumentów dla każdego zwykłego konta (do CLI).

    `stan`: 'potwierdzil' (kliknął „Rozumiem” na bieżącej wersji), 'rejestracja' (wersja
    przyjęta przy zakładaniu konta, bez kliknięcia), 'brak' (nie potwierdził bieżącej wersji).
    Konto demo jest pomijane - nie zapisuje potwierdzeń.
    """
    wynik = []
    for u in db.session.query(User).order_by(User.id).all():
        if _is_demo(u):
            continue
        if u.legal_docs_ack is None or u.legal_docs_ack < DOCS_LAST_UPDATED_DATE:
            stan = 'brak'
        else:
            stan = 'potwierdzil' if u.legal_docs_ack_at else 'rejestracja'
        if tylko_bez_potwierdzenia and stan != 'brak':
            continue
        wynik.append({'username': u.username, 'wersja': u.legal_docs_ack,
                      'potwierdzono': u.legal_docs_ack_at, 'stan': stan})
    return wynik


def acknowledge(user_token: str) -> None:
    """Zapisuje, że użytkownik zapoznał się z aktualną wersją dokumentów."""
    user = _get_user(user_token)
    if _is_demo(user):
        raise PermissionError("Konto demo nie zapisuje potwierdzeń.")
    try:
        user.legal_docs_ack = DOCS_LAST_UPDATED_DATE
        user.legal_docs_ack_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        logger.info("Potwierdzono dokumenty prawne (token=%s)", user_token)
    except Exception:
        db.session.rollback()
        raise
