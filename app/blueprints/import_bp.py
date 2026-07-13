from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app import db
from app.models import TransactionStaging, Category, Contractor, Account
from typing import Optional
from app.schemas import StagingApproveSchema
from app.services.budget_service import parse_ing_csv, save_transactions_to_staging, approve_staging_record, reanalyze_all_staging, clear_pending_staging, accept_staging_contractor

import_bp = Blueprint('import', __name__)


def _abbrev_account(number: Optional[str]) -> str:
    """Zwraca skrócony numer konta: 2 pierwsze + '....' + 4 ostatnie cyfry."""
    if not number:
        return ''
    n = number.replace(' ', '').replace('-', '')
    return f"{n[:2]}....{n[-4:]}" if len(n) >= 6 else n

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
        try:
            file_content = file.read().decode('windows-1250')
        except UnicodeDecodeError:
            return jsonify({'error': 'Nieobsługiwane kodowanie pliku. Oczekiwano UTF-8 lub Windows-1250 (eksport z ING).'}), 400

    account_id = request.form.get('account_id')

    try:
        result = parse_ing_csv(
            file_content,
            user_token=user_token,
            main_account_id=int(account_id) if account_id else None
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    transactions = result['transactions']
    skipped_count = result['skipped_count']

    if not transactions:
        msg = 'Plik nie zawiera poprawnych transakcji lub jest uszkodzony.'
        if skipped_count:
            msg += f' Pominięto {skipped_count} transakcji z kont nieznanych aplikacji.'
        return jsonify({'error': msg}), 400

    try:
        saved_records = save_transactions_to_staging(transactions, user_token=user_token)
        resp: dict = {
            'message': f'Udało się zaimportować {len(saved_records)} transakcji do weryfikacji.',
            'count': len(saved_records),
        }
        if result['csv_accounts']:
            resp['csv_accounts'] = result['csv_accounts']
        if skipped_count:
            resp['skipped_count'] = skipped_count
        return jsonify(resp), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@import_bp.route('/api/staging/pending', methods=['GET'])
@login_required
def get_pending_staging_transactions():
    user_token = current_user.token

    pending_txs = (
        db.session.query(TransactionStaging, Category, Contractor)
        .outerjoin(Category, TransactionStaging.proposed_category_id == Category.id)
        .outerjoin(Contractor, TransactionStaging.proposed_contractor_id == Contractor.id)
        .filter(TransactionStaging.user_token == user_token, TransactionStaging.status == 'pending')
        .order_by(TransactionStaging.date.desc())
        .all()
    )

    user_accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
    accounts_by_id = {acc.id: acc for acc in user_accounts}
    accounts_by_name = {acc.name: acc for acc in user_accounts}

    data = []
    for tx, cat, cont in pending_txs:
        item = {
            'id': tx.id,
            'date': tx.date.strftime('%Y-%m-%d'),
            'amount': float(tx.amount),
            'title': tx.title,
            'contractor': tx.contractor or '',
            'status': tx.status,
            'proposed_category': cat.name if cat else '',
            'proposed_contractor_id': tx.proposed_contractor_id,
            'proposed_contractor_name': cont.name if cont else '',
            'suggested_contractor_name': tx.suggested_contractor_name or '',
        }

        if cat and cat.type == 'transfer' and cont and cont.name.startswith("Moje konto: "):
            src_acc = accounts_by_id.get(tx.account_id)
            dest_name = cont.name[len("Moje konto: "):]
            dest_acc = accounts_by_name.get(dest_name)
            item['transfer_from'] = {
                'name': src_acc.name if src_acc else '?',
                'abbrev': _abbrev_account(src_acc.account_number if src_acc else None),
            }
            item['transfer_to'] = {
                'name': dest_name,
                'abbrev': _abbrev_account(dest_acc.account_number if dest_acc else None),
            }

        data.append(item)

    return jsonify(data), 200

@import_bp.route('/api/staging/reanalyze', methods=['POST'])
@login_required
def reanalyze_staging():
    """Ponownie uruchamia autokategoryzację na wszystkich pending rekordach stagingu."""
    try:
        count = reanalyze_all_staging(current_user.token)
        return jsonify({'message': f'Przeanalizowano ponownie {count} rekordów.', 'count': count}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 500

@import_bp.route('/api/staging/pending', methods=['DELETE'])
@login_required
def clear_pending_staging_transactions():
    try:
        deleted_count = clear_pending_staging(current_user.token)
        return jsonify({'message': f'Odrzucono {deleted_count} transakcji.'}), 200
    except ValueError:
        return jsonify({'error': 'Wystąpił błąd podczas odrzucania transakcji.'}), 500

@import_bp.route('/api/staging/<int:stg_id>/accept-contractor', methods=['POST'])
@login_required
def accept_suggested_contractor(stg_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Nazwa kontrahenta nie może być pusta.'}), 400

    try:
        result = accept_staging_contractor(current_user.token, stg_id, name)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404 if 'Nie znaleziono' in str(e) else 500


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
