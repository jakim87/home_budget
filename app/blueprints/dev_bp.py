from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.services.demo_service import wipe_user_data

dev_bp = Blueprint('dev', __name__)


@dev_bp.route('/api/dev/reset', methods=['POST'])
@login_required
def reset_user_data():
    """Czyści dane WYŁĄCZNIE bieżącego użytkownika — tylko do testów.

    Uwaga: reset NIE usuwa kategorii — ani globalnych (te są współdzielone), ani
    własnych użytkownika. Słownik kategorii buduje się długo i nie jest "danymi
    testowymi"; zerujemy jedynie powiązania kategorii w usuwanych rekordach.
    """
    try:
        wipe_user_data(current_user.token)
        return jsonify({'message': 'Dane zostały wyczyszczone.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
