from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app.schemas import AccountSchema
from app.services.account_service import create_account, update_account, soft_delete_account

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/api/accounts', methods=['POST'])
@login_required
def add_account():
    try:
        data = AccountSchema().load(request.get_json() or {})
        acc = create_account(current_user.id, data)
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': 0.0}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@accounts_bp.route('/api/accounts/<int:a_id>', methods=['PUT'])
@login_required
def edit_account(a_id):
    try:
        data = AccountSchema(partial=True).load(request.get_json() or {})
        acc = update_account(current_user.id, a_id, data)
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': float(acc.balance)}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

@accounts_bp.route('/api/accounts/<int:a_id>', methods=['DELETE'])
@login_required
def delete_account(a_id):
    soft_delete_account(current_user.id, a_id)
    return jsonify({'message': 'Konto usunięte ze słownika.'}), 200