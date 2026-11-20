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


@legal_bp.context_processor
def _data_wejscia_w_zycie():
    # legal_base.html dopisuje ją pod datą aktualizacji, dopóki zmiany jeszcze nie obowiązują.
    return {'obowiazuje_od': legal_notice_service.obowiazuje_od()}


@legal_bp.route('/regulamin')
def regulamin():
    return render_template('regulamin.html', last_updated=DOCS_LAST_UPDATED, seo={
        'path': '/regulamin',
        'title': 'Regulamin aplikacji Ile mam kasy',
        'description': 'Zasady korzystania z aplikacji Ile mam kasy: konto, import wyciągów, '
                       'dane użytkownika, odpowiedzialność i zasady usuwania danych.',
    })


@legal_bp.route('/polityka-prywatnosci')
def polityka_prywatnosci():
    return render_template('polityka_prywatnosci.html', last_updated=DOCS_LAST_UPDATED, seo={
        'path': '/polityka-prywatnosci',
        'title': 'Polityka prywatności (RODO) - Ile mam kasy',
        'description': 'Jakie dane przetwarza aplikacja Ile mam kasy, na jakiej podstawie, '
                       'jak długo i jakie prawa przysługują użytkownikowi.',
    })


@legal_bp.route('/o-aplikacji')
def o_aplikacji():
    return render_template('o_aplikacji.html', last_updated=DOCS_LAST_UPDATED, seo={
        'path': '/o-aplikacji',
        'title': 'O aplikacji Ile mam kasy',
        'description': 'Czym jest Ile mam kasy, kto ją tworzy i na jakiej licencji jest '
                       'udostępniony kod źródłowy.',
    })


@legal_bp.route('/kalkulator-kredytu')
def kalkulator_kredytu():
    return render_template('kalkulator_kredytu.html', seo={
        'path': '/kalkulator-kredytu',
        'title': 'Kalkulator kredytu - Ile mam kasy',
        'description': 'Rata, pełny koszt, RRSO i plan spłaty rata po racie - z prowizją, '
                       'opłatami i nadpłatami. Liczy się w przeglądarce.',
    })


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
