"""Uwagi użytkowników o działaniu aplikacji.

Zgłoszenia zostają na tym serwerze — nie ma wysyłki mailem ani do zewnętrznych
usług. Powód nie jest wygodowy: zrzut ekranu i opis z aplikacji budżetowej
zawierają nazwy kont, salda i kontrahentów, czyli dane finansowe osoby trzeciej.
Wyprowadzenie ich poza serwer wymagałoby zgody i wpisu w polityce prywatności.
"""
import logging

from app import db
from app.models import Feedback

logger = logging.getLogger(__name__)

# Górna granica treści. Marshmallow pilnuje tego samego przy wejściu — tutaj
# przycinamy jako ostatnia linia obrony, żeby żaden inny wołający nie wsadził
# do bazy megabajta tekstu.
MAX_CONTENT = 5000
MAX_CONTEXT = 120
MAX_USER_AGENT = 255


def create_feedback(user_token: str, content: str, context: str | None = None,
                    user_agent: str | None = None) -> Feedback:
    """Zapisuje uwagę użytkownika. Podnosi ValueError przy pustej treści."""
    tresc = (content or '').strip()
    if not tresc:
        raise ValueError('Treść zgłoszenia nie może być pusta.')

    try:
        zgloszenie = Feedback(
            user_token=user_token,
            content=tresc[:MAX_CONTENT],
            context=(context or None) and context[:MAX_CONTEXT],
            user_agent=(user_agent or None) and user_agent[:MAX_USER_AGENT],
        )
        db.session.add(zgloszenie)
        db.session.commit()
        logger.info("Nowe zgłoszenie #%s od %s", zgloszenie.id, user_token[:8])
        return zgloszenie
    except Exception:
        db.session.rollback()
        logger.exception("Nie udało się zapisać zgłoszenia (user_token=%s)", user_token[:8])
        raise


def list_feedback(limit: int = 200) -> list[Feedback]:
    """Wszystkie zgłoszenia, od najnowszego.

    Wołane wyłącznie z `flask feedback-list`, czyli spod konta z dostępem do
    serwera. Aplikacja webowa NIE ma trasy czytającej zgłoszenia — dlatego ta
    funkcja świadomie nie filtruje po użytkowniku i nie sprawdza uprawnień.
    """
    return (
        db.session.query(Feedback)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .limit(limit)
        .all()
    )
