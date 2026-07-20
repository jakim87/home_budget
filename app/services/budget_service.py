from app import db
from app.models import Transaction, Account, TransactionStaging, Contractor, Category, TransactionSplit
from app.services.import_history_service import account_has_statement_imports
from datetime import date, timedelta
from typing import Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime
from difflib import SequenceMatcher
import csv
import io
import re
import logging

# logging.getLogger(__name__) -> logger dostaje nazwę "app.services.budget_service".
# Dzięki temu w pliku logów widać dokładnie, KTÓRY moduł zapisał daną linię.
logger = logging.getLogger(__name__)

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
    splits_data: Optional[list] = None,
    comment: Optional[str] = None,
    source_recurring_id: Optional[int] = None,
    source_planned_id: Optional[int] = None,
    commit: bool = True,
    preserve_sign: bool = False
) -> Transaction:
    """
    Tworzy nową transakcję i automatycznie aktualizuje saldo powiązanego konta.

    commit=False pozwala wywołującemu (np. zatwierdzanie stagingu, przetwarzanie
    harmonogramu) domknąć transakcję jednym wspólnym commitem — dzięki temu utworzenie
    transakcji i powiązana operacja (usunięcie stagingu, przesunięcie next_run_date)
    są atomowe (albo obie się udają, albo obie cofają). Zapobiega to podwójnym
    księgowaniom po awarii między dwoma osobnymi commitami.
    """
    try:
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        account = db.session.query(Account).filter_by(id=account_id, user_token=user_token, is_active=True).first()
        if not account:
            raise ValueError(f"Konto o ID {account_id} nie istnieje, jest nieaktywne lub brak uprawnień.")

        new_transaction = Transaction(
            user_token=user_token,
            account_id=account_id,
            amount=amount,
            title=title,
            date=transaction_date,
            category_id=category_id,
            contractor=contractor,
            contractor_id=contractor_id,
            comment=comment or None,
            source_recurring_id=source_recurring_id,
            source_planned_id=source_planned_id
        )

        account.balance = Decimal(account.balance) + amount

        db.session.add(new_transaction)

        if splits_data:
            for split in splits_data:
                cat_name = split.get('category')
                split_cat = db.session.query(Category).filter_by(name=cat_name, is_active=True).first() if cat_name else None
                new_split = TransactionSplit(
                    amount=Decimal(str(split.get('amount', 0))),
                    desc=split.get('desc', ''),
                    category_id=split_cat.id if split_cat else None
                )
                new_transaction.splits.append(new_split)

        # --- LOGIKA PRZELEWÓW WEWNĘTRZNYCH ---
        if category_id and contractor_id:
            category = db.session.get(Category, category_id)
            if category and category.type == 'transfer':
                contractor_obj = db.session.query(Contractor).filter_by(
                    id=contractor_id, user_token=user_token, is_active=True
                ).first()
                if contractor_obj and contractor_obj.name.startswith("Moje konto: "):
                    _handle_internal_transfer(
                        user_token, account, new_transaction, contractor_obj,
                        amount, title, transaction_date, category_id, preserve_sign
                    )

        if commit:
            db.session.commit()

        return new_transaction
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))


def _resolve_destination_account(user_token: str, contractor_obj: Contractor) -> Optional[Account]:
    """Wyznacza konto docelowe przelewu wewnętrznego dla kontrahenta 'Moje konto: {nazwa}'.

    Najpierw po twardym powiązaniu (linked_account_id) — odporne na zmianę nazwy i
    duplikaty. Dopiero w razie braku powiązania (stare dane) wraca do dopasowania po nazwie.
    """
    if contractor_obj.linked_account_id:
        acc = db.session.query(Account).filter_by(
            id=contractor_obj.linked_account_id, user_token=user_token, is_active=True
        ).first()
        if acc:
            return acc

    dest_account_name = contractor_obj.name.replace("Moje konto: ", "")
    matches = db.session.query(Account).filter_by(
        user_token=user_token, name=dest_account_name, is_active=True
    ).all()
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Niejednoznaczna nazwa konta — nie zgadujemy, na które konto trafiają pieniądze.
        logger.warning(
            "Przelew wewnętrzny: nazwa konta '%s' jest niejednoznaczna (%d dopasowań, user_token=%s) — pomijam lustro.",
            dest_account_name, len(matches), user_token
        )
    return None


# Tolerancja dat przy parowaniu nóg przelewu — ta sama operacja bywa księgowana
# w różnych dniach po obu stronach (zwłaszcza między bankami).
_TRANSFER_MATCH_WINDOW_DAYS = 4


def _handle_internal_transfer(
    user_token: str, account: Account, new_transaction: Transaction,
    contractor_obj: Contractor, amount: Decimal, title: str,
    transaction_date: date, category_id: int, preserve_sign: bool = False
) -> None:
    """Obsługuje przelew wewnętrzny: parowanie z drugą nogą albo wygenerowanie lustra.

    Kolejność decyzji:
    1. Jeśli druga noga JUŻ istnieje (realna, z wyciągu drugiego konta) — wiążemy obie
       i nic nie tworzymy.
    2. Jeśli konto docelowe dostaje własne wyciągi — druga noga przyjdzie realnie,
       więc lustra NIE generujemy (inaczej podwójne liczenie). Transakcja zostaje
       niepowiązana (linked_transaction_id IS NULL) = widoczny "wiersz do zmapowania",
       który domknie się sam, gdy tamta noga zostanie zatwierdzona.
    3. Dopiero gdy konto docelowe nie ma własnych wyciągów (np. cel oszczędnościowy),
       lustro jest jedynym źródłem drugiej strony — tworzymy je jak dotąd.

    preserve_sign=True (import z wyciągu): znak kwoty pochodzi z banku i jest źródłem
    prawdy — nie wymuszamy wypływu. Przy ręcznym dodawaniu (False) strona źródłowa
    jest wypływem, bo formularz oznacza "wyślij z tego konta".
    """
    if not preserve_sign:
        outflow_amount = -abs(amount)
        if new_transaction.amount != outflow_amount:
            account.balance += (outflow_amount - new_transaction.amount)
            new_transaction.amount = outflow_amount

    dest_account = _resolve_destination_account(user_token, contractor_obj)
    if not dest_account or dest_account.id == account.id:
        return

    db.session.flush()  # nadaj ID nowej transakcji, by móc powiązać drugą nogę

    # Kontrahent reprezentujący konto źródłowe (widoczny na transakcji docelowej).
    source_cont_name = f"Moje konto: {account.name}"
    source_contractor = db.session.query(Contractor).filter_by(
        user_token=user_token, linked_account_id=account.id
    ).first()
    if not source_contractor:
        source_contractor = db.session.query(Contractor).filter_by(
            user_token=user_token, name=source_cont_name, is_active=True
        ).first()
    if not source_contractor:
        source_contractor = Contractor(
            name=source_cont_name, user_token=user_token,
            default_category_id=category_id, linked_account_id=account.id
        )
        db.session.add(source_contractor)
        db.session.flush()
    elif source_contractor.linked_account_id is None:
        source_contractor.linked_account_id = account.id

    # 1. Parowanie z istniejącą drugą nogą. Szukamy transakcji o PRZECIWNEJ kwocie na
    # koncie docelowym, jeszcze niepowiązanej, której kontrahent wskazuje NA nasze konto.
    # Zwykły wpływ zewnętrzny nie ma takiego kontrahenta, więc nie zostanie błędnie
    # sparowany. Data z tolerancją — banki księgują obie strony w różnych dniach.
    counter_amount = -new_transaction.amount
    window_start = transaction_date - timedelta(days=_TRANSFER_MATCH_WINDOW_DAYS)
    window_end = transaction_date + timedelta(days=_TRANSFER_MATCH_WINDOW_DAYS)
    counterpart = (
        db.session.query(Transaction)
        .filter(
            Transaction.user_token == user_token,
            Transaction.account_id == dest_account.id,
            Transaction.amount == counter_amount,
            Transaction.contractor_id == source_contractor.id,
            Transaction.linked_transaction_id.is_(None),
            Transaction.id != new_transaction.id,
            Transaction.date >= window_start,
            Transaction.date <= window_end,
        )
        .order_by(Transaction.date, Transaction.id)
        .first()
    )
    if counterpart:
        counterpart.linked_transaction_id = new_transaction.id
        new_transaction.linked_transaction_id = counterpart.id
        return

    # 2. Konto docelowe ma własne wyciągi → jego noga przyjdzie realnie. Nie generujemy
    # lustra; transakcja zostaje niepowiązana jako "do zmapowania".
    if account_has_statement_imports(user_token, dest_account.id):
        logger.info(
            "Przelew wewnętrzny: konto docelowe '%s' ma własne wyciągi — pomijam lustro, "
            "druga noga przyjdzie z importu (transaction_id=%s, user_token=%s)",
            dest_account.name, new_transaction.id, user_token
        )
        return

    # 3. Konto docelowe bez własnych wyciągów — lustro jest jedynym źródłem drugiej strony.
    mirror_tx = Transaction(
        user_token=user_token, account_id=dest_account.id, amount=counter_amount,
        title=title, date=transaction_date, category_id=category_id,
        contractor=source_contractor.name, contractor_id=source_contractor.id,
        linked_transaction_id=new_transaction.id
    )
    dest_account.balance = Decimal(dest_account.balance) + counter_amount
    db.session.add(mirror_tx)
    db.session.flush()
    new_transaction.linked_transaction_id = mirror_tx.id

    # Usuń oczekujący wiersz stagingu odpowiadający TEJ stronie wpływu — ale tylko
    # jeśli jego proponowany kontrahent to lustro naszego konta źródłowego. Dzięki
    # temu nie kasujemy przypadkiem niepowiązanego wpływu o zbieżnej kwocie i dacie.
    matching_staging = db.session.query(TransactionStaging).filter_by(
        user_token=user_token, account_id=dest_account.id, amount=counter_amount,
        date=transaction_date, status='pending', proposed_contractor_id=source_contractor.id
    ).first()
    if matching_staging:
        db.session.delete(matching_staging)

def reconcile_account_balance(user_token: str, account_id: int, new_balance: Decimal, comment: Optional[str] = None) -> Transaction:
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
            contractor="-",
            comment=comment or None
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

    result = {
        'date': tx_date,
        'contractor': contractor,
        'title': title,
        'amount': amount,
        'counterparty_account': counterparty_account
    }

    src_col = key_map.get('source_account')
    if src_col and src_col in header_map:
        try:
            result['source_account'] = parts[header_map[src_col]].strip() or None
        except IndexError:
            result['source_account'] = None

    return result

def parse_ing_csv(file_content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """
    Parsuje plik CSV z ING.

    Plik wielokontowy (ma sekcję 'Wybrane rachunki' i kolumnę 'Konto'):
      — automatycznie wykrywa konto źródłowe każdej transakcji na podstawie kolumny 'Konto'.
      — transakcje z kont nieznanych aplikacji (brak account_number) są pomijane.

    Plik jednokontowy: wszystkie transakcje trafiają na main_account_id.

    Zwraca słownik:
        transactions  — lista sparsowanych transakcji z ustawionym account_id
        csv_accounts  — lista kont z nagłówka CSV [{csv_name, iban, account_id, account_name, matched}]
        skipped_count — liczba transakcji pominiętych z powodu nierozpoznanego konta
    """
    lines = file_content.strip().splitlines()

    # 1. Parsuj sekcję "Wybrane rachunki" — nazwy i numery IBAN kont w pliku
    csv_accounts_entries: list[tuple[str, str]] = []  # (clean_name, normalized_iban)
    in_accounts_section = False
    for line in lines:
        if 'Wybrane rachunki' in line:
            in_accounts_section = True
            continue
        if in_accounts_section:
            if not line.strip():
                in_accounts_section = False
                continue
            try:
                parts = next(csv.reader(io.StringIO(line), delimiter=';'))
                parts = [p.strip().strip('"') for p in parts]
                # parts[0] = nazwa konta (np. "Smart Saver (PLN)"), parts[2] = IBAN
                if len(parts) >= 3 and parts[2].strip():
                    clean_name = re.sub(r'\s*\([^)]*\)\s*$', '', parts[0]).strip()
                    iban = _normalize_acc_num(parts[2])
                    if iban:
                        csv_accounts_entries.append((clean_name, iban))
            except (StopIteration, IndexError):
                pass

    # Zbuduj słownik (pierwszy wpis wygrywa przy duplikatach nazw) i zbiór wszystkich IBAN
    csv_accounts_raw: dict[str, str] = {}
    csv_ibans_set: set[str] = set()
    for name, iban in csv_accounts_entries:
        if name not in csv_accounts_raw:
            csv_accounts_raw[name] = iban
        csv_ibans_set.add(iban)

    # 2. Dopasuj konta z CSV do kont w bazie danych (po numerze IBAN)
    db_accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
    iban_to_account = {_normalize_acc_num(a.account_number): a for a in db_accounts if a.account_number}

    csv_accounts_info: list[dict] = []
    csv_name_to_account_id: dict[str, Optional[int]] = {}

    for csv_name, iban in csv_accounts_entries:
        db_acc = iban_to_account.get(iban)
        csv_accounts_info.append({
            'csv_name': csv_name,
            'iban': iban,
            'account_id': db_acc.id if db_acc else None,
            'account_name': db_acc.name if db_acc else None,
            'matched': db_acc is not None,
        })
        # Przy duplikatach nazw zachowujemy pierwsze dopasowanie;
        # reszta jest obsługiwana przez fallback po nazwie konta w DB.
        if csv_name not in csv_name_to_account_id:
            csv_name_to_account_id[csv_name] = db_acc.id if db_acc else None

    # Fallback: własne nazwy kont z aplikacji (np. "Fundusz remontowy", "Wakacje").
    # ING wyświetla je w kolumnie "Konto", lecz w "Wybrane rachunki" używa nazw produktów
    # (np. "Otwarte Konto Oszczędnościowe"). Dopasowujemy case-insensitive po nazwie w DB.
    db_name_to_account_id: dict[str, int] = {
        acc.name.lower(): acc.id
        for acc in db_accounts
        if acc.account_number and _normalize_acc_num(acc.account_number) in csv_ibans_set
    }

    # 3. Znajdź nagłówek transakcji i zbierz wiersze danych
    header_map: dict[str, int] = {}
    tx_lines: list[str] = []
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

    # Tryb wielokontowy: plik zawiera sekcję "Wybrane rachunki" ORAZ kolumnę "Konto"
    is_multi_account = 'Konto' in header_map and bool(csv_accounts_raw)

    key_map = {
        'date': 'Data transakcji',
        'contractor': 'Dane kontrahenta',
        'title': 'Tytuł',
        'counterparty_account': 'Nr rachunku',
        'source_account': 'Konto' if is_multi_account else None,
        'amount': next((k for k in ['Kwota transakcji (waluta rachunku)', 'Kwota transakcji'] if k in header_map), None)
    }
    if not key_map['amount']:
        raise ValueError("Nie znaleziono kolumny z kwotą transakcji ('Kwota transakcji' lub 'Kwota transakcji (waluta rachunku)').")

    if not is_multi_account and main_account_id is None:
        raise ValueError("Plik CSV zawiera jedno konto — proszę wybrać konto docelowe przed importem.")

    # 4. Parsuj wiersze transakcji i przypisz właściwe account_id
    transactions: list[dict] = []
    skipped_count = 0

    for line in tx_lines:
        try:
            parsed_row = parse_ing_csv_row(line, header_map, key_map)
            if parsed_row is None:
                continue

            if is_multi_account:
                konto_raw = parsed_row.pop('source_account', None) or ''
                konto_clean = re.sub(r'\s*\([^)]*\)\s*$', '', konto_raw).strip()

                matched_id: Optional[int] = None
                in_csv_accounts = False

                # 1. Dopasowanie po nazwie produktowej z "Wybrane rachunki"
                for lookup_key in [konto_raw, konto_clean]:
                    if lookup_key in csv_name_to_account_id:
                        in_csv_accounts = True
                        matched_id = csv_name_to_account_id[lookup_key]
                        break

                # 2. Fallback: własna nazwa konta w aplikacji (case-insensitive)
                if not in_csv_accounts:
                    fallback_id = db_name_to_account_id.get(konto_clean.lower())
                    if fallback_id is not None:
                        in_csv_accounts = True
                        matched_id = fallback_id

                if not in_csv_accounts:
                    # Podkonto / cel oszczędnościowy (np. "iPad 3k") — pomiń
                    skipped_count += 1
                    continue
                if matched_id is None:
                    # Konto z CSV nie istnieje w aplikacji — pomiń
                    skipped_count += 1
                    continue

                # Pomiń stronę "wpływu" (+) przelewu wewnętrznego między śledzonymi kontami.
                # Lustro zostanie automatycznie utworzone przy zatwierdzaniu strony "wypływu" (-).
                counterparty_iban = _normalize_acc_num(parsed_row.get('counterparty_account') or '')
                if (parsed_row['amount'] > 0
                        and counterparty_iban
                        and counterparty_iban in csv_ibans_set
                        and counterparty_iban in iban_to_account):
                    skipped_count += 1
                    continue

                parsed_row['account_id'] = matched_id
            else:
                parsed_row['account_id'] = main_account_id

            transactions.append(parsed_row)
        except (ValueError, StopIteration, IndexError) as e:
            if line.strip() and line.strip()[0].isdigit():
                logger.warning("Odrzucono wiersz CSV przy imporcie (user_token=%s): %s | powód: %s", user_token, line, e)
            continue

    logger.info(
        "Import CSV zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': csv_accounts_info,
        'skipped_count': skipped_count,
    }

# Numer rachunku kontrahenta w mBanku to ciąg dokładnie 26 cyfr (NRB bez prefiksu PL),
# zaszyty w blobie opisu operacji. (?<!\d)/(?!\d) zapobiega złapaniu fragmentu dłuższego ciągu.
_MBANK_ACCOUNT_RE = re.compile(r'(?<!\d)\d{26}(?!\d)')

def parse_mbank_csv(file_content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """
    Parsuje plik CSV z mBanku (jednokontowy — jeden rachunek na plik).

    Wszystkie transakcje trafiają na main_account_id (wybrane przez użytkownika).
    Format różni się od ING: śmieciowy nagłówek (dane banku, klient, okres, saldo),
    kolumny '#Data operacji;#Opis operacji;#Rachunek;#Kategoria;#Kwota', kwota
    z sufiksem ' PLN' i przecinkiem dziesiętnym, brak osobnej kolumny kontrahenta
    (opis to jeden blob), numer konta kontrahenta zaszyty w opisie jako ciąg 26 cyfr.

    Zwraca ten sam kształt co parse_ing_csv (transactions/csv_accounts/skipped_count),
    dzięki czemu dalszy przepływ (save_transactions_to_staging) jest bank-agnostyczny.
    """
    if main_account_id is None:
        raise ValueError("Plik CSV z mBanku dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

    lines = file_content.splitlines()

    # Nagłówek transakcji: pierwsza linia zaczynająca się od '#Data operacji'.
    header_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith('#Data operacji'):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Nie znaleziono nagłówka transakcji ('#Data operacji') w pliku CSV z mBanku.")

    header_cells = next(csv.reader(io.StringIO(lines[header_idx]), delimiter=';'))
    header_map = {cell.strip().lstrip('#').strip(): idx for idx, cell in enumerate(header_cells)}
    try:
        date_col = header_map['Data operacji']
        desc_col = header_map['Opis operacji']
        amount_col = header_map['Kwota']
    except KeyError as e:
        raise ValueError(f"Brak oczekiwanej kolumny w pliku CSV z mBanku: {e}")

    transactions: list[dict] = []
    skipped_count = 0

    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        try:
            parts = next(csv.reader(io.StringIO(line), delimiter=';'))
        except StopIteration:
            continue
        # Wiersz transakcji zaczyna się od daty (cyfra) — pomijamy stopki/śmieci.
        if date_col >= len(parts) or not parts[date_col].strip()[:1].isdigit():
            continue

        date_str = parts[date_col].strip()
        raw_desc = parts[desc_col].strip() if desc_col < len(parts) else ''
        amount_str = parts[amount_col].strip() if amount_col < len(parts) else ''

        # Kwota: usuń sufiks 'PLN', spacje tysięczne (zwykłe i twarde), przecinek → kropka.
        amount_clean = (amount_str
                        .replace('PLN', '')
                        .replace('\xa0', '')
                        .replace(' ', '')
                        .replace(',', '.'))
        if not amount_clean:
            continue
        try:
            amount = Decimal(amount_clean)
        except InvalidOperation:
            logger.warning("Odrzucono wiersz mBank — nieprawidłowa kwota '%s' (user_token=%s)", amount_str, user_token)
            skipped_count += 1
            continue

        try:
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                tx_date = datetime.strptime(date_str, '%d.%m.%Y').date()
            except ValueError:
                logger.warning("Odrzucono wiersz mBank — nieznany format daty '%s' (user_token=%s)", date_str, user_token)
                skipped_count += 1
                continue

        # Opis mBanku wypełniony jest wieloma spacjami — zwijamy do pojedynczych, by tytuł był czytelny.
        title = re.sub(r'\s+', ' ', raw_desc).strip()

        acc_match = _MBANK_ACCOUNT_RE.search(raw_desc)
        counterparty_account = acc_match.group(0) if acc_match else None

        transactions.append({
            'date': tx_date,
            'contractor': None,
            'title': title,
            'amount': amount,
            'counterparty_account': counterparty_account,
            'account_id': main_account_id,
        })

    logger.info(
        "Import CSV mBank zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': [],
        'skipped_count': skipped_count,
    }

def analyze_transaction_data(
    title: str,
    raw_contractor: Optional[str],
    user_token: str,
    counterparty_account: Optional[str] = None,
    accounts: Optional[list] = None,
    contractors: Optional[list] = None
) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Analizuje dane transakcji i próbuje dopasować kontrahenta ze słownika.
    Zwraca (category_id, contractor_id, suggested_name).
    suggested_name jest ustawiony tylko gdy nie znaleziono dopasowania.

    accounts / contractors można podać z zewnątrz (wczytane raz przed pętlą importu),
    aby uniknąć zapytania do bazy o pełny słownik przy każdym wierszu (problem N+1).
    """
    # 1. Sprawdzenie przelewu wewnętrznego (po numerze konta)
    if counterparty_account:
        norm_csv_acc = _normalize_acc_num(counterparty_account)
        if norm_csv_acc:
            if accounts is None:
                accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
            for acc in accounts:
                if acc.account_number and _normalize_acc_num(acc.account_number) == norm_csv_acc:
                    transfer_cat = db.session.query(Category).filter_by(name="Przelew wewnętrzny", is_active=True).first()
                    if not transfer_cat:
                        transfer_cat = Category(name="Przelew wewnętrzny", type="transfer")
                        db.session.add(transfer_cat)
                        db.session.flush()
                    transfer_cont = db.session.query(Contractor).filter_by(
                        user_token=user_token, linked_account_id=acc.id
                    ).first()
                    if not transfer_cont:
                        cont_name = f"Moje konto: {acc.name}"
                        transfer_cont = Contractor(
                            name=cont_name, user_token=user_token,
                            default_category_id=transfer_cat.id, linked_account_id=acc.id
                        )
                        db.session.add(transfer_cont)
                        db.session.flush()
                    return transfer_cat.id, transfer_cont.id, None

    # 2. Dopasowanie po nazwie i regułach mapowania
    if contractors is None:
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

def _existing_import_keys(user_token: str) -> set:
    """Zbiera klucze (data, kwota, tytuł, konto) już istniejących transakcji i wierszy
    stagingu użytkownika — do wykrywania duplikatów przy ponownym wgraniu tego samego pliku."""
    keys: set = set()
    for tx in db.session.query(
        Transaction.date, Transaction.amount, Transaction.title, Transaction.account_id
    ).filter(Transaction.user_token == user_token).all():
        keys.add((tx.date, tx.amount, tx.title, tx.account_id))
    for stg in db.session.query(
        TransactionStaging.date, TransactionStaging.amount,
        TransactionStaging.title, TransactionStaging.account_id
    ).filter(TransactionStaging.user_token == user_token, TransactionStaging.status == 'pending').all():
        keys.add((stg.date, stg.amount, stg.title, stg.account_id))
    return keys


def save_transactions_to_staging(
    parsed_transactions: list[dict],
    user_token: Optional[str] = None
) -> list[TransactionStaging]:
    """Zapisuje sparsowaną listę transakcji do tabeli tymczasowej (stagingowej).

    Pomija wiersze będące duplikatami transakcji lub oczekujących wierszy stagingu
    (ta sama data, kwota, tytuł i konto), aby ponowne wgranie tego samego wyciągu
    nie tworzyło podwójnych zapisów.
    """
    try:
        # Wczytaj słowniki RAZ — analyze_transaction_data operuje na nich w pamięci
        # zamiast odpytywać bazę przy każdym wierszu (unikamy N+1).
        accounts = contractors = None
        seen_keys: set = set()
        if user_token:
            accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
            contractors = db.session.query(Contractor).filter_by(user_token=user_token, is_active=True).all()
            seen_keys = _existing_import_keys(user_token)

        staging_records = []
        skipped_duplicates = 0
        for tx_data in parsed_transactions:
            key = (tx_data['date'], tx_data['amount'], tx_data['title'], tx_data.get('account_id'))
            if user_token and key in seen_keys:
                skipped_duplicates += 1
                continue
            seen_keys.add(key)

            prop_cat_id, prop_contractor_id, suggested_name = None, None, None
            if user_token:
                prop_cat_id, prop_contractor_id, suggested_name = analyze_transaction_data(
                    title=tx_data['title'],
                    raw_contractor=tx_data.get('contractor'),
                    user_token=user_token,
                    counterparty_account=tx_data.get('counterparty_account'),
                    accounts=accounts,
                    contractors=contractors
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
        logger.info(
            "Zapisano %d transakcji do stagingu (user_token=%s, pominięto duplikatów: %d)",
            len(staging_records), user_token, skipped_duplicates
        )
        return staging_records
    except Exception as e:
        db.session.rollback()
        logger.error("Błąd zapisu transakcji do stagingu (user_token=%s): %s", user_token, e)
        raise ValueError(str(e))

def reanalyze_all_staging(user_token: str) -> int:
    """Ponownie uruchamia autokategoryzację na wszystkich pending rekordach stagingu."""
    try:
        accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
        contractors = db.session.query(Contractor).filter_by(user_token=user_token, is_active=True).all()
        rows = db.session.query(TransactionStaging).filter_by(user_token=user_token, status='pending').all()
        for row in rows:
            cat_id, cont_id, suggested = analyze_transaction_data(
                row.title, row.contractor, user_token,
                accounts=accounts, contractors=contractors
            )
            row.proposed_category_id = cat_id
            row.proposed_contractor_id = cont_id
            row.suggested_contractor_name = suggested
        db.session.commit()
        return len(rows)
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))


def clear_pending_staging(user_token: str) -> int:
    """Usuwa wszystkie oczekujące rekordy stagingu dla użytkownika."""
    try:
        deleted = db.session.query(TransactionStaging).filter_by(user_token=user_token, status='pending').delete()
        db.session.commit()
        return deleted
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))


def accept_staging_contractor(user_token: str, stg_id: int, name: str) -> dict:
    """Tworzy lub wyszukuje kontrahenta po nazwie i przypisuje go do rekordu stagingu."""
    try:
        stg_tx = db.session.query(TransactionStaging).filter_by(id=stg_id, user_token=user_token, status='pending').first()
        if not stg_tx:
            raise ValueError('Nie znaleziono transakcji.')

        cont = db.session.query(Contractor).filter_by(user_token=user_token, name=name, is_active=True).first()
        if not cont:
            cont = Contractor(name=name, mapping_rules=name.lower(), user_token=user_token)
            db.session.add(cont)
            db.session.flush()

        stg_tx.proposed_contractor_id = cont.id
        stg_tx.suggested_contractor_name = None
        db.session.commit()

        return {
            'contractor_id': cont.id,
            'contractor_name': cont.name,
            'mapping_rules': cont.mapping_rules or '',
            'default_category_id': cont.default_category_id,
            'default_category_name': ''
        }
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

        # commit=False → utworzenie transakcji i usunięcie wiersza stagingu są jedną
        # atomową operacją. Bez tego awaria między dwoma commitami zostawiłaby wiersz
        # w stanie 'pending', a ponowne kliknięcie "zatwierdź" zdublowałoby transakcję.
        new_tx = create_transaction(
            user_token=stg_tx.user_token,
            account_id=stg_tx.account_id,
            amount=stg_tx.amount,
            title=stg_tx.title,
            transaction_date=stg_tx.date,
            category_id=category.id,
            contractor=stg_tx.contractor,
            contractor_id=contractor.id,
            commit=False,
            # Dane pochodzą z wyciągu — znak kwoty jest źródłem prawdy i nie wolno
            # wymuszać wypływu (noga wpływu przelewu wewnętrznego musi zostać dodatnia).
            preserve_sign=True
        )
        db.session.delete(stg_tx)
        db.session.commit()
        logger.info(
            "Zatwierdzono transakcję ze stagingu #%s -> transaction #%s (user_token=%s, kwota=%s)",
            stg_id, new_tx.id, user_token, new_tx.amount
        )
        return new_tx
    except Exception as e:
        db.session.rollback()
        logger.error("Błąd zatwierdzania stagingu #%s (user_token=%s): %s", stg_id, user_token, e)
        raise ValueError(str(e))
