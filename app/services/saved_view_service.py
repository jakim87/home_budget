"""Zapisane widoki zakładki Wnioski (decyzja 12 planu „Poprawka wizualna”, sekcja 4).

Widok to nazwa i konfiguracja filtrów. Konfigurację liczy i rysuje przeglądarka —
serwer tylko ją przechowuje, po walidacji schematem `WidokConfigSchema` (blueprint).
Trzy widoki wbudowane żyją w kodzie frontu (`23_wnioski.js`); ich nazwy są tu
zarezerwowane, bo dwa chipy o tej samej nazwie nie dałyby się odróżnić.
"""
import json
import logging

from app import db
from app.models import SavedView

logger = logging.getLogger(__name__)

# Razem z trzema wbudowanymi to 10 chipów — tyle mieści jeden rząd nad filtrami.
MAKS_WLASNYCH = 7
NAZWY_WBUDOWANYCH = ('Miesiąc w liczbach', 'Przychody i wydatki w czasie', 'Saldo na koniec miesiąca')


class BrakWidoku(ValueError):
    """Widoku nie ma albo należy do kogoś innego — blueprint odpowiada 404."""


def view_dict(w: SavedView) -> dict:
    return {'id': w.id, 'name': w.name, 'config': json.loads(w.config)}


def list_views(user_token: str) -> list[SavedView]:
    return (
        db.session.query(SavedView)
        .filter_by(user_token=user_token)
        .order_by(SavedView.id)
        .all()
    )


def _sprawdz_nazwe(user_token: str, nazwa: str, pomin_id: int | None = None) -> str:
    nazwa = (nazwa or '').strip()
    if not nazwa:
        raise ValueError('Wpisz nazwę widoku.')
    zajete = {n.lower() for n in NAZWY_WBUDOWANYCH}
    zajete |= {w.name.lower() for w in list_views(user_token) if w.id != pomin_id}
    if nazwa.lower() in zajete:
        raise ValueError('Widok o tej nazwie już jest. Wybierz inną nazwę.')
    return nazwa


def _wlasny(user_token: str, view_id: int) -> SavedView:
    w = db.session.query(SavedView).filter_by(id=view_id, user_token=user_token).first()
    if not w:
        raise BrakWidoku('Nie znaleziono widoku.')
    return w


def create_view(user_token: str, name: str, config: dict) -> SavedView:
    """Zapisuje nowy widok. `config` musi być już przepuszczony przez schemat."""
    try:
        if db.session.query(SavedView).filter_by(user_token=user_token).count() >= MAKS_WLASNYCH:
            raise ValueError(f'Masz już {MAKS_WLASNYCH} własnych widoków. Usuń któryś, żeby zapisać nowy.')
        w = SavedView(user_token=user_token, name=_sprawdz_nazwe(user_token, name),
                      config=json.dumps(config, ensure_ascii=False))
        db.session.add(w)
        db.session.commit()
        logger.info("Zapisano widok #%s (user=%s)", w.id, user_token[:8])
        return w
    except Exception:
        db.session.rollback()
        raise


def update_view(user_token: str, view_id: int, name: str, config: dict) -> SavedView:
    try:
        w = _wlasny(user_token, view_id)
        w.name = _sprawdz_nazwe(user_token, name, pomin_id=w.id)
        w.config = json.dumps(config, ensure_ascii=False)
        db.session.commit()
        logger.info("Zmieniono widok #%s (user=%s)", w.id, user_token[:8])
        return w
    except Exception:
        db.session.rollback()
        raise


def delete_view(user_token: str, view_id: int) -> None:
    try:
        db.session.delete(_wlasny(user_token, view_id))
        db.session.commit()
        logger.info("Usunięto widok #%s (user=%s)", view_id, user_token[:8])
    except Exception:
        db.session.rollback()
        raise
