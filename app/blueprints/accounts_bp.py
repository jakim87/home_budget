from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from app import db
from app.models import User, Account
from app.schemas import AccountSchema
from app.services.account_service import create_account, update_account, soft_delete_account

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/api/accounts', methods=['POST'])
def add_account():
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    try:
        req_data = request.get_json() or {}
        data = AccountSchema().load(req_data)
        acc = create_account(user_id, data)
        
        # Odczyt ze zwalidowanych danych (Marshmallow)
        if data.get('is_default'):
            db.session.query(Account).filter(Account.user_id == user_id, Account.id != acc.id).update({'is_default': False})
            acc.is_default = True
            db.session.commit()
            
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': 0.0, 'is_default': getattr(acc, 'is_default', False)}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@accounts_bp.route('/api/accounts/<int:a_id>', methods=['PUT'])
def edit_account(a_id):
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    try:
        req_data = request.get_json() or {}
        data = AccountSchema(partial=True).load(req_data)
        acc = update_account(user_id, a_id, data)
        
        if data.get('is_default'):
            db.session.query(Account).filter(Account.user_id == user_id, Account.id != acc.id).update({'is_default': False})
            acc.is_default = True
            db.session.commit()
            
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': float(acc.balance), 'is_default': getattr(acc, 'is_default', False)}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

@accounts_bp.route('/api/accounts/<int:a_id>', methods=['DELETE'])
def delete_account(a_id):
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    try:
        soft_delete_account(user_id, a_id)
        return jsonify({'message': 'Konto usunięte ze słownika.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404