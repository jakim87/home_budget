import logging
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from marshmallow import ValidationError
from app.schemas import RegisterSchema, LoginSchema
from app.services.auth_service import register_user, authenticate_user
from app import db
from app.models import User

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/register', methods=['POST'])
def register():
    try:
        data = RegisterSchema().load(request.get_json() or {})
        user = register_user(data)
        return jsonify({'message': 'Rejestracja pomyślna', 'user_id': user.id}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@auth_bp.route('/api/login', methods=['POST'])
def login():
    try:
        data = LoginSchema().load(request.get_json() or {})
        identifier = data.get('username') or data.get('email')
        user = authenticate_user(identifier, data['password'])
        if user:
            login_user(user)
            logger.info("Zalogowano: %s (IP=%s)", user.username, request.remote_addr)
            return jsonify({'message': 'Zalogowano pomyślnie'}), 200
        logger.warning("Nieudana próba logowania: '%s' (IP=%s)", identifier, request.remote_addr)
        return jsonify({'error': 'Nieprawidłowe dane logowania'}), 401
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    logger.info("Wylogowano: %s", current_user.username if current_user.is_authenticated else '-')
    logout_user()
    return jsonify({'message': 'Wylogowano pomyślnie'}), 200

@auth_bp.route('/api/me', methods=['GET'])
@login_required
def me():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Użytkownik niezalogowany'}), 401
    return jsonify({'id': current_user.id, 'username': current_user.username, 'email': current_user.email})