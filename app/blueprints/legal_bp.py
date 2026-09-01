"""Strony informacyjne: regulamin, polityka prywatności (RODO), informacja o autorze.

Treść jest statyczna — nie ma tu logiki biznesowej ani dostępu do bazy, więc
blueprint celowo nie ma odpowiednika w warstwie serwisów.

Strony są PUBLICZNE (bez @login_required): linkujemy do nich z modalu logowania
i rejestracji, więc muszą dać się przeczytać zanim ktokolwiek założy konto.
"""
import logging
from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

legal_bp = Blueprint('legal', __name__)

# Data ostatniej zmiany TREŚCI dokumentów (nie data dzisiejsza) — aktualizuj
# razem z edycją szablonów regulamin.html / polityka_prywatnosci.html.
DOCS_LAST_UPDATED = '31 sierpnia 2026'


@legal_bp.route('/regulamin')
def regulamin():
    return render_template('regulamin.html', last_updated=DOCS_LAST_UPDATED)


@legal_bp.route('/polityka-prywatnosci')
def polityka_prywatnosci():
    return render_template('polityka_prywatnosci.html', last_updated=DOCS_LAST_UPDATED)


@legal_bp.route('/o-aplikacji')
def o_aplikacji():
    return render_template('o_aplikacji.html', last_updated=DOCS_LAST_UPDATED)
