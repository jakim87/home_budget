from decimal import Decimal
from datetime import date

# TDD: Faza RED - importujemy funkcję, która jeszcze nie istnieje
from app.services.budget_service import parse_ing_csv_row, parse_ing_csv

def test_parse_ing_valid_income_row():
    """Testuje poprawne parsowanie pojedynczego wiersza CSV z przychodem (ING)."""
    # Przykładowy wiersz - wyciągnięty z rzeczywistego pliku ING
    # Prawdziwa struktura: Data;Data;Kontrahent;Tytuł;Konto;Bank;Szczegóły;NrTx;Kwota;Waluta
    row_data = "2023-10-25;2023-10-25;Pracodawca Sp. z o.o.;Wypłata za październik;;Bank;;;12500,50;PLN"
    
    parsed = parse_ing_csv_row(row_data)
    
    assert parsed['date'] == date(2023, 10, 25)
    assert parsed['title'] == "Wypłata za październik"
    assert parsed['amount'] == Decimal('12500.50')
    assert parsed['contractor'] == "Pracodawca Sp. z o.o."

def test_parse_ing_valid_expense_row():
    """Testuje parsowanie wydatku (kwota ujemna) bez podanego kontrahenta."""
    # Przykładowy wiersz - np. opłata za kartę
    row_data = "2023-10-28;2023-10-28;;Opłata za kartę miesięczna;;Bank;;;-7,00;PLN"
    
    parsed = parse_ing_csv_row(row_data)
    
    assert parsed['date'] == date(2023, 10, 28)
    assert parsed['title'] == "Opłata za kartę miesięczna"
    assert parsed['amount'] == Decimal('-7.00')
    # Oczekujemy None jeśli pole kontrahenta było puste
    assert parsed['contractor'] is None

def test_parse_ing_skipped_block_row():
    """Testuje celowe pomijanie nierozliczonej płatności kartą (blokady)."""
    # Kwota transakcji (index 8) jest pusta, kwota blokady znajduje się gdzie indziej.
    row_data = '2026-05-16;;" ALDI SP. Z O.O.";" Płatność kartą";;;Bank;;;"";;;-54,75;PLN;;;4066,32;PLN;;;;;'
    parsed = parse_ing_csv_row(row_data)
    assert parsed is None

def test_parse_ing_csv_content():
    """Testuje parsowanie całego pliku CSV z pominięciem nagłówków oraz szumu."""
    csv_content = """Data transakcji;Data księgowania;Dane kontrahenta;Tytuł;Konto;Bank;Szczegóły;NrTx;Kwota;Waluta
2023-10-25;2023-10-25;Pracodawca;Wypłata;;Bank;;;12500,50;PLN
2023-10-28;2023-10-28;;Opłata za kartę;;Bank;;;-7,00;PLN
Puste dane i nieistotne metadane na końcu pliku wgrywanego przez ING
"""
    parsed_list = parse_ing_csv(csv_content)
    
    assert len(parsed_list) == 2
    assert parsed_list[0]['title'] == "Wypłata"
    assert parsed_list[0]['amount'] == Decimal('12500.50')
    assert parsed_list[1]['title'] == "Opłata za kartę"
    assert parsed_list[1]['amount'] == Decimal('-7.00')