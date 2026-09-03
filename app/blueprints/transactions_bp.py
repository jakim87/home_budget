from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from datetime import date
from app.schemas import BulkTransactionSchema, TransactionSchema
from app.services.category_service import find_by_name as find_category_by_name
from app.services.transaction_service import (
    archive_and_delete_transaction,
    bulk_delete_transactions,
    bulk_update_category,
    update_transaction,
)
from app.services.budget_service import create_transaction

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    try:
        data = TransactionSchema().load(request.get_json() or {})
        account_id = data.get('account_id')
        if not account_id:
            raise ValueError("Brakuje przypisanego konta.")

        title = data.get('title') or data.get('desc', 'Bez tytułu')
        # Podana, ale nierozpoznana nazwa kategorii to błąd — bez tego transakcja
        # zapisywała się bez kategorii i mimo to zwracała 201 (ciche pominięcie).
        # Brak kategorii (None) jest dozwolony.
        category = find_category_by_name(current_user.token, data.get('category'))
        if data.get('category') and not category:
            raise ValueError(f"Kategoria '{data.get('category')}' nie istnieje lub jest nieaktywna.")

        new_tx = create_transaction(
            current_user.token, account_id, data.get('amount', 0),
            title, data.get('date') or date.today(),
            category.id if category else None,
            contractor_id=data.get('contractor_id'),
            splits_data=data.get('splits', []),
            comment=data.get('comment') or None
        )

        return_splits = [
            {
                'id': s.id,
                'amount': float(s.amount),
                'desc': s.desc,
                'category': s.category.name if s.category else 'Inne'
            }
            for s in new_tx.splits
        ]

        # Kontrahent jest już zweryfikowany co do właściciela w create_transaction,
        # więc bierzemy nazwę z relacji zamiast powtarzać zapytanie.
        return jsonify({'id': new_tx.id, 'desc': new_tx.title, 'amount': float(new_tx.amount), 'date': new_tx.date.strftime('%Y-%m-%d'), 'category': category.name if category else 'Inne', 'contractor_id': new_tx.contractor_id, 'contractor_name': new_tx.contractor_details.name if new_tx.contractor_details else None, 'splits': return_splits}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@transactions_bp.route('/api/transactions/<int:tx_id>', methods=['PUT'])
@login_required
def edit_transaction(tx_id):
    try:
        # Bez schematu błędna kwota kończyła się 500: decimal.InvalidOperation nie
        # dziedziczy po ValueError, więc `except` poniżej jej nie łapał.
        # partial=True — edycja jest częściowa: pola nieobecne w żądaniu muszą
        # zostać nietknięte (front wysyła albo pola inline, albo samą listę
        # podziałów). Patrz test_partial_update_does_not_wipe_unsent_fields.
        data = TransactionSchema(partial=True).load(request.get_json() or {})
        update_transaction(current_user.token, tx_id, data)
        return jsonify({'message': 'Transakcja zaktualizowana pomyślnie.'}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@transactions_bp.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
@login_required
def remove_transaction(tx_id):
    try:
        archive_and_delete_transaction(current_user.token, tx_id)
        return jsonify({'message': 'Transakcja zarchiwizowana i usunięta.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400


# --- Operacje zbiorcze ---
# Osobne ścieżki zamiast pętli po /api/transactions/<id> po stronie frontu:
# jedno żądanie to jedna transakcja bazodanowa, więc albo zmienia się cała
# zaznaczona paczka, albo nic. Pętla po froncie przy błędzie w połowie
# zostawiałaby dane w stanie, którego użytkownik nie potrafi odtworzyć.

@transactions_bp.route('/api/transactions/bulk/category', methods=['POST'])
@login_required
def bulk_category():
    try:
        data = BulkTransactionSchema().load(request.get_json() or {})
        if not data.get('category'):
            raise ValueError('Nie wskazano kategorii.')
        wynik = bulk_update_category(current_user.token, data['ids'], data['category'])
        return jsonify(wynik), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400


@transactions_bp.route('/api/transactions/bulk/delete', methods=['POST'])
@login_required
def bulk_delete():
    # POST, nie DELETE: lista identyfikatorów jedzie w ciele żądania, a ciało
    # przy DELETE bywa gubione po drodze (proxy, klienci HTTP).
    try:
        data = BulkTransactionSchema().load(request.get_json() or {})
        wynik = bulk_delete_transactions(current_user.token, data['ids'])
        return jsonify(wynik), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
