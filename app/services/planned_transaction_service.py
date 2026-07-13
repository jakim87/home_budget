from app import db
from app.models import PlannedTransaction, Transaction, Account, Contractor
from app.services.budget_service import create_transaction as create_standard_transaction
from datetime import date
import logging

logger = logging.getLogger(__name__)

def create_planned_transaction(user_token, data):
    """Tworzy nową definicję zaplanowanej transakcji."""
    try:
        # Walidacja własności — konto i kontrahent muszą należeć do użytkownika i być aktywne.
        account = db.session.query(Account).filter_by(
            id=data.get('account_id'), user_token=user_token, is_active=True
        ).first()
        if not account:
            raise ValueError("Konto nie istnieje, jest nieaktywne lub brak uprawnień.")
        if data.get('contractor_id') is not None:
            contractor = db.session.query(Contractor).filter_by(
                id=data['contractor_id'], user_token=user_token, is_active=True
            ).first()
            if not contractor:
                raise ValueError("Kontrahent nie istnieje, jest nieaktywny lub brak uprawnień.")

        planned_tx = PlannedTransaction(user_token=user_token, **data)
        db.session.add(planned_tx)
        db.session.commit()
        return planned_tx
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Błąd podczas tworzenia zaplanowanej transakcji: {e}")

def get_all_planned_transactions(user_token):
    """Pobiera wszystkie aktywne (pending) zaplanowane transakcje dla użytkownika."""
    return db.session.query(PlannedTransaction).filter_by(user_token=user_token, status='pending').order_by(PlannedTransaction.execution_date.asc()).all()

def delete_planned_transaction(user_token, pt_id):
    """Usuwa definicję zaplanowanej transakcji."""
    try:
        planned_tx = db.session.query(PlannedTransaction).filter_by(id=pt_id, user_token=user_token).first()
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

    query = db.session.query(PlannedTransaction).filter(
        PlannedTransaction.execution_date <= today,
        PlannedTransaction.status == 'pending'
    )
    if db.session.get_bind().dialect.name == 'postgresql':
        query = query.with_for_update(skip_locked=True)
    due_planned_txs = query.all()

    for pt in due_planned_txs:
        try:
            # Strażnik idempotentności: jeśli transakcja z tej definicji na tę datę
            # już istnieje (np. awaria przed zmianą statusu), nie twórz jej ponownie.
            already_created = db.session.query(Transaction).filter_by(
                source_planned_id=pt.id, date=pt.execution_date
            ).first()

            if not already_created:
                # commit=False → utworzenie transakcji i zmiana statusu jednym commitem.
                create_standard_transaction(
                    user_token=pt.user_token,
                    account_id=pt.account_id,
                    amount=pt.amount,
                    title=pt.title,
                    transaction_date=pt.execution_date,
                    category_id=pt.category_id,
                    contractor_id=pt.contractor_id,
                    source_planned_id=pt.id,
                    commit=False
                )
                created_count += 1

            pt.status = 'processed'
            db.session.commit()
        except Exception as e:
            logger.error("Błąd podczas przetwarzania zaplanowanej transakcji ID %s: %s", pt.id, e)
            db.session.rollback()
            continue

    logger.info("Przetwarzanie zaplanowanych transakcji: utworzono %d nowych transakcji", created_count)
    return created_count
