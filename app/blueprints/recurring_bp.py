from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app import ma
from app.schemas import RecurringTransactionSchema
from app.services.recurring_service import (
    create_recurring_transaction,
    get_all_recurring_transactions,
    update_recurring_transaction,
    delete_recurring_transaction
)

recurring_bp = Blueprint('recurring', __name__, url_prefix='/api/recurring-transactions')

@recurring_bp.route('/', methods=['POST'])
@login_required
def add_recurring_transaction():
    try:
        data = RecurringTransactionSchema().load(request.get_json() or {})
        rec_tx = create_recurring_transaction(current_user.token, data)
        return jsonify({'message': 'Recurring transaction created', 'id': rec_tx.id}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@recurring_bp.route('/', methods=['GET'])
@login_required
def list_recurring_transactions():
    transactions = get_all_recurring_transactions(current_user.token)
    return RecurringTransactionSchema(many=True).dump(transactions), 200

@recurring_bp.route('/<int:rec_tx_id>', methods=['PUT'])
@login_required
def edit_recurring_transaction(rec_tx_id):
    try:
        data = RecurringTransactionSchema(partial=True).load(request.get_json() or {})
        updated_tx = update_recurring_transaction(current_user.token, rec_tx_id, data)
        return RecurringTransactionSchema().dump(updated_tx), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

@recurring_bp.route('/<int:rec_tx_id>', methods=['DELETE'])
@login_required
def remove_recurring_transaction(rec_tx_id):
    try:
        delete_recurring_transaction(current_user.token, rec_tx_id)
        return jsonify({'message': 'Recurring transaction deleted'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404
