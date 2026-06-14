from app import db
from app.models import Transaction, Account, TransactionStaging, Contractor, Category, TransactionSplit
from datetime import date
from typing import Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime
from difflib import SequenceMatcher
import csv
import io
import re

_LEGAL_SUFFIXES = re.compile(
    r'\bSP(?:ÓŁKA)?\s+Z\s+O\.?O\.?\b'
    r'|\bSP(?:ÓŁKA)?\s+ZOO\b'
    r'|\bSPÓŁKA\s+Z\s+OGRANICZONĄ\s+ODPOWIEDZIALNOŚCIĄ\b'
    r'|\bS\.A\.\B|\bSA\b'
    r'|\bSP\.?\s*J\.?\b'
    r'|\bSP\.?\s*K\.?\b'
    r'|\bS\.C\.\b'
    r'|\bLTD\.?\b|\bLIMITED\b|\bGMBH\b|\bINC\.?\b'
    r'|\bPPH\b|\bFHU\b|\bPHU\b',
    re.IGNORECASE | re.UNICODE
)
_PAYMENT_ARTIFACTS = re.compile(
    r'PŁATNOŚć\s+KARTĄ.*|PLATNOSC\s+KARTA.*|NR\s+KARTY\s*[\dXx*]+.*'
    r'|PRZELEW\s+BANKOWY.*|ZLECENIE\s+STAŁE.*',
    re.IGNORECASE | re.UNICODE
)
_TRAILING_CODES = re.compile(r'[\s\d\-/\\.#]+$', re.UNICODE)
_TRAILING_WORDS = re.compile(r'(\s+[A-ZĄĆĘŁŃÓŚŹŻ]{2,})+$', re.UNICODE)
_MULTI_SPACE = re.compile(r'\s+')


def normalize_contractor_name(text: str) -> str:
    """Normalizuje surową nazwę kontrahenta z banku do czytelnej formy.
    Np. 'BIEDRONKA SP Z OO WARSZAWA 3' -> 'Biedronka'
    """
    if not text or not text.strip():
        return ''
    t = text.strip()
    t = _PAYMENT_ARTIFACTS.sub('', t).strip()
    if not t:
        return ''
    t = _LEGAL_SUFFIXES.sub('', t).strip()
    t = _TRAILING_CODES.sub('', t).strip()
    words = t.split()
    if len(words) > 2:
        t = ' '.join(words[:2])
    t = _MULTI_SPACE.sub(' ', t).strip()
    t = t.title()
    return t if len(t) >= 2 else ''


def _fuzzy_match_contractor(normalized_name: str, contractors: list) -> Optional[Contractor]:
    """Szuka najlepszego przybliżonego dopasowania powyżej progu 0.72."""
    if not normalized_name or len(normalized_name) < 3:
        return None
    name_l = normalized_name.lower()
    best_ratio = 0.72
    best_match = None
    for c in contractors:
        ratio = SequenceMatcher(None, name_l, c.name.lower()).ratio()
        if c.mapping_rules:
            for rule in c.mapping_rules.split(','):
                r = rule.strip().lower()
                if len(r) >= 3:
                    ratio = max(ratio, SequenceMatcher(None, name_l, r).ratio())
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = c
    return best_match

def create_transaction(
    user_token: str,
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

        account = db.session.query(Account).filter_by(id=account_id, user_token=user_token).first()
        if not account:
            raise ValueError(f"Konto o ID {account_id} nie istnieje lub brak uprawnień.")

        new_transaction = Transaction(
            user_token=user_token,
            account_id=account_id,
            amount=amount,
            title=title,
            date=transaction_date,
            category_id=category_id,
            contractor=contractor,
            contractor_id=contractor_id
        )

        account.balance = Decimal(account.balance) + amount

        db.session.add(new_transaction)

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
                if not (contractor_obj and contractor_obj.name.startswith("Moje konto: ")):
                    db.session.commit()
                    return new_transaction

                outflow_amount = -abs(amount)
                inflow_amount = abs(amount)

                if amount != outflow_amount:
                    correction = outflow_amount - amount
                    account.balance += correction
                    new_transaction.amount = outflow_amount

                dest_account_name = contractor_obj.name.replace("Moje konto: ", "")
                dest_account = db.session.query(Account).filter_by(user_token=user_token, name=dest_account_name, is_active=True).first()

                if not (dest_account and dest_account.id != account_id):
                    db.session.commit()
                    return new_transaction

                existing_mirror = db.session.query(Transaction).filter_by(user_token=user_token, account_id=dest_account.id, amount=inflow_amount, date=transaction_date).first()
                if not existing_mirror:
                    source_cont_name = f"Moje konto: {account.name}"
                    source_contractor = db.session.query(Contractor).filter_by(user_token=user_token, name=source_cont_name).first()
                    if not source_contractor:
                        source_contractor = Contractor(name=source_cont_name, user_token=user_token, default_category_id=category_id)
                        db.session.add(source_contractor)
                        db.session.flush()

                    mirror_tx = Transaction(user_token=user_token, account_id=dest_account.id, amount=inflow_amount, title=title, date=transaction_date, category_id=category_id, contractor=source_contractor.name, contractor_id=source_contractor.id)
                    dest_account.balance = Decimal(dest_account.balance) + inflow_amount
                    db.session.add(mirror_tx)

                matching_staging = db.session.query(TransactionStaging).filter_by(user_token=user_token, account_id=dest_account.id, amount=inflow_amount, date=transaction_date, status='pending').first()
                if matching_staging:
                    db.session.delete(matching_staging)

        db.session.commit()

        return new_transaction
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def reconcile_account_balance(user_token: str, account_id: int, new_balance: Decimal) -> Transaction:
    """
    Uzgadnia saldo konta. Tworzy transakcję korygującą, jeśli istnieje różnica
    między nowym saldem a bieżącym saldem w systemie.
    """
    try:
        account = db.session.query(Account).filter_by(id=account_id, user_token=user_token).first()
        if not account:
            raise ValueError(f"Konto o ID {account_id} nie istnieje lub brak uprawnień.")

        current_balance = Decimal(account.balance)
        difference = new_balance - current_balance

        if difference == Decimal('0.00'):
            return None

        reconciliation_category = db.session.query(Category).filter_by(name="Uzgadnianie salda", is_system_category=True).first()
        if not reconciliation_category:
            reconciliation_category = Category(name="Uzgadnianie salda", type="system_reconciliation", is_system_category=True)
            db.session.add(reconciliation_category)
            db.session.flush()

        reconciliation_tx = create_transaction(
            user_token=user_token,
            account_id=account_id,
            amount=difference,
            title="Uzgadnianie salda",
            transaction_date=date.today(),
            category_id=reconciliation_category.id,
            contractor="-"
        )
        db.session.commit()
        return reconciliation_tx
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
        return None

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

def parse_ing_csv(file_content: str, user_token: str, main_account_id: int) -> list[dict]:
    """
    Parsuje plik CSV z ING, używając podanego konta głównego jako kontekstu.
    """
    lines = file_content.strip().splitlines()

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

    key_map = {
        'date': 'Data transakcji',
        'contractor': 'Dane kontrahenta',
        'title': 'Tytuł',
        'counterparty_account': 'Nr rachunku',
        'amount': next((k for k in ['Kwota transakcji (waluta rachunku)', 'Kwota transakcji'] if k in header_map), None)
    }
    if not key_map['amount']:
        raise ValueError("Nie znaleziono kolumny z kwotą transakcji ('Kwota transakcji' lub 'Kwota transakcji (waluta rachunku)').")

    transactions = []
    for line in tx_lines:
        try:
            parsed_row = parse_ing_csv_row(line, header_map, key_map)
            if parsed_row is None:
                continue
            parsed_row['account_id'] = main_account_id
            transactions.append(parsed_row)
        except (ValueError, StopIteration, IndexError) as e:
            if line.strip() and line.strip()[0].isdigit():
                print(f"[Parser] Odrzucono potencjalną transakcję: {line}")
                print(f"[Parser] Powód: {e}")
            continue

    return transactions

def analyze_transaction_data(
    title: str,
    raw_contractor: Optional[str],
    user_token: str,
    counterparty_account: Optional[str] = None
) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Analizuje dane transakcji i próbuje dopasować kontrahenta ze słownika.
    Zwraca (category_id, contractor_id, suggested_name).
    suggested_name jest ustawiony tylko gdy nie znaleziono dopasowania.
    """
    # 1. Sprawdzenie przelewu wewnętrznego (po numerze konta)
    if counterparty_account:
        norm_csv_acc = _normalize_acc_num(counterparty_account)
        if norm_csv_acc:
            accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
            for acc in accounts:
                if acc.account_number and _normalize_acc_num(acc.account_number) == norm_csv_acc:
                    transfer_cat = db.session.query(Category).filter_by(name="Przelew wewnętrzny").first()
                    if not transfer_cat:
                        transfer_cat = Category(name="Przelew wewnętrzny", type="transfer")
                        db.session.add(transfer_cat)
                        db.session.commit()
                    cont_name = f"Moje konto: {acc.name}"
                    transfer_cont = db.session.query(Contractor).filter_by(user_token=user_token, name=cont_name).first()
                    if not transfer_cont:
                        transfer_cont = Contractor(name=cont_name, user_token=user_token, default_category_id=transfer_cat.id)
                        db.session.add(transfer_cont)
                        db.session.commit()
                    return transfer_cat.id, transfer_cont.id, None

    # 2. Dopasowanie po nazwie i regułach mapowania
    contractors = db.session.query(Contractor).filter_by(user_token=user_token, is_active=True).all()
    search_text = f"{title} {raw_contractor or ''}".lower()

    for contractor in contractors:
        if contractor.name and len(contractor.name) >= 3 and contractor.name.lower() in search_text:
            return contractor.default_category_id, contractor.id, None
        if contractor.mapping_rules:
            rules = [r.strip().lower() for r in contractor.mapping_rules.split(',')]
            for rule in rules:
                if rule and rule in search_text:
                    return contractor.default_category_id, contractor.id, None

    # 3. Fuzzy match na znormalizowanej nazwie
    normalized = normalize_contractor_name(raw_contractor or title or '')
    if normalized:
        fuzzy = _fuzzy_match_contractor(normalized, contractors)
        if fuzzy:
            return fuzzy.default_category_id, fuzzy.id, None

    # 4. Brak dopasowania — zwróć sugestię znormalizowanej nazwy
    suggested = normalize_contractor_name(raw_contractor or '') or normalize_contractor_name(title or '')
    return None, None, suggested or None

def save_transactions_to_staging(
    parsed_transactions: list[dict],
    user_token: Optional[str] = None
) -> list[TransactionStaging]:
    """Zapisuje sparsowaną listę transakcji do tabeli tymczasowej (stagingowej)."""
    try:
        staging_records = []
        for tx_data in parsed_transactions:
            prop_cat_id, prop_contractor_id, suggested_name = None, None, None
            if user_token:
                prop_cat_id, prop_contractor_id, suggested_name = analyze_transaction_data(
                    title=tx_data['title'],
                    raw_contractor=tx_data.get('contractor'),
                    user_token=user_token,
                    counterparty_account=tx_data.get('counterparty_account')
                )

            staging_tx = TransactionStaging(
                date=tx_data['date'],
                amount=tx_data['amount'],
                title=tx_data['title'],
                contractor=tx_data.get('contractor'),
                user_token=user_token,
                account_id=tx_data.get('account_id'),
                proposed_category_id=prop_cat_id,
                proposed_contractor_id=prop_contractor_id,
                suggested_contractor_name=suggested_name
            )
            db.session.add(staging_tx)
            staging_records.append(staging_tx)

        db.session.commit()
        return staging_records
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def approve_staging_record(user_token, stg_id, data):
    try:
        stg_tx = db.session.query(TransactionStaging).filter_by(id=stg_id, user_token=user_token, status='pending').first()
        if not stg_tx:
            raise ValueError('Nie znaleziono oczekującej transakcji.')

        if not stg_tx.account_id:
            raise ValueError('Ta transakcja nie ma przypisanego konta (pochodzi z wcześniejszego importu). Proszę usunąć ją i wgrać wyciąg ponownie.')

        category_name = data.get('category')
        contractor_id = data.get('contractor_id')

        if not category_name or not contractor_id:
            raise ValueError('Wybór kategorii i kontrahenta jest wymagany do zatwierdzenia.')

        category = db.session.query(Category).filter_by(name=category_name, is_active=True).first()
        if not category:
            raise ValueError(f"Kategoria '{category_name}' nie istnieje lub jest nieaktywna.")

        contractor = db.session.query(Contractor).filter_by(id=contractor_id, user_token=user_token, is_active=True).first()
        if not contractor:
            raise ValueError(f"Kontrahent o ID {contractor_id} nie istnieje lub jest nieaktywny.")

        new_tx = create_transaction(
            user_token=stg_tx.user_token,
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
