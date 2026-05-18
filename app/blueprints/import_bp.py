from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app import db
from app.models import TransactionStaging, Category, Contractor, User
from app.schemas import StagingApproveSchema
from app.services.budget_service import parse_ing_csv, save_transactions_to_staging, approve_staging_record

import_bp = Blueprint('import', __name__)

@import_bp.route('/api/import/ing', methods=['POST'])
@login_required
def import_ing_csv():
    user_id = current_user.id

    if 'file' not in request.files:
        return jsonify({'error': 'Brak pliku w żądaniu.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku.'}), 400

    try:
        file_content = file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        file.seek(0)
        file_content = file.read().decode('windows-1250')

    account_id = request.form.get('account_id')
    if not account_id:
        return jsonify({'error': 'Nie wybrano konta, którego dotyczy wyciąg.'}), 400

    parsed_data = parse_ing_csv(file_content, user_id=user_id, main_account_id=int(account_id))
    if not parsed_data:
        return jsonify({'error': 'Plik nie zawiera poprawnych transakcji lub jest uszkodzony.'}), 400
        
    try:
        saved_records = save_transactions_to_staging(parsed_data, user_id=user_id)
        return jsonify({'message': f'Udało się zaimportować {len(saved_records)} transakcji do weryfikacji.', 'count': len(saved_records)}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@import_bp.route('/api/staging/pending', methods=['GET'])
@login_required
def get_pending_staging_transactions():
    user_id = current_user.id

    pending_txs = db.session.query(TransactionStaging, Category, Contractor).outerjoin(Category, TransactionStaging.proposed_category_id == Category.id).outerjoin(Contractor, TransactionStaging.proposed_contractor_id == Contractor.id).filter(TransactionStaging.user_id == user_id, TransactionStaging.status == 'pending').order_by(TransactionStaging.date.desc()).all()
    data = [{'id': tx.id, 'date': tx.date.strftime('%Y-%m-%d'), 'amount': float(tx.amount), 'title': tx.title, 'contractor': tx.contractor or '', 'status': tx.status, 'proposed_category': cat.name if cat else '', 'proposed_contractor_id': tx.proposed_contractor_id, 'proposed_contractor_name': cont.name if cont else ''} for tx, cat, cont in pending_txs]
    return jsonify(data), 200

@import_bp.route('/api/staging/pending', methods=['DELETE'])
@login_required
def clear_pending_staging_transactions():
    user_id = current_user.id

    try:
        deleted_count = db.session.query(TransactionStaging).filter_by(user_id=user_id, status='pending').delete()
        db.session.commit()
        return jsonify({'message': f'Odrzucono {deleted_count} transakcji.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Wystąpił błąd podczas odrzucania transakcji.'}), 500

@import_bp.route('/api/staging/<int:stg_id>/approve', methods=['POST'])
@login_required
def approve_staging_transaction(stg_id):
    user_id = current_user.id

    try:
        data = StagingApproveSchema().load(request.get_json() or {})
        new_tx = approve_staging_record(user_id, stg_id, data)
        return jsonify({'message': 'Transakcja zatwierdzona.', 'transaction_id': new_tx.id}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400