from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app.schemas import PlannedTransactionSchema
from app.services.planned_transaction_service import (
    create_planned_transaction,
    get_all_planned_transactions,
    delete_planned_transaction
)

planned_bp = Blueprint('planned', __name__, url_prefix='/api/planned-transactions')

@planned_bp.route('/', methods=['POST'])
@login_required
def add_planned_transaction():
    try:
        data = PlannedTransactionSchema().load(request.get_json() or {})
        planned_tx = create_planned_transaction(current_user.token, data)
        return jsonify(PlannedTransactionSchema().dump(planned_tx)), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@planned_bp.route('/', methods=['GET'])
@login_required
def list_planned_transactions():
    transactions = get_all_planned_transactions(current_user.token)
    return PlannedTransactionSchema(many=True).dump(transactions), 200

@planned_bp.route('/<int:pt_id>', methods=['DELETE'])
@login_required
def remove_planned_transaction(pt_id):
    try:
        delete_planned_transaction(current_user.token, pt_id)
        return jsonify({'message': 'Zaplanowana transakcja usunięta'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 404
