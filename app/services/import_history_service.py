"""Historia importów wyciągów — ewidencja, wykrywanie nakładających się zakresów
i sygnał pokrycia dla modelu transferów.
"""
import logging
from datetime import date
from typing import Optional

from app import db
from app.models import Account, StatementImport

logger = logging.getLogger(__name__)


def record_statement_import(
    user_token: str,
    filename: str,
    bank: str,
    file_format: str,
    account_id: Optional[int],
    period_start: Optional[date],
    period_end: Optional[date],
    transaction_count: int,
    skipped_count: int,
    batch_id: str,
    commit: bool = True,
) -> StatementImport:
    """Zapisuje wpis historii dla jednej pary (plik, pokryte konto)."""
    entry = StatementImport(
        user_token=user_token,
        batch_id=batch_id,
        filename=filename[:255],
        bank=bank,
        file_format=file_format,
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        transaction_count=transaction_count,
        skipped_count=skipped_count,
    )
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry


def find_overlapping_imports(
    user_token: str,
    account_id: Optional[int],
    period_start: Optional[date],
    period_end: Optional[date],
) -> list[StatementImport]:
    """Zwraca wcześniejsze importy tego konta, których zakres nachodzi na podany.

    Nakładanie liczone inkluzywnie (dotknięcie brzegami to już nakładanie):
    istniejący.start <= nowy.koniec ORAZ istniejący.koniec >= nowy.start.
    """
    if account_id is None or period_start is None or period_end is None:
        return []
    return (
        db.session.query(StatementImport)
        .filter(
            StatementImport.user_token == user_token,
            StatementImport.account_id == account_id,
            StatementImport.period_start.isnot(None),
            StatementImport.period_end.isnot(None),
            StatementImport.period_start <= period_end,
            StatementImport.period_end >= period_start,
        )
        .order_by(StatementImport.imported_at.desc())
        .all()
    )


def account_has_statement_imports(user_token: str, account_id: Optional[int]) -> bool:
    """Czy konto dostaje własne wyciągi (sygnał pokrycia dla modelu transferów).

    True → druga noga przelewu wewnętrznego przyjdzie z własnego wyciągu tego
    konta, więc lustra generować NIE wolno (podwójne liczenie).
    False → konto nie ma własnych wyciągów (np. cel oszczędnościowy); lustro jest
    jedynym źródłem drugiej strony.
    """
    if account_id is None:
        return False
    return db.session.query(
        db.session.query(StatementImport)
        .filter(
            StatementImport.user_token == user_token,
            StatementImport.account_id == account_id,
        )
        .exists()
    ).scalar()


def build_overlap_warning(overlaps: list[StatementImport]) -> Optional[str]:
    """Buduje komunikat ostrzegawczy o nakładaniu zakresów (albo None)."""
    if not overlaps:
        return None
    prev = overlaps[0]
    account_name = prev.account.name if prev.account else f"konto #{prev.account_id}"
    zakres = ''
    if prev.period_start and prev.period_end:
        zakres = f" ({prev.period_start.strftime('%d.%m.%Y')}–{prev.period_end.strftime('%d.%m.%Y')})"
    return (
        f"Dla konta „{account_name}” zaimportowano już nakładający się zakres{zakres} "
        f"z pliku „{prev.filename}”. Duplikaty transakcji zostały pominięte, ale sprawdź, "
        f"czy to zamierzone."
    )


def list_import_history(user_token: str, limit: int = 100) -> list[dict]:
    """Historia importów użytkownika — najnowsze najpierw."""
    rows = (
        db.session.query(StatementImport, Account)
        .outerjoin(Account, StatementImport.account_id == Account.id)
        .filter(StatementImport.user_token == user_token)
        .order_by(StatementImport.imported_at.desc(), StatementImport.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id': imp.id,
            'batch_id': imp.batch_id,
            'filename': imp.filename,
            'bank': imp.bank,
            'file_format': imp.file_format,
            'account_id': imp.account_id,
            'account_name': acc.name if acc else None,
            'period_start': imp.period_start.strftime('%Y-%m-%d') if imp.period_start else None,
            'period_end': imp.period_end.strftime('%Y-%m-%d') if imp.period_end else None,
            'transaction_count': imp.transaction_count,
            'skipped_count': imp.skipped_count,
            'imported_at': imp.imported_at.strftime('%Y-%m-%d %H:%M') if imp.imported_at else None,
        }
        for imp, acc in rows
    ]
