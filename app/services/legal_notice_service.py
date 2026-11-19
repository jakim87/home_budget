"""Komunikat o zmianie dokumentów prawnych (regulamin, polityka prywatności).

Baner po zalogowaniu pokazuje się, gdy data ostatniej zmiany dokumentów jest
nowsza niż ta, którą użytkownik potwierdził. To jedyne miejsce z tą datą —
strony `/regulamin` i `/polityka-prywatnosci` formatują ją z tej samej stałej.
"""
import logging
from datetime import date

from flask import current_app

from app import db
from app.models import User

logger = logging.getLogger(__name__)

# Data ostatniej zmiany TREŚCI dokumentów (nie data dzisiejsza) — podbijaj razem
# z edycją szablonów regulamin.html / polityka_prywatnosci.html. Podbicie
# pokazuje baner wszystkim użytkownikom, którzy potwierdzili wcześniejszą datę.
DOCS_LAST_UPDATED_DATE = date(2026, 11, 19)

_MIESIACE = ('stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca',
             'sierpnia', 'września', 'października', 'listopada', 'grudnia')


def format_pl(d: date) -> str:
    return f"{d.day} {_MIESIACE[d.month - 1]} {d.year}"


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
    return {'show': pokaz, 'updated': format_pl(DOCS_LAST_UPDATED_DATE)}


def acknowledge(user_token: str) -> None:
    """Zapisuje, że użytkownik zapoznał się z aktualną wersją dokumentów."""
    user = _get_user(user_token)
    if _is_demo(user):
        raise PermissionError("Konto demo nie zapisuje potwierdzeń.")
    try:
        user.legal_docs_ack = DOCS_LAST_UPDATED_DATE
        db.session.commit()
        logger.info("Potwierdzono dokumenty prawne (token=%s)", user_token)
    except Exception:
        db.session.rollback()
        raise
