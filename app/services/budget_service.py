from app import db
from app.models import Transaction, Account, TransactionStaging, Contractor, Category, TransactionSplit
from datetime import date, datetime
from typing import Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime
import csv
import io

def create_transaction(
    user_id: int,
    account_id: int,
    amount: Decimal | float,
    title: str,
    transaction_date: date,
    category_id: Optional[int] = None,
    contractor: Optional[str] = None,
    contractor_id: Optional[int] = None,
    splits_data: Optional[list] = None
) -> Transaction:
    """
    Tworzy nową transakcję i automatycznie aktualizuje saldo powiązanego konta.
    """
    try:
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        account = db.session.query(Account).filter_by(id=account_id, user_id=user_id).first()
        if not account:
            raise ValueError(f"Konto o ID {account_id} nie istnieje lub brak uprawnień.")

        new_transaction = Transaction(
            user_id=user_id,
            account_id=account_id,
            amount=amount,
            title=title,
            date=transaction_date,
            category_id=category_id,
            contractor=contractor,
            contractor_id=contractor_id
        )

        # Aktualizacja salda konta (obsługa Decimal dla precyzji finansowej)
        account.balance = (Decimal(str(account.balance)) if not isinstance(account.balance, Decimal) else account.balance) + amount
        
        db.session.add(new_transaction)
        
        # --- ZAPIS PODZIAŁÓW (SPLITS) ---
        if splits_data:
            for split in splits_data:
                cat_name = split.get('category')
                split_cat = db.session.query(Category).filter_by(name=cat_name).first() if cat_name else None
                new_split = TransactionSplit(
                    amount=split.get('amount', 0),
                    desc=split.get('desc', ''),
                    category_id=split_cat.id if split_cat else None
                )
                new_transaction.splits.append(new_split)

        # --- LOGIKA PRZELEWÓW WEWNĘTRZNYCH ---
        if category_id and contractor_id:
            category = db.session.get(Category, category_id)
            if category and category.type == 'transfer':
                contractor_obj = db.session.get(Contractor, contractor_id)
                if contractor_obj and contractor_obj.name.startswith("Moje konto: "):
                    dest_account_name = contractor_obj.name.replace("Moje konto: ", "")
                    dest_account = db.session.query(Account).filter_by(user_id=user_id, name=dest_account_name, is_active=True).first()
                    
                    if dest_account and dest_account.id != account_id:
                        mirror_amount = -amount
                        
                        # Sprawdzamy, czy lustrzana transakcja już istnieje (np. dodana ręcznie lub przez drugi wyciąg)
                        existing_mirror = db.session.query(Transaction).filter_by(
                            user_id=user_id,
                            account_id=dest_account.id,
                            amount=mirror_amount,
                            date=transaction_date
                        ).first()
                        
                        if not existing_mirror:
                            source_cont_name = f"Moje konto: {account.name}"
                            source_contractor = db.session.query(Contractor).filter_by(user_id=user_id, name=source_cont_name).first()
                            if not source_contractor:
                                source_contractor = Contractor(name=source_cont_name, user_id=user_id, default_category_id=category_id)
                                db.session.add(source_contractor)
                                db.session.flush()
                                
                            mirror_tx = Transaction(
                                user_id=user_id,
                                account_id=dest_account.id,
                                amount=mirror_amount,
                                title=title,
                                date=transaction_date,
                                category_id=category_id,
                                contractor=source_contractor.name,
                                contractor_id=source_contractor.id
                            )
                            dest_account.balance = (Decimal(str(dest_account.balance)) if not isinstance(dest_account.balance, Decimal) else dest_account.balance) + mirror_amount
                            db.session.add(mirror_tx)
                            
                        # Usuwamy pasujący wpis ze stagingu (aby uniknąć duplikatów przy imporcie z wielu kont)
                        matching_staging = db.session.query(TransactionStaging).filter_by(
                            user_id=user_id,
                            account_id=dest_account.id,
                            amount=mirror_amount,
                            date=transaction_date,
                            status='pending'
                        ).first()
                        if matching_staging:
                            db.session.delete(matching_staging)

        db.session.commit()
        
        return new_transaction
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def _normalize_acc_num(acc_str: Optional[str]) -> str:
    """Normalizuje numer konta do porównań (usuwa spacje, cudzysłowy i prefix PL)."""
    if not acc_str:
        return ""
    return acc_str.replace(" ", "").replace("'", "").replace('"', "").upper().lstrip("PL")

def parse_ing_csv_row(row_data: str, header_map: dict, key_map: dict) -> Optional[dict]:
    """Parsuje pojedynczy wiersz z pliku CSV z banku ING na podstawie mapy nagłówka."""
    reader = csv.reader(io.StringIO(row_data), delimiter=';')
    try:
        parts = next(reader)
    except StopIteration:
        return None  # Pusta linia

    try:
        date_str = parts[header_map[key_map['date']]].strip()
        contractor = parts[header_map[key_map['contractor']]].strip() or None
        title = parts[header_map[key_map['title']]].strip()
        counterparty_account = parts[header_map[key_map['counterparty_account']]].strip() or None
        amount_str = parts[header_map[key_map['amount']]].strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    except (KeyError, IndexError) as e:
        raise ValueError(f"Błąd struktury pliku CSV. Brak oczekiwanej kolumny: {e} lub nieprawidłowy wiersz.")
    
    if not amount_str:
        return None

    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        raise ValueError(f"Nieprawidłowy format kwoty: {amount_str}")

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
        'amount': amount,
        'counterparty_account': counterparty_account
    }

def parse_ing_csv(file_content: str, user_id: int, main_account_id: int) -> list[dict]:
    """
    Parsuje plik CSV z ING, używając podanego konta głównego jako kontekstu.
    """
    lines = file_content.strip().splitlines()

    # 1. Znajdź nagłówek tabeli transakcji i zmapuj kolumny
    header_map = {}
    tx_lines = []
    in_tx_section = False
    for line in lines:
        if line.startswith('Data transakcji') or line.startswith('"Data transakcji"'):
            try:
                headers = next(csv.reader(io.StringIO(line), delimiter=';'))
                header_map = {header.strip(): i for i, header in enumerate(headers)}
                in_tx_section = True
            except StopIteration:
                pass
            continue
        if in_tx_section and line.strip():
            tx_lines.append(line)

    if not header_map:
        raise ValueError("Nie znaleziono nagłówka transakcji ('Data transakcji') w pliku CSV.")

    # 2. Znajdź faktyczne klucze nagłówków użyte w tym pliku
    key_map = {
        'date': 'Data transakcji',
        'contractor': 'Dane kontrahenta',
        'title': 'Tytuł',
        'counterparty_account': 'Nr rachunku',
        'amount': next((k for k in ['Kwota transakcji (waluta rachunku)', 'Kwota transakcji'] if k in header_map), None)
    }
    if not key_map['amount']:
        raise ValueError("Nie znaleziono kolumny z kwotą transakcji ('Kwota transakcji' lub 'Kwota transakcji (waluta rachunku)').")

    # 3. Parsuj wiersze transakcji
    transactions = []
    for line in tx_lines:
        try:
            parsed_row = parse_ing_csv_row(line, header_map, key_map)
            if parsed_row is None:
                continue

            # Każda transakcja w pliku dotyczy konta wybranego w formularzu
            parsed_row['account_id'] = main_account_id
            transactions.append(parsed_row)
        except (ValueError, StopIteration, IndexError) as e:
            if line.strip() and line.strip()[0].isdigit():
                print(f"[Parser] Odrzucono potencjalną transakcję: {line}")
                print(f"[Parser] Powód: {e}")
            continue
            
    return transactions

def analyze_transaction_data(title: str, raw_contractor: Optional[str], user_id: int, counterparty_account: Optional[str] = None) -> tuple[Optional[int], Optional[int]]:
    """
    Analizuje dane transakcji (tytuł, surowy kontrahent) i próbuje dopasować
    znormalizowanego kontrahenta ze słownika oraz jego domyślną kategorię.
    """
    # 1. Sprawdzenie przelewu wewnętrznego (po numerze konta)
    if counterparty_account:
        norm_csv_acc = _normalize_acc_num(counterparty_account)
        if norm_csv_acc:
            accounts = db.session.query(Account).filter_by(user_id=user_id, is_active=True).all()
            for acc in accounts:
                if acc.account_number and _normalize_acc_num(acc.account_number) == norm_csv_acc:
                    # Mamy przelew wewnętrzny!
                    transfer_cat = db.session.query(Category).filter_by(name="Przelew wewnętrzny").first()
                    if not transfer_cat:
                        transfer_cat = Category(name="Przelew wewnętrzny", type="transfer")
                        db.session.add(transfer_cat)
                        db.session.commit()
                        
                    cont_name = f"Moje konto: {acc.name}"
                    transfer_cont = db.session.query(Contractor).filter_by(user_id=user_id, name=cont_name).first()
                    if not transfer_cont:
                        transfer_cont = Contractor(name=cont_name, user_id=user_id, default_category_id=transfer_cat.id)
                        db.session.add(transfer_cont)
                        db.session.commit()
                        
                    return transfer_cat.id, transfer_cont.id

    # 2. Standardowe dopasowywanie na bazie słów kluczowych
    contractors = db.session.query(Contractor).filter_by(user_id=user_id, is_active=True).all()
    
    # Łączymy cały tekst z banku w jeden mały ciąg znaków (do wygodnego szukania substringów)
    search_text = f"{title} {raw_contractor or ''}".lower()
    
    for contractor in contractors:
        # 1. Sprawdzenie po dokładnej nazwie kontrahenta (minimum 3 znaki dla bezpieczeństwa)
        if contractor.name and len(contractor.name) >= 3 and contractor.name.lower() in search_text:
            return contractor.default_category_id, contractor.id
            
        if contractor.mapping_rules:
            # Rozdzielamy reguły po przecinku (np. "biedronka, jeronimo martins")
            rules = [rule.strip().lower() for rule in contractor.mapping_rules.split(',')]
            for rule in rules:
                if rule and rule in search_text:
                    return contractor.default_category_id, contractor.id
                    
    return None, None

def save_transactions_to_staging(
    parsed_transactions: list[dict], 
    user_id: Optional[int] = None
) -> list[TransactionStaging]:
    """Zapisuje sparsowaną listę transakcji do tabeli tymczasowej (stagingowej)."""
    try:
        staging_records = []
        for tx_data in parsed_transactions:
            prop_cat_id, prop_contractor_id = None, None
            if user_id:
                prop_cat_id, prop_contractor_id = analyze_transaction_data(
                    title=tx_data['title'],
                    raw_contractor=tx_data.get('contractor'),
                    user_id=user_id,
                    counterparty_account=tx_data.get('counterparty_account')
                )

            staging_tx = TransactionStaging(
                date=tx_data['date'],
                amount=tx_data['amount'],
                title=tx_data['title'],
                contractor=tx_data.get('contractor'),
                user_id=user_id,
                account_id=tx_data.get('account_id'),
                proposed_category_id=prop_cat_id,
                proposed_contractor_id=prop_contractor_id
            )
            db.session.add(staging_tx)
            staging_records.append(staging_tx)
            
        db.session.commit()
        return staging_records
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def approve_staging_record(user_id, stg_id, data):
    try:
        stg_tx = db.session.query(TransactionStaging).filter_by(id=stg_id, user_id=user_id, status='pending').first()
        if not stg_tx:
            raise ValueError('Nie znaleziono oczekującej transakcji.')
            
        if not stg_tx.account_id:
            raise ValueError('Ta transakcja nie ma przypisanego konta (pochodzi z wcześniejszego importu). Proszę usunąć ją i wgrać wyciąg ponownie.')
            
        category_name = data.get('category')
        contractor_id = data.get('contractor_id')
        
        if not category_name or not contractor_id:
            # Ta walidacja jest też w Marshmallow, ale dla pewności.
            raise ValueError('Wybór kategorii i kontrahenta jest wymagany do zatwierdzenia.')

        category = db.session.query(Category).filter_by(name=category_name, is_active=True).first()
        if not category:
            raise ValueError(f"Kategoria '{category_name}' nie istnieje lub jest nieaktywna.")

        contractor = db.session.query(Contractor).filter_by(id=contractor_id, user_id=user_id, is_active=True).first()
        if not contractor:
            raise ValueError(f"Kontrahent o ID {contractor_id} nie istnieje lub jest nieaktywny.")
            
        new_tx = create_transaction(
            user_id=stg_tx.user_id,
            account_id=stg_tx.account_id,
            amount=stg_tx.amount,
            title=stg_tx.title,
            transaction_date=stg_tx.date,
            category_id=category.id,
            contractor=stg_tx.contractor,
            contractor_id=contractor.id
        )
        db.session.delete(stg_tx)
        db.session.commit()
        return new_tx
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))