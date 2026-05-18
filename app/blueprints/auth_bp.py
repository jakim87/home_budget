from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user
from marshmallow import ValidationError
from app.schemas import RegisterSchema, LoginSchema
from app.services.auth_service import register_user, authenticate_user
from app import db
from app.models import User

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
            return jsonify({'message': 'Zalogowano pomyślnie'}), 200
        return jsonify({'error': 'Nieprawidłowe dane logowania'}), 401
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'message': 'Wylogowano pomyślnie'}), 200

@auth_bp.route('/api/me', methods=['GET'])
def me():
    # Zgodnie z nowym podejściem, zawsze zwracamy dane "default_user"
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        # Chociaż `before_request` powinien go stworzyć, to jest to zabezpieczenie
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
        
    return jsonify({'id': default_user.id, 'username': default_user.username, 'email': default_user.email})