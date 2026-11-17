from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app.schemas import PlannedTransactionSchema, PotwierdzenieSchema
from app.services.planned_transaction_service import (
    create_planned_transaction,
    get_all_planned_transactions,
    delete_planned_transaction,
    pomin_zaplanowana,
    potwierdz_zaplanowana,
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


# Ten sam schemat co przy cyklicznych, bez wymaganego occurrence_date —
# zaplanowana ma jedno wystąpienie, więc nie ma czego wskazywać.
def _wczytaj_potwierdzenie():
    return PotwierdzenieSchema(partial=('occurrence_date',)).load(request.get_json() or {})


@planned_bp.route('/<int:pt_id>/potwierdz', methods=['POST'])
@login_required
def confirm_planned(pt_id):
    try:
        data = _wczytaj_potwierdzenie()
        tx = potwierdz_zaplanowana(current_user.token, pt_id,
                                   amount=data.get('amount'), transaction_date=data.get('date'))
        return jsonify({'message': 'Potwierdzono', 'transaction_id': tx.id}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400


@planned_bp.route('/<int:pt_id>/pomin', methods=['POST'])
@login_required
def skip_planned(pt_id):
    try:
        pomin_zaplanowana(current_user.token, pt_id)
        return jsonify({'message': 'Pominięto'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
