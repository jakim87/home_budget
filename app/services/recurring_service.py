from app import db
from app.models import RecurringTransaction, Transaction, Account, Category, Contractor, User, Frequency
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from app.services.budget_service import create_transaction as create_standard_transaction # Avoid name collision

def _calculate_next_run_date_for_recurring(rec_tx: RecurringTransaction, current_run_date: date) -> date:
    """
    Calculates the *next* scheduled run date for a recurring transaction
    based on its frequency and interval, starting from current_run_date.
    """
    next_date = current_run_date

    if rec_tx.frequency == Frequency.DAILY:
        next_date += timedelta(days=rec_tx.interval)
    elif rec_tx.frequency == Frequency.WEEKLY:
        next_date += timedelta(weeks=rec_tx.interval)
        # If day_of_week is specified, ensure it lands on that day
        if rec_tx.day_of_week is not None:
            # Calculate days to add to reach the target day_of_week
            # (target_day - current_day + 7) % 7
            days_until_target_day = (rec_tx.day_of_week - next_date.weekday() + 7) % 7
            next_date += timedelta(days=days_until_target_day)
    elif rec_tx.frequency == Frequency.MONTHLY:
        next_date += relativedelta(months=rec_tx.interval)
        # If day_of_month is specified, adjust to that day
        if rec_tx.day_of_month is not None:
            try:
                next_date = next_date.replace(day=rec_tx.day_of_month)
            except ValueError:
                # If day_of_month is too high for the month (e.g., 31st in Feb), use last day of month
                # This moves to the first day of the next month, then subtracts one day.
                next_date = next_date.replace(day=1) + relativedelta(months=1, days=-1)
    elif rec_tx.frequency == Frequency.YEARLY:
        next_date += relativedelta(years=rec_tx.interval)
        # If day_of_month is specified, adjust to that day
        if rec_tx.day_of_month is not None:
            try:
                next_date = next_date.replace(day=rec_tx.day_of_month)
            except ValueError:
                # Similar logic for year, if day_of_month is invalid for the target month
                next_date = next_date.replace(day=1) + relativedelta(months=1, days=-1)
    
    return next_date


def _calculate_first_occurrence_date(start_date: date, frequency: Frequency, interval: int) -> date:
    """
    Calculates the first run date for a recurring transaction.
    If the start_date is in the future, it returns start_date.
    If the start_date is in the past, it calculates the first upcoming
    run date that is on or after today.
    """
    next_run = start_date
    today = date.today()

    if next_run >= today:
        return next_run

    # Advance date from the past until it's on or after today
    while next_run < today:
        if frequency == Frequency.DAILY:
            next_run += timedelta(days=interval)
        elif frequency == Frequency.WEEKLY:
            next_run += timedelta(weeks=interval)
        elif frequency == Frequency.MONTHLY:
            next_run += relativedelta(months=interval)
        elif frequency == Frequency.YEARLY:
            next_run += relativedelta(years=interval)
        else:
            # Fallback for unknown frequency, should not be reached with schema validation
            return today
    
    return next_run

def create_recurring_transaction(user_id, data):
    """Creates a new recurring transaction definition with improved clarity."""
    next_run_date = _calculate_first_occurrence_date(
        start_date=data['start_date'],
        frequency=data['frequency'],
        interval=data.get('interval', 1)
    )

    rec_tx = RecurringTransaction(
        user_id=user_id,
        account_id=data['account_id'],
        category_id=data.get('category_id'),
        contractor_id=data.get('contractor_id'),
        title=data['title'],
        amount=data['amount'],
        frequency=data['frequency'],
        interval=data.get('interval', 1),
        day_of_week=data.get('day_of_week'),
        day_of_month=data.get('day_of_month'),
        start_date=data['start_date'],
        end_date=data.get('end_date'),
        next_run_date=next_run_date,
        is_active=data.get('is_active', True)
    )
    db.session.add(rec_tx)
    db.session.commit()
    return rec_tx

def get_all_recurring_transactions(user_id):
    return db.session.query(RecurringTransaction).filter_by(user_id=user_id, is_active=True).all()

def update_recurring_transaction(user_id, rec_tx_id, data):
    # Używamy db.session.get() do pobrania po kluczu głównym
    rec_tx = db.session.get(RecurringTransaction, rec_tx_id)
    
    # Weryfikujemy istnienie i prawa dostępu
    if not rec_tx or rec_tx.user_id != user_id:
        raise ValueError("Recurring transaction not found or access denied.")
    
    # --- Jawna aktualizacja pól dla bezpieczeństwa i czytelności ---
    rec_tx.title = data.get('title', rec_tx.title)
    rec_tx.amount = data.get('amount', rec_tx.amount)
    rec_tx.account_id = data.get('account_id', rec_tx.account_id)
    rec_tx.category_id = data.get('category_id', rec_tx.category_id)
    rec_tx.contractor_id = data.get('contractor_id', rec_tx.contractor_id)
    rec_tx.is_active = data.get('is_active', rec_tx.is_active)
    rec_tx.end_date = data.get('end_date', rec_tx.end_date)
    
    # --- Przeliczenie next_run_date, jeśli zmieniły się pola częstotliwości ---
    recalculate_date = False
    if 'start_date' in data and data['start_date'] != rec_tx.start_date:
        rec_tx.start_date = data['start_date']
        recalculate_date = True
    if 'frequency' in data and data['frequency'] != rec_tx.frequency:
        rec_tx.frequency = data['frequency']
        recalculate_date = True
    if 'interval' in data and data['interval'] != rec_tx.interval:
        rec_tx.interval = data['interval']
        recalculate_date = True
    
    # Aktualizacja dni tygodnia/miesiąca, które są częścią definicji częstotliwości
    if 'day_of_week' in data:
        rec_tx.day_of_week = data['day_of_week']
    if 'day_of_month' in data:
        rec_tx.day_of_month = data['day_of_month']

    if recalculate_date:
        rec_tx.next_run_date = _calculate_first_occurrence_date(
            start_date=rec_tx.start_date,
            frequency=rec_tx.frequency,
            interval=rec_tx.interval
        )
    
    db.session.commit()
    return rec_tx

def delete_recurring_transaction(user_id, rec_tx_id):
    rec_tx = db.session.query(RecurringTransaction).filter_by(id=rec_tx_id, user_id=user_id).first()
    if not rec_tx:
        raise ValueError("Recurring transaction not found.")
    db.session.delete(rec_tx)
    db.session.commit()

def process_recurring_transactions():
    """
    Processes all due recurring transactions and creates standard transactions.
    """
    created_count = 0
    today = date.today()
    
    due_recurring_transactions = db.session.query(RecurringTransaction).filter(
        RecurringTransaction.next_run_date <= today,
        RecurringTransaction.is_active == True
    ).all()

    for rec_tx in due_recurring_transactions:
        if rec_tx.end_date and rec_tx.next_run_date > rec_tx.end_date:
            rec_tx.is_active = False
            db.session.commit()
            continue

        try:
            create_standard_transaction(
                user_id=rec_tx.user_id,
                account_id=rec_tx.account_id,
                amount=rec_tx.amount,
                title=rec_tx.title,
                transaction_date=rec_tx.next_run_date,
                category_id=rec_tx.category_id,
                contractor_id=rec_tx.contractor_id
            )
            created_count += 1

            rec_tx.next_run_date = _calculate_next_run_date_for_recurring(rec_tx, rec_tx.next_run_date)

            rec_tx.updated_at = datetime.now(timezone.utc)
            db.session.commit()

        except Exception as e:
            print(f"Error processing recurring transaction ID {rec_tx.id}: {e}")
            db.session.rollback()
            continue
    
    return created_count
