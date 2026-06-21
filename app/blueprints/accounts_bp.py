from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from flask_login import login_required, current_user
from app.schemas import AccountSchema
from app.services.account_service import create_account, update_account, soft_delete_account
from app.services.budget_service import reconcile_account_balance
from decimal import Decimal, InvalidOperation

accounts_bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')

@accounts_bp.route('/', methods=['POST'])
@login_required
def add_account():
    try:
        req_data = request.get_json() or {}
        data = AccountSchema().load(req_data)
        acc = create_account(current_user.token, data)
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': 0.0, 'is_default': acc.is_default, 'owner': acc.owner, 'co_owner': acc.co_owner}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@accounts_bp.route('/<int:a_id>', methods=['PUT'])
@login_required
def edit_account(a_id):
    try:
        req_data = request.get_json() or {}
        data = AccountSchema(partial=True).load(req_data)
        acc = update_account(current_user.token, a_id, data)
        return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': float(acc.balance), 'is_default': acc.is_default, 'owner': acc.owner, 'co_owner': acc.co_owner}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

@accounts_bp.route('/<int:a_id>', methods=['DELETE'])
@login_required
def delete_account(a_id):
    try:
        soft_delete_account(current_user.token, a_id)
        return jsonify({'message': 'Konto usunięte ze słownika.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

@accounts_bp.route('/<int:account_id>/reconcile', methods=['POST'])
@login_required
def reconcile_account(account_id):
    """
    Endpoint do uzgadniania salda konta.
    Przyjmuje nowe saldo i tworzy transakcję korygującą.
    """
    data = request.get_json()
    if not data or 'new_balance' not in data:
        return jsonify({'error': 'Brak pola "new_balance" w żądaniu.'}), 400

    try:
        new_balance = Decimal(str(data['new_balance']))
    except InvalidOperation:
        return jsonify({'error': 'Nieprawidłowy format salda.'}), 400

    try:
        comment = data.get('comment') or None
        reconciliation_tx = reconcile_account_balance(current_user.token, account_id, new_balance, comment=comment)
        if reconciliation_tx:
            return jsonify({'message': 'Saldo uzgodnione pomyślnie.', 'transaction_id': reconciliation_tx.id}), 200
        return jsonify({'message': 'Saldo jest już zgodne, nie utworzono transakcji.'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
