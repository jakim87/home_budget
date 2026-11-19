"""Strony publiczne: regulamin, polityka prywatności (RODO), informacja o autorze
oraz kalkulator kredytu (liczy w przeglądarce, nic nie wysyła na serwer).

Treść jest statyczna — nie ma tu logiki biznesowej ani dostępu do bazy, więc
blueprint celowo nie ma odpowiednika w warstwie serwisów.

Strony są PUBLICZNE (bez @login_required): linkujemy do nich z modalu logowania
i rejestracji, więc muszą dać się przeczytać zanim ktokolwiek założy konto.
"""
import logging
from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required

from app.services import legal_notice_service

logger = logging.getLogger(__name__)

legal_bp = Blueprint('legal', __name__)

# Data ostatniej zmiany TREŚCI dokumentów żyje w legal_notice_service (od niej zależy
# baner po zalogowaniu) — podbijaj ją razem z edycją szablonów regulamin.html /
# polityka_prywatnosci.html.
DOCS_LAST_UPDATED = legal_notice_service.format_pl(legal_notice_service.DOCS_LAST_UPDATED_DATE)


@legal_bp.route('/regulamin')
def regulamin():
    return render_template('regulamin.html', last_updated=DOCS_LAST_UPDATED)


@legal_bp.route('/polityka-prywatnosci')
def polityka_prywatnosci():
    return render_template('polityka_prywatnosci.html', last_updated=DOCS_LAST_UPDATED)


@legal_bp.route('/o-aplikacji')
def o_aplikacji():
    return render_template('o_aplikacji.html', last_updated=DOCS_LAST_UPDATED)


@legal_bp.route('/kalkulator-kredytu')
def kalkulator_kredytu():
    return render_template('kalkulator_kredytu.html')


@legal_bp.route('/api/legal-ack', methods=['POST'])
@login_required
def potwierdz_dokumenty():
    # Jedyna trasa tego blueprintu wymagająca logowania: zapisuje potwierdzenie
    # banera o zmianie dokumentów dla bieżącego użytkownika.
    try:
        legal_notice_service.acknowledge(current_user.token)
    except PermissionError as err:
        return jsonify({'error': str(err)}), 403
    return jsonify({'message': 'Zapisano'}), 200
