from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app import db
from app.models import Category, Contractor, User
from datetime import datetime
from app.schemas import TransactionSchema
from app.services.transaction_service import archive_and_delete_transaction, update_transaction
from app.services.budget_service import create_transaction

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    user_id = current_user.id

    try:
        data = TransactionSchema().load(request.get_json() or {})
        account_id = data.get('account_id')
        if not account_id: raise ValueError("Brakuje przypisanego konta.")
        
        title = data.get('title') or data.get('desc', 'Bez tytułu')
        amount = data.get('amount', 0.0)
        date_str = data.get('date')
        tx_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.today().date()

        category_name = data.get('category')
        category = db.session.query(Category).filter_by(name=category_name).first()
        contractor_id = data.get('contractor_id')
        splits_data = data.get('splits', [])

        new_tx = create_transaction(
            user_id, account_id, amount, title, tx_date, 
            category.id if category else None, 
            contractor_id=contractor_id,
            splits_data=splits_data
        )
        
        return_splits = []
        for s in new_tx.splits:
            return_splits.append({
                'id': s.id,
                'amount': float(s.amount),
                'desc': s.desc,
                'category': s.category.name if s.category else 'Inne'
            })
        
        return jsonify({'id': new_tx.id, 'desc': new_tx.title, 'amount': float(new_tx.amount), 'date': new_tx.date.strftime('%Y-%m-%d'), 'category': category.name if category else 'Inne', 'contractor_id': new_tx.contractor_id, 'contractor_name': db.session.get(Contractor, new_tx.contractor_id).name if new_tx.contractor_id else None, 'splits': return_splits}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@transactions_bp.route('/api/transactions/<int:tx_id>', methods=['PUT'])
@login_required
def edit_transaction(tx_id):
    user_id = current_user.id

    try:
        update_transaction(user_id, tx_id, request.get_json() or {})
        return jsonify({'message': 'Transakcja zaktualizowana pomyślnie.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@transactions_bp.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
@login_required
def remove_transaction(tx_id):
    user_id = current_user.id

    try:
        archive_and_delete_transaction(user_id, tx_id)
        return jsonify({'message': 'Transakcja zarchiwizowana i usunięta.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400