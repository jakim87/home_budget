from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from sqlalchemy import text
from app import db

dev_bp = Blueprint('dev', __name__)


@dev_bp.route('/api/dev/reset', methods=['POST'])
@login_required
def reset_user_data():
    """Czyści wszystkie dane użytkownika — tylko do testów."""
    utok = current_user.token
    try:
        # 1. Wyzeruj FK do kategorii we WSZYSTKICH wierszach (kategorie są globalne, bez user_token)
        db.session.execute(text("UPDATE transactions SET category_id = NULL"))
        db.session.execute(text("UPDATE transaction_splits SET category_id = NULL"))
        db.session.execute(text("UPDATE transaction_staging SET proposed_category_id = NULL"))
        db.session.execute(text("UPDATE recurring_transactions SET category_id = NULL"))
        db.session.execute(text("UPDATE planned_transactions SET category_id = NULL"))
        db.session.execute(text("UPDATE contractors SET default_category_id = NULL"))
        db.session.flush()

        # 2. Usuń rekordy w odpowiedniej kolejności
        db.session.execute(text(
            "DELETE FROM transaction_splits "
            "WHERE transaction_id IN (SELECT id FROM transactions WHERE user_token = :utok)"
        ), {'utok': utok})
        db.session.execute(text("DELETE FROM transaction_staging WHERE user_token = :utok"), {'utok': utok})
        db.session.execute(text("DELETE FROM transaction_archive WHERE user_token = :utok"), {'utok': utok})
        db.session.execute(text("DELETE FROM transactions WHERE user_token = :utok"), {'utok': utok})
        db.session.execute(text("DELETE FROM recurring_transactions WHERE user_token = :utok"), {'utok': utok})
        db.session.execute(text("DELETE FROM planned_transactions WHERE user_token = :utok"), {'utok': utok})
        db.session.execute(text("DELETE FROM budgets WHERE user_token = :utok"), {'utok': utok})
        db.session.execute(text("DELETE FROM contractors WHERE user_token = :utok"), {'utok': utok})
        db.session.flush()

        # 3. Teraz bezpiecznie usuń kategorie (bez systemowych)
        db.session.execute(text("DELETE FROM categories WHERE is_system_category = false"))

        # 4. Wyzeruj salda kont
        db.session.execute(text("UPDATE accounts SET balance = 0 WHERE user_token = :utok"), {'utok': utok})

        db.session.commit()
        return jsonify({'message': 'Dane zostały wyczyszczone.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
