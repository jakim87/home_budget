from app import db
from app.models import Transaction, Account, TransactionStaging, Contractor
from datetime import date
from typing import Optional
from decimal import Decimal, InvalidOperation
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

def parse_ing_csv_row(row_data: str) -> Optional[dict]:
    """Parsuje pojedynczy wiersz z pliku CSV z banku ING."""
    # Używamy modułu csv w przypadku wystąpienia zakamuflowanych średników w nazwach
    reader = csv.reader(io.StringIO(row_data), delimiter=';')
    try:
        parts = next(reader)
    except StopIteration:
        raise ValueError("Pusta linia")
    
    if len(parts) < 9:
        raise ValueError(f"Nieprawidłowy format wiersza ING (znaleziono {len(parts)} kolumn, oczekiwano min. 9)")
        
    date_str = parts[0].strip()
    contractor = parts[2].strip() if parts[2].strip() else None
    title = parts[3].strip()
    
    # Oczyszczenie kwoty: usunięcie spacji, twardych spacji (\xa0) i zamiana przecinka na kropkę
    amount_str = parts[8].strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    
    if not amount_str:
        # Decyzja biznesowa: Nierozliczone płatności kartą (blokady) są pomijane. 
        # Główna kwota jest wtedy pusta. Zwracamy None, by parser pominął ten wiersz po cichu.
        return None

    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        raise ValueError(f"Nieprawidłowy format kwoty: {amount_str}")

    # Parsowanie daty (obsługa standardu bankowego oraz alternatywnego, np. z Excela)
    try:
        tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            tx_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            raise ValueError(f"Nieznany format daty: {date_str}")

    return {
        'date': tx_date,
        'contractor': contractor,
        'title': title,
        'amount': amount
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
            if parsed is not None:
                transactions.append(parsed)
        except ValueError as e:
            # Zaloguj w terminalu błąd tylko dla linii, które zaczynają się od cyfry (potencjalne transakcje)
            if line.strip() and line.strip()[0].isdigit():
                print(f"[Parser] Odrzucono potencjalną transakcję: {line}")
                print(f"[Parser] Powód: {e}")
            # Ignorujemy linie, które nie mają struktury transakcji (np. puste stopki/podsumowania ING)
            continue
            
    return transactions

def analyze_transaction_data(title: str, raw_contractor: Optional[str], user_id: int) -> tuple[Optional[int], Optional[int]]:
    """
    Analizuje dane transakcji (tytuł, surowy kontrahent) i próbuje dopasować
    znormalizowanego kontrahenta ze słownika oraz jego domyślną kategorię.
    """
    contractors = db.session.query(Contractor).filter_by(user_id=user_id).all()
    
    # Łączymy cały tekst z banku w jeden mały ciąg znaków (do wygodnego szukania substringów)
    search_text = f"{title} {raw_contractor or ''}".lower()
    
    for contractor in contractors:
        if contractor.mapping_rules:
            # Rozdzielamy reguły po przecinku (np. "biedronka, jeronimo martins")
            rules = [rule.strip().lower() for rule in contractor.mapping_rules.split(',')]
            for rule in rules:
                if rule and rule in search_text:
                    return contractor.default_category_id, contractor.id
                    
    return None, None

def save_transactions_to_staging(
    parsed_transactions: list[dict], 
    user_id: Optional[int] = None, 
    account_id: Optional[int] = None
) -> list[TransactionStaging]:
    """Zapisuje sparsowaną listę transakcji do tabeli tymczasowej (stagingowej)."""
    staging_records = []
    for tx_data in parsed_transactions:
        prop_cat_id, prop_contractor_id = None, None
        if user_id:
            prop_cat_id, prop_contractor_id = analyze_transaction_data(
                title=tx_data['title'],
                raw_contractor=tx_data.get('contractor'),
                user_id=user_id
            )

        staging_tx = TransactionStaging(
            date=tx_data['date'],
            amount=tx_data['amount'],
            title=tx_data['title'],
            contractor=tx_data.get('contractor'),
            user_id=user_id,
            account_id=account_id,
            proposed_category_id=prop_cat_id,
            proposed_contractor_id=prop_contractor_id
        )
        db.session.add(staging_tx)
        staging_records.append(staging_tx)
        
    db.session.commit()
    return staging_records