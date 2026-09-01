"""Przyjmowanie uwag użytkowników o działaniu aplikacji.

Blueprint robi WYŁĄCZNIE zapis — nie ma trasy do czytania zgłoszeń. Odczyt idzie
przez `flask feedback-list` na serwerze, więc aplikacja w ogóle nie potrzebuje
pojęcia „administrator" ani ról: nie ma czego chronić poza tym jednym POST-em.

Konto demo nie może wysyłać. Demo jest publiczne, więc formularz dostępny z niego
byłby anonimowym endpointem zapisu dla całego internetu.
"""
import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from marshmallow import ValidationError

from app import limiter
from app.schemas import FeedbackSchema
from app.services.feedback_service import create_feedback

logger = logging.getLogger(__name__)

feedback_bp = Blueprint('feedback', __name__)


@feedback_bp.route('/api/feedback', methods=['POST'])
@login_required
# Limit per IP: zgłoszenie pisze się minutami, nie sekundami. Zapora przed botem,
# nie przed człowiekiem, który ma dużo do powiedzenia.
@limiter.limit("10 per hour")
def send_feedback():
    if current_user.username == current_app.config.get('DEMO_USERNAME'):
        return jsonify({'error': 'Konto demo nie może wysyłać zgłoszeń.'}), 403

    try:
        dane = FeedbackSchema().load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    try:
        create_feedback(
            user_token=current_user.token,
            content=dane['content'],
            context=dane.get('context'),
            user_agent=request.headers.get('User-Agent'),
        )
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    return jsonify({'message': 'Dziękujemy! Zgłoszenie zostało zapisane.'}), 201
