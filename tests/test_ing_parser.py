from decimal import Decimal
from datetime import date
import pytest
from app import db
from app.models import User, Account

from app.services.budget_service import parse_ing_csv

@pytest.fixture
def parser_user(app):
    """Przygotowuje użytkownika i konto testowe dla parsera."""
    with app.app_context():
        user = User(username="parser_user", email="parser@user.com", password_hash="a")
        acc1 = Account(user=user, name="KONTO Z LWEM Direct (PLN)", bank_name="ING", account_number="PL10105000997603123456789123")
        acc2 = Account(user=user, name="Smart Saver", bank_name="ING", account_number="PL24105010251000009180015928")
        db.session.add_all([user, acc1, acc2])
        db.session.commit()
        return user.token, {'acc1_id': acc1.id, 'acc2_id': acc2.id}

def test_parse_ing_csv_content(app, parser_user):
    """Testuje parsowanie całego pliku CSV z automatycznym wykrywaniem wielu kont na podstawie ich nazw."""
    user_token, account_ids = parser_user
    csv_content = """
"Wybrane rachunki:";
"KONTO Z LWEM Direct (PLN)";;"10 1050 0099 7603 1234 5678 9123";
"Smart Saver (PLN)";;"24 1050 1025 1000 0091 8001 5928";
"Zastosowane kryteria wyboru";;;;;
"Data transakcji";"Data księgowania";"Dane kontrahenta";"Tytuł";"Nr rachunku";"Nazwa banku";"Szczegóły";"Nr transakcji";"Kwota transakcji (waluta rachunku)";"Waluta";"Konto"
"2023-10-25";"2023-10-25";"Pracodawca";"Wypłata";"";"Bank";"";"";"12500,50";"PLN";"KONTO Z LWEM Direct (PLN)"
"2023-10-28";"2023-10-28";"";"Opłata za kartę";"";"Bank";"";"";"-7,00";"PLN";"KONTO Z LWEM Direct (PLN)"
"2023-10-29";"2023-10-29";"Przelew";"Oszczędności";"";"Bank";"";"";"-100,00";"PLN";"Smart Saver (PLN)"
"""
    with app.app_context():
        parsed_list = parse_ing_csv(csv_content, user_token, account_ids['acc1_id'])

    assert len(parsed_list) == 3
    assert parsed_list[0]['title'] == "Wypłata"
    assert parsed_list[0]['amount'] == Decimal('12500.50')
    assert parsed_list[0]['account_id'] == account_ids['acc1_id']
    assert parsed_list[1]['title'] == "Opłata za kartę"
    assert parsed_list[1]['amount'] == Decimal('-7.00')
    assert parsed_list[1]['account_id'] == account_ids['acc1_id']
    assert parsed_list[2]['title'] == "Oszczędności"
    assert parsed_list[2]['amount'] == Decimal('-100.00')
    assert parsed_list[2]['account_id'] == account_ids['acc1_id']
