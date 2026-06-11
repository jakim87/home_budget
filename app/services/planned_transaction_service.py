from app import db
from app.models import PlannedTransaction
from app.services.budget_service import create_transaction as create_standard_transaction
from datetime import date

def create_planned_transaction(user_id, data):
    """Tworzy nową definicję zaplanowanej transakcji."""
    try:
        planned_tx = PlannedTransaction(user_id=user_id, **data)
        db.session.add(planned_tx)
        db.session.commit()
        return planned_tx
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Błąd podczas tworzenia zaplanowanej transakcji: {e}")

def get_all_planned_transactions(user_id):
    """Pobiera wszystkie aktywne (pending) zaplanowane transakcje dla użytkownika."""
    return db.session.query(PlannedTransaction).filter_by(user_id=user_id, status='pending').order_by(PlannedTransaction.execution_date.asc()).all()

def delete_planned_transaction(user_id, pt_id):
    """Usuwa definicję zaplanowanej transakcji."""
    try:
        planned_tx = db.session.query(PlannedTransaction).filter_by(id=pt_id, user_id=user_id).first()
        if not planned_tx:
            raise ValueError("Nie znaleziono zaplanowanej transakcji lub brak uprawnień.")
        db.session.delete(planned_tx)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Błąd podczas usuwania: {e}")

def process_planned_transactions():
    """
    Przetwarza wszystkie należne zaplanowane transakcje, tworząc z nich standardowe transakcje.
    """
    created_count = 0
    today = date.today()
    
    due_planned_txs = db.session.query(PlannedTransaction).filter(
        PlannedTransaction.execution_date <= today,
        PlannedTransaction.status == 'pending'
    ).all()

    for pt in due_planned_txs:
        try:
            create_standard_transaction(
                user_id=pt.user_id,
                account_id=pt.account_id,
                amount=pt.amount,
                title=pt.title,
                transaction_date=pt.execution_date,
                category_id=pt.category_id,
                contractor_id=pt.contractor_id
            )
            pt.status = 'processed'
            db.session.commit()
            created_count += 1
        except Exception as e:
            print(f"Błąd podczas przetwarzania zaplanowanej transakcji ID {pt.id}: {e}")
            db.session.rollback()
            continue
            
    return created_count