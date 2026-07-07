from decimal import Decimal
from datetime import date
import pytest
from app import db
from app.models import User, Account

from app.services.budget_service import parse_ing_csv

@pytest.fixture
def parser_user(app):
    """Przygotowuje użytkownika i konta testowe dla parsera."""
    with app.app_context():
        user = User(username="parser_user", email="parser@user.com", password_hash="a")
        # acc1: ING nazywa "KONTO Z LWEM Direct", w aplikacji "Moje ING"
        acc1 = Account(user=user, name="Moje ING", bank_name="ING", account_number="PL10105000997603123456789123")
        # acc2: ING nazywa "Smart Saver", w aplikacji też "Smart Saver"
        acc2 = Account(user=user, name="Smart Saver", bank_name="ING", account_number="PL24105010251000009180015928")
        # acc3: ING nazywa "Otwarte Konto Oszczędnościowe", użytkownik zmienił na "Fundusz Remontowy"
        acc3 = Account(user=user, name="Fundusz Remontowy", bank_name="ING", account_number="PL72105010251000009111440914")
        db.session.add_all([user, acc1, acc2, acc3])
        db.session.commit()
        return user.token, {'acc1_id': acc1.id, 'acc2_id': acc2.id, 'acc3_id': acc3.id}

def test_parse_ing_csv_content(app, parser_user):
    """Każda transakcja trafia na właściwe konto — dopasowanie po nazwie ING i po nazwie w DB."""
    user_token, account_ids = parser_user
    csv_content = """
"Wybrane rachunki:";
"KONTO Z LWEM Direct (PLN)";;"10 1050 0099 7603 1234 5678 9123";
"Smart Saver (PLN)";;"24 1050 1025 1000 0091 8001 5928";
"Otwarte Konto Oszczędnościowe (PLN)";;"72 1050 1025 1000 0091 1144 0914";

"Data transakcji";"Data księgowania";"Dane kontrahenta";"Tytuł";"Nr rachunku";"Nazwa banku";"Szczegóły";"Nr transakcji";"Kwota transakcji (waluta rachunku)";"Waluta";"Konto"
"2023-10-25";"2023-10-25";"Pracodawca";"Wypłata";"";"Bank";"";"";"12500,50";"PLN";"KONTO Z LWEM Direct"
"2023-10-28";"2023-10-28";"";"Opłata za kartę";"";"Bank";"";"";"-7,00";"PLN";"KONTO Z LWEM Direct"
"2023-10-29";"2023-10-29";"Przelew";"Oszczędności";"";"Bank";"";"";"-100,00";"PLN";"Smart Saver"
"2023-10-01";"2023-10-01";"ING";"Odsetki";"";"Bank";"";"";"+3,50";"PLN";"Fundusz Remontowy"
"""
    with app.app_context():
        result = parse_ing_csv(csv_content, user_token)

    transactions = result['transactions']
    assert len(transactions) == 4
    assert transactions[0]['title'] == "Wypłata"
    assert transactions[0]['account_id'] == account_ids['acc1_id']
    assert transactions[1]['title'] == "Opłata za kartę"
    assert transactions[1]['account_id'] == account_ids['acc1_id']
    assert transactions[2]['title'] == "Oszczędności"
    assert transactions[2]['account_id'] == account_ids['acc2_id']
    # "Fundusz Remontowy" to własna nazwa konta — dopasowanie przez fallback DB
    assert transactions[3]['title'] == "Odsetki"
    assert transactions[3]['account_id'] == account_ids['acc3_id']

    assert result['skipped_count'] == 0
    assert len(result['csv_accounts']) == 3


def test_parse_ing_csv_skips_unknown_account(app, parser_user):
    """Podkonto (np. 'iPad 3k') spoza 'Wybrane rachunki' i bez dopasowania DB jest pomijane."""
    user_token, account_ids = parser_user
    csv_content = """
"Wybrane rachunki:";
"KONTO Z LWEM Direct (PLN)";;"10 1050 0099 7603 1234 5678 9123";
"Smart Saver (PLN)";;"24 1050 1025 1000 0091 8001 5928";

"Data transakcji";"Data księgowania";"Dane kontrahenta";"Tytuł";"Nr rachunku";"Nazwa banku";"Szczegóły";"Nr transakcji";"Kwota transakcji (waluta rachunku)";"Waluta";"Konto"
"2023-10-25";"2023-10-25";"Pracodawca";"Wypłata";"";"Bank";"";"";"12500,50";"PLN";"KONTO Z LWEM Direct"
"2023-10-26";"2023-10-26";"";"Cel oszczędnościowy";"";"Bank";"";"";"-50,00";"PLN";"iPad 3k"
"""
    with app.app_context():
        result = parse_ing_csv(csv_content, user_token)

    assert len(result['transactions']) == 1
    assert result['transactions'][0]['title'] == "Wypłata"
    assert result['skipped_count'] == 1


def test_parse_ing_csv_skips_inflow_of_internal_transfer(app, parser_user):
    """Strona wpływu (+) przelewu między śledzonymi kontami jest pomijana — lustro tworzy zatwierdzenie wypływu."""
    user_token, account_ids = parser_user
    # Transfer 500 PLN: Moje ING (10...) → Smart Saver (24...)
    # CSV zawiera obie strony z tym samym Nr transakcji
    csv_content = """
"Wybrane rachunki:";
"KONTO Z LWEM Direct (PLN)";;"10 1050 0099 7603 1234 5678 9123";
"Smart Saver (PLN)";;"24 1050 1025 1000 0091 8001 5928";

"Data transakcji";"Data księgowania";"Dane kontrahenta";"Tytuł";"Nr rachunku";"Nazwa banku";"Szczegóły";"Nr transakcji";"Kwota transakcji (waluta rachunku)";"Waluta";"Konto"
"2023-10-30";"2023-10-30";"Jan";"Oszczędności";"24105010251000009180015928";"ING";"";"TX001";"-500,00";"PLN";"KONTO Z LWEM Direct"
"2023-10-30";"2023-10-30";"Jan";"Oszczędności";"10105000997603123456789123";"ING";"";"TX001";"500,00";"PLN";"Smart Saver"
"""
    with app.app_context():
        result = parse_ing_csv(csv_content, user_token)

    # Tylko wypływ (-500 z Moje ING) powinien być zaimportowany
    assert len(result['transactions']) == 1
    assert result['transactions'][0]['amount'] == Decimal('-500.00')
    assert result['transactions'][0]['account_id'] == account_ids['acc1_id']
    # Wpływ (+500 do Smart Saver) pominięty — lustro stworzy zatwierdzenie wypływu
    assert result['skipped_count'] == 1


def test_parse_ing_csv_single_account_requires_account_id(app, parser_user):
    """Jednokontowy CSV (bez kolumny Konto) wymaga podania main_account_id."""
    user_token, account_ids = parser_user
    csv_content = """
"Wybrane rachunki:";
"KONTO Z LWEM Direct (PLN)";;"10 1050 0099 7603 1234 5678 9123";

"Data transakcji";"Data księgowania";"Dane kontrahenta";"Tytuł";"Nr rachunku";"Kwota transakcji (waluta rachunku)";"Waluta"
"2023-10-25";"2023-10-25";"Pracodawca";"Wpłata";"";"500,00";"PLN"
"""
    with app.app_context():
        result = parse_ing_csv(csv_content, user_token, main_account_id=account_ids['acc1_id'])

    assert len(result['transactions']) == 1
    assert result['transactions'][0]['account_id'] == account_ids['acc1_id']
