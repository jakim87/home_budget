from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from app import db
from app.models import User
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
        data = AccountSchema().load(request.get_json() or {})
        acc = create_account(user_id, data)
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': 0.0}), 201
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
        data = AccountSchema(partial=True).load(request.get_json() or {})
        acc = update_account(user_id, a_id, data)
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': float(acc.balance)}), 200
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

    soft_delete_account(user_id, a_id)
    return jsonify({'message': 'Konto usunięte ze słownika.'}), 200