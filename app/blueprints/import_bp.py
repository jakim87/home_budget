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
    user_token = current_user.token

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

    parsed_data = parse_ing_csv(file_content, user_token=user_token, main_account_id=int(account_id))
    if not parsed_data:
        return jsonify({'error': 'Plik nie zawiera poprawnych transakcji lub jest uszkodzony.'}), 400

    try:
        saved_records = save_transactions_to_staging(parsed_data, user_token=user_token)
        return jsonify({'message': f'Udało się zaimportować {len(saved_records)} transakcji do weryfikacji.', 'count': len(saved_records)}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@import_bp.route('/api/staging/pending', methods=['GET'])
@login_required
def get_pending_staging_transactions():
    user_token = current_user.token

    pending_txs = db.session.query(TransactionStaging, Category, Contractor).outerjoin(Category, TransactionStaging.proposed_category_id == Category.id).outerjoin(Contractor, TransactionStaging.proposed_contractor_id == Contractor.id).filter(TransactionStaging.user_token == user_token, TransactionStaging.status == 'pending').order_by(TransactionStaging.date.desc()).all()
    data = [{'id': tx.id, 'date': tx.date.strftime('%Y-%m-%d'), 'amount': float(tx.amount), 'title': tx.title, 'contractor': tx.contractor or '', 'status': tx.status, 'proposed_category': cat.name if cat else '', 'proposed_contractor_id': tx.proposed_contractor_id, 'proposed_contractor_name': cont.name if cont else '', 'suggested_contractor_name': tx.suggested_contractor_name or ''} for tx, cat, cont in pending_txs]
    return jsonify(data), 200

@import_bp.route('/api/staging/pending', methods=['DELETE'])
@login_required
def clear_pending_staging_transactions():
    user_token = current_user.token

    try:
        deleted_count = db.session.query(TransactionStaging).filter_by(user_token=user_token, status='pending').delete()
        db.session.commit()
        return jsonify({'message': f'Odrzucono {deleted_count} transakcji.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Wystąpił błąd podczas odrzucania transakcji.'}), 500

@import_bp.route('/api/staging/<int:stg_id>/accept-contractor', methods=['POST'])
@login_required
def accept_suggested_contractor(stg_id):
    user_token = current_user.token
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Nazwa kontrahenta nie może być pusta.'}), 400

    try:
        stg_tx = db.session.query(TransactionStaging).filter_by(id=stg_id, user_token=user_token, status='pending').first()
        if not stg_tx:
            return jsonify({'error': 'Nie znaleziono transakcji.'}), 404

        existing = db.session.query(Contractor).filter_by(user_token=user_token, name=name, is_active=True).first()
        if existing:
            stg_tx.proposed_contractor_id = existing.id
            stg_tx.suggested_contractor_name = None
            db.session.commit()
            return jsonify({'contractor_id': existing.id, 'contractor_name': existing.name, 'mapping_rules': existing.mapping_rules or '', 'default_category_id': existing.default_category_id, 'default_category_name': ''}), 200

        mapping_rules = name.lower()
        new_cont = Contractor(name=name, mapping_rules=mapping_rules, user_token=user_token)
        db.session.add(new_cont)
        db.session.flush()

        stg_tx.proposed_contractor_id = new_cont.id
        stg_tx.suggested_contractor_name = None
        db.session.commit()

        return jsonify({'contractor_id': new_cont.id, 'contractor_name': new_cont.name, 'mapping_rules': new_cont.mapping_rules, 'default_category_id': None, 'default_category_name': ''}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@import_bp.route('/api/staging/<int:stg_id>/approve', methods=['POST'])
@login_required
def approve_staging_transaction(stg_id):
    user_token = current_user.token

    try:
        data = StagingApproveSchema().load(request.get_json() or {})
        new_tx = approve_staging_record(user_token, stg_id, data)
        return jsonify({'message': 'Transakcja zatwierdzona.', 'transaction_id': new_tx.id}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
