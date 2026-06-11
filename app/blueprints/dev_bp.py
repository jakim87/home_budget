from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Transaction, TransactionSplit, TransactionStaging,
                         TransactionArchive, RecurringTransaction, PlannedTransaction,
                         Category, Contractor, Budget, Account)

dev_bp = Blueprint('dev', __name__)


@dev_bp.route('/api/dev/reset', methods=['POST'])
@login_required
def reset_user_data():
    """Czyści wszystkie dane użytkownika (transakcje, kategorie, kontrahentów) — tylko do testów."""
    user_id = current_user.id
    try:
        user_tx_ids = [row[0] for row in db.session.query(Transaction.id).filter_by(user_id=user_id).all()]
        if user_tx_ids:
            db.session.query(TransactionSplit).filter(
                TransactionSplit.transaction_id.in_(user_tx_ids)
            ).delete(synchronize_session='fetch')

        db.session.query(TransactionStaging).filter_by(user_id=user_id).delete()
        db.session.query(TransactionArchive).filter_by(user_id=user_id).delete()
        db.session.query(Transaction).filter_by(user_id=user_id).delete()
        db.session.query(RecurringTransaction).filter_by(user_id=user_id).delete()
        db.session.query(PlannedTransaction).filter_by(user_id=user_id).delete()
        db.session.query(Budget).filter_by(user_id=user_id).delete()
        db.session.flush()

        db.session.query(Contractor).filter_by(user_id=user_id).update(
            {'default_category_id': None}, synchronize_session='fetch'
        )
        db.session.flush()
        db.session.query(Contractor).filter_by(user_id=user_id).delete()
        db.session.query(Category).filter_by(is_system_category=False).delete()
        db.session.query(Account).filter_by(user_id=user_id).update(
            {'balance': 0}, synchronize_session='fetch'
        )

        db.session.commit()
        return jsonify({'message': 'Dane zostały wyczyszczone.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
