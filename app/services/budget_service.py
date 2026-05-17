from app import db
from app.models import Transaction, Account, TransactionStaging
from datetime import date
from typing import Optional
from decimal import Decimal
from datetime import datetime
import csv
import io

def create_transaction(
    user_id: int,
    account_id: int,
    amount: float,
    title: str,
    transaction_date: date,
    category_id: Optional[int] = None,
    contractor: Optional[str] = None
) -> Transaction:
    """
    Tworzy nową transakcję i automatycznie aktualizuje saldo powiązanego konta.
    """
    account = db.session.get(Account, account_id)
    if not account:
        raise ValueError(f"Konto o ID {account_id} nie istnieje.")

    new_transaction = Transaction(
        user_id=user_id,
        account_id=account_id,
        amount=amount,
        title=title,
        date=transaction_date,
        category_id=category_id,
        contractor=contractor
    )

    # Aktualizacja salda konta (obsługa Decimal dla precyzji finansowej)
    account.balance = Decimal(str(account.balance)) + Decimal(str(amount))
    
    db.session.add(new_transaction)
    db.session.commit()
    
    return new_transaction

def parse_ing_csv_row(row_data: str) -> dict:
    """Parsuje pojedynczy wiersz z pliku CSV z banku ING."""
    # Używamy modułu csv w przypadku wystąpienia zakamuflowanych średników w nazwach
    reader = csv.reader(io.StringIO(row_data), delimiter=';')
    parts = next(reader)
    
    if len(parts) < 6:
        raise ValueError("Nieprawidłowy format wiersza ING")
        
    date_str = parts[0].strip()
    contractor = parts[2].strip() if parts[2].strip() else None
    title = parts[3].strip()
    
    # Oczyszczenie kwoty: usunięcie możliwych spacji i zamiana przecinka na kropkę dla formatu Decimal
    amount_str = parts[5].strip().replace(' ', '').replace(',', '.')
    
    return {
        'date': datetime.strptime(date_str, '%Y-%m-%d').date(),
        'contractor': contractor,
        'title': title,
        'amount': Decimal(amount_str)
    }

def parse_ing_csv(file_content: str) -> list[dict]:
    """Parsuje cały plik CSV z banku ING, pomijając nagłówki i metadane pliku."""
    transactions = []
    for line in file_content.strip().splitlines():
        # Prosty filtr odrzucający puste linie i typowe nagłówki ING ("Data transakcji...")
        if not line.strip() or line.startswith('Data'):
            continue
            
        try:
            parsed = parse_ing_csv_row(line)
            transactions.append(parsed)
        except ValueError:
            # Ignorujemy linie, które nie mają struktury transakcji (np. puste stopki/podsumowania ING)
            continue
            
    return transactions

def save_transactions_to_staging(
    parsed_transactions: list[dict], 
    user_id: Optional[int] = None, 
    account_id: Optional[int] = None
) -> list[TransactionStaging]:
    """Zapisuje sparsowaną listę transakcji do tabeli tymczasowej (stagingowej)."""
    staging_records = []
    for tx_data in parsed_transactions:
        staging_tx = TransactionStaging(
            date=tx_data['date'],
            amount=tx_data['amount'],
            title=tx_data['title'],
            contractor=tx_data.get('contractor'),
            user_id=user_id,
            account_id=account_id
        )
        db.session.add(staging_tx)
        staging_records.append(staging_tx)
        
    db.session.commit()
    return staging_records