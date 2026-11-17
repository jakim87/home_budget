from app import db
from app.models import PlannedTransaction, Account, Contractor
from app.services.budget_service import create_transaction as create_standard_transaction
from app.services.category_service import find_owned as find_category_owned
from calendar import monthrange
from datetime import date
from decimal import Decimal
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
        if data.get('category_id') is not None:
            if not find_category_owned(user_token, data['category_id']):
                raise ValueError("Kategoria nie istnieje, jest nieaktywna lub brak uprawnień.")

        planned_tx = PlannedTransaction(user_token=user_token, **data)
        db.session.add(planned_tx)
        db.session.commit()
        return planned_tx
    except Exception:
        db.session.rollback()
        raise

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
    except Exception:
        db.session.rollback()
        raise

def planned_dict(pt: PlannedTransaction) -> dict:
    """Oczekująca zaplanowana w kształcie wiersza transakcji (jak _wystapienie_dict
    w recurring_service) — front pokazuje ją na liście operacji obok cyklicznych."""
    return {
        'id': f'plan-{pt.id}',
        'desc': pt.title,
        'amount': float(pt.amount),
        'date': pt.execution_date.isoformat(),
        'category': pt.category.name if pt.category else 'Inne',
        'contractor_id': pt.contractor_id,
        'contractor_name': pt.contractor.name if pt.contractor else None,
        'account_id': pt.account_id,
        'comment': '',
        'isVirtual': True,
        'planned_id': pt.id,
        'do_potwierdzenia': pt.execution_date <= date.today(),
        'najstarsze': True,
    }


def planned_preview(user_token, year: int, month: int) -> list:
    """Oczekujące zaplanowane z datą w danym miesiącu."""
    od = date(year, month, 1)
    do = date(year, month, monthrange(year, month)[1])
    return [planned_dict(pt) for pt in db.session.query(PlannedTransaction).filter(
        PlannedTransaction.user_token == user_token,
        PlannedTransaction.status == 'pending',
        PlannedTransaction.execution_date >= od,
        PlannedTransaction.execution_date <= do,
    ).all()]


def oczekujace_potwierdzenia(user_token) -> list:
    """Zaplanowane, których termin nadszedł, a użytkownik ich nie rozstrzygnął."""
    return [planned_dict(pt) for pt in db.session.query(PlannedTransaction).filter(
        PlannedTransaction.user_token == user_token,
        PlannedTransaction.status == 'pending',
        PlannedTransaction.execution_date <= date.today(),
    ).all()]


def _zablokuj_oczekujaca(user_token, pt_id) -> PlannedTransaction:
    """Zaplanowana do rozstrzygnięcia, z blokadą wiersza — drugie równoległe
    potwierdzenie czeka, po czym widzi zmieniony status i zostaje odrzucone."""
    pt = (db.session.query(PlannedTransaction)
          .filter_by(id=pt_id, user_token=user_token)
          .with_for_update().populate_existing().first())
    if not pt:
        raise ValueError("Nie znaleziono zaplanowanej transakcji lub brak uprawnień.")
    if pt.status != 'pending':
        raise ValueError("Ta zaplanowana transakcja jest już rozstrzygnięta.")
    if pt.execution_date > date.today():
        raise ValueError("Tej transakcji nie można jeszcze potwierdzić — jej termin nie nadszedł.")
    return pt


def potwierdz_zaplanowana(user_token, pt_id, amount: Decimal | None = None,
                          transaction_date: date | None = None):
    """Księguje zaplanowaną; poprawka kwoty (bez znaku) i daty jak w cyklicznych."""
    try:
        pt = _zablokuj_oczekujaca(user_token, pt_id)
        kwota = pt.amount if amount is None else abs(Decimal(str(amount))).copy_sign(pt.amount)
        transakcja = create_standard_transaction(
            user_token=user_token,
            account_id=pt.account_id,
            amount=kwota,
            title=pt.title,
            transaction_date=transaction_date or pt.execution_date,
            category_id=pt.category_id,
            contractor_id=pt.contractor_id,
            source_planned_id=pt.id,
            commit=False,
        )
        pt.status = 'processed'
        db.session.commit()
        logger.info("Potwierdzono zaplanowaną ID %s, transakcja ID %s", pt.id, transakcja.id)
        return transakcja
    except Exception:
        db.session.rollback()
        raise


def pomin_zaplanowana(user_token, pt_id):
    """Rozstrzyga zaplanowaną bez księgowania („nie wykonała się")."""
    try:
        pt = _zablokuj_oczekujaca(user_token, pt_id)
        pt.status = 'skipped'
        db.session.commit()
        logger.info("Pominięto zaplanowaną ID %s", pt.id)
        return pt
    except Exception:
        db.session.rollback()
        raise
