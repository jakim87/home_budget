import re
from app import db
from app.models import Account, ACCOUNT_TYPES
from decimal import Decimal
from sqlalchemy import func


def _validate_account_type(value):
    """Zwraca znormalizowany typ konta (jeden z ACCOUNT_TYPES) albo None.
    Pusty string traktujemy jak brak typu; nieznany typ to błąd."""
    if value is None or value == '':
        return None
    if value not in ACCOUNT_TYPES:
        raise ValueError(f"Nieznany typ konta: '{value}'. Dozwolone: {', '.join(ACCOUNT_TYPES)}.")
    return value


def _validate_account_number(value):
    """Zwraca numer konta jako 26 cyfr bez spacji, albo None (pole opcjonalne).
    Numer musi mieć poprawną długość i sumę kontrolną mod-97 (jak w IBAN, z
    prefiksem 'PL') — to samo, co bank sprawdza przy realnym przelewie."""
    if value is None:
        return None
    digits = value.replace(' ', '')
    if digits == '':
        return None
    if not re.fullmatch(r'\d{26}', digits):
        raise ValueError("Nieprawidłowy numer rachunku: musi mieć 26 cyfr.")
    numeric = digits[2:] + '2521' + digits[:2]  # PL przeniesione na koniec, P=25 L=21
    if int(numeric) % 97 != 1:
        raise ValueError("Nieprawidłowy numer rachunku: błędna suma kontrolna (sprawdź, czy nie ma literówki).")
    return digits


def resolve_statement_account(user_token, statement_ibans, chosen_account_id=None):
    """Wskazuje konto, którego dotyczy wgrywany wyciąg.

    Zwraca (account_id, dopasowane_konto_albo_None); drugi element jest wypełniony
    tylko wtedy, gdy konto zostało rozpoznane automatycznie (użytkownik go nie wybrał).
    Rozbieżność między wyciągiem a wybranym kontem to ValueError — import na złe konto
    rozjeżdża salda, więc nie zgadujemy.
    """
    from app.services.budget_service import _normalize_acc_num

    accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()

    # Własność chosen_account_id sprawdzana ZAWSZE i jako pierwsza rzecz — niezależnie
    # od statement_ibans. Bez tego, gdy wyciąg nie deklaruje IBAN-u (np. ING CSV
    # jednokontowy), cudze konto przechodziłoby przez tę funkcję bez żadnej kontroli (#127).
    chosen = None
    if chosen_account_id:
        chosen = next((a for a in accounts if a.id == int(chosen_account_id)), None)
        if chosen is None:
            raise ValueError("Wybrane konto nie istnieje, jest nieaktywne lub brak uprawnień.")

    if not statement_ibans:
        return (chosen.id if chosen else chosen_account_id), None

    norm_iban = _normalize_acc_num(statement_ibans[0])
    masked = f"{norm_iban[:2]}...{norm_iban[-4:]}"
    matched = next(
        (a for a in accounts if a.account_number and _normalize_acc_num(a.account_number) == norm_iban),
        None
    )

    if not chosen:
        if matched:
            return matched.id, matched
        raise ValueError(
            f"Wyciąg dotyczy rachunku {masked}, który nie pasuje do żadnego konta w aplikacji. "
            "Dodaj konto z tym numerem rachunku w Słownikach albo wybierz konto ręcznie."
        )

    chosen_num_differs = bool(chosen.account_number
                              and _normalize_acc_num(chosen.account_number) != norm_iban)
    matched_is_other = bool(matched and matched.id != chosen.id)
    if chosen_num_differs or matched_is_other:
        raise ValueError(
            f"Wyciąg dotyczy rachunku {masked}, a wybrano konto '{chosen.name}' o innym numerze. "
            f"{'Rachunek z wyciągu pasuje do konta: ' + matched.name + '. ' if matched else ''}"
            "Wybierz właściwe konto lub pozostaw wybór automatyczny."
        )
    return chosen.id, None


def create_account(user_token, data):
    try:
        account_number = _validate_account_number(data.get('account_number'))
        is_default = data.get('is_default', False)
        account_type = _validate_account_type(data.get('account_type'))
        max_order = db.session.query(func.max(Account.sort_order)).filter_by(user_token=user_token).scalar()
        new_acc = Account(
            name=data['name'],
            bank_name=data.get('bank_name'),
            account_number=account_number,
            balance=Decimal('0'),
            account_type=account_type,
            user_token=user_token,
            owner=data.get('owner') or None,
            co_owner=data.get('co_owner') or None,
            sort_order=(max_order or 0) + 1,
        )
        db.session.add(new_acc)
        db.session.flush()
        if is_default:
            db.session.query(Account).filter(
                Account.user_token == user_token,
                Account.id != new_acc.id
            ).update({'is_default': False})
            new_acc.is_default = True
        db.session.commit()
        return new_acc
    except Exception:
        db.session.rollback()
        raise

def update_account(user_token, a_id, data):
    try:
        acc = db.session.query(Account).filter_by(id=a_id, user_token=user_token).first()
        if not acc:
            raise ValueError('Nie znaleziono konta.')
        acc.name = data.get('name', acc.name)
        acc.bank_name = data.get('bank_name', acc.bank_name)
        if 'account_number' in data:
            acc.account_number = _validate_account_number(data.get('account_number'))
        if 'owner' in data:
            acc.owner = data['owner'] or None
        if 'co_owner' in data:
            acc.co_owner = data['co_owner'] or None
        if 'account_type' in data:
            acc.account_type = _validate_account_type(data['account_type'])
        if data.get('is_default'):
            db.session.query(Account).filter(
                Account.user_token == user_token,
                Account.id != acc.id
            ).update({'is_default': False})
            acc.is_default = True
        db.session.commit()
        return acc
    except Exception:
        db.session.rollback()
        raise

def soft_delete_account(user_token, a_id):
    try:
        acc = db.session.query(Account).filter_by(id=a_id, user_token=user_token).first()
        if not acc:
            raise ValueError('Nie znaleziono konta lub brak uprawnień.')
        acc.is_active = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

def reorder_accounts(user_token, ordered_ids):
    """Zapisuje kolejność wyświetlania kont wg listy ID podanej przez użytkownika (tylko UI, bez wpływu na logikę)."""
    try:
        accounts = db.session.query(Account).filter(
            Account.user_token == user_token,
            Account.id.in_(ordered_ids)
        ).all()
        accounts_by_id = {a.id: a for a in accounts}
        if len(accounts_by_id) != len(ordered_ids):
            raise ValueError('Jedno lub więcej kont nie istnieje lub nie należy do użytkownika.')
        for position, acc_id in enumerate(ordered_ids):
            accounts_by_id[acc_id].sort_order = position
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
