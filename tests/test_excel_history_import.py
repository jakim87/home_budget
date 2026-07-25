"""Migracja historii sald z Excela (#110) — Faza A: parsowanie i raport, zero zapisu.

Dane w testach są w pełni syntetyczne (zmyślone nazwy, numery, kwoty) — nie
pochodzą z prawdziwego pliku użytkownika, który nigdy nie trafia do repo.
"""
import io
import zipfile
from datetime import date
from decimal import Decimal

from app.services.excel_history_import_service import (
    DictAccount,
    MonthlyBalance,
    build_migration_report,
    clean_nrb,
    parse_dictionaries,
    parse_saldo_end_of_month,
    read_xlsx_sheet_rows,
)


# --- clean_nrb ---

def test_clean_nrb_strips_leading_quote_and_whitespace():
    assert clean_nrb("'11111111111111111111111111 ") == "11111111111111111111111111"


def test_clean_nrb_strips_apostrophe_on_both_sides():
    """Regresja: prawdziwe wartości w arkuszu mają apostrof PO OBU stronach
    (np. "'45105010251000009102930329 '"), nie tylko na początku."""
    assert clean_nrb("'22222222222222222222222222 '") == "22222222222222222222222222"


def test_clean_nrb_rejects_placeholder_short_numbers():
    """Stare wpisy słownika mają zastępczy numer typu '1', '2' zamiast prawdziwego NRB."""
    assert clean_nrb("'3 '") is None
    assert clean_nrb("7") is None


def test_clean_nrb_rejects_none_and_empty():
    assert clean_nrb(None) is None
    assert clean_nrb("") is None


# --- parse_dictionaries ---

DICT_HEADER = ['account_name', 'account_raport_name', 'bank_name', 'NRB', 'NRB_short',
              'NRB_ING', 'interest_rate', 'account_type', 'owner', 'co_owner',
              'open_date', 'close_date']


def test_parse_dictionaries_filters_to_real_nrb_only():
    rows = [
        DICT_HEADER,
        ['Konto Testowe', 'ROR - Test', 'TestBank', '11 1111 1111 1111 1111 1111 1111',
         '1111', "'11111111111111111111111111 ", '0', 'ROR', 'Jan', None, 42370, None],
        ['Portfel Gotówka', 'GOT', 'Gotówka', None, None, "' '", None, 'GOT', 'Jan', None, 42370, None],
        ['Stare Konto', 'Inv', 'TestBank2', '3', '3', "'3 '", '0', 'Inv', 'Jan', None, 42370, None],
    ]
    result = parse_dictionaries(rows)
    assert len(result) == 1
    assert result[0].account_name == 'Konto Testowe'
    assert result[0].nrb == '11111111111111111111111111'
    assert result[0].is_open is True


def test_parse_dictionaries_marks_closed_account():
    rows = [
        DICT_HEADER,
        ['Zamknięte', 'KO', 'TestBank', 'x', 'x', "'22222222222222222222222222 ",
         '0', 'KO', 'Jan', None, 42370, 43009],
    ]
    result = parse_dictionaries(rows)
    assert result[0].is_open is False


def test_parse_dictionaries_uses_first_account_name_column_not_last():
    """Regresja: arkusz Dictionaries ma zduplikowaną kolumnę 'account_name'
    (prawdziwa nazwa konta na początku, niepowiązana tabelka dalej w wierszu).
    Wcześniejszy bug: dict comprehension nadpisywał się na OSTATNIE wystąpienie,
    więc krótsze wiersze (bez tej drugiej kolumny) były cicho odrzucane."""
    header_with_dup = DICT_HEADER + [None, 'account_cashdroid', 'account_name']
    short_row = ['Konto Realne', 'ROR - Realne', 'TestBank', 'x', 'x',
                "'11111111111111111111111111 ", '0', 'ROR', 'Jan', None, 42370, None]
    # Wiersz krótszy niż pozycja drugiej kolumny 'account_name' (indeks 14) —
    # dokładnie przypadek, który wcześniej gubił poprawne konta.
    result = parse_dictionaries([header_with_dup, short_row])
    assert len(result) == 1
    assert result[0].account_name == 'Konto Realne'


def test_parse_dictionaries_missing_column_raises():
    bad_header = ['account_name', 'bank_name']  # brak NRB_ING itd.
    try:
        parse_dictionaries([bad_header, ['x', 'y']])
        assert False, "powinien rzucić ValueError"
    except ValueError as e:
        assert 'NRB_ING' in str(e)


# --- parse_saldo_end_of_month ---

SALDO_HEADER = ['bank', 'account_name', 'account_raport_name', 'interest_rate',
                'account_type', 'saldo_eom', 'date', 'months_diff', 'Klucz',
                'Poprzedni_mc', 'Zmiana', 'Avg last 6']


def test_parse_saldo_end_of_month_reads_balance_and_date():
    rows = [
        SALDO_HEADER,
        ['TestBank', 'Konto Testowe', 'ROR - Test', '0', 'ROR', '1234.56', 42338,
         '0', 'K1', '0', '1234.56', '1234.56'],
    ]
    result = parse_saldo_end_of_month(rows)
    assert len(result) == 1
    assert result[0].account_name == 'Konto Testowe'
    assert result[0].balance == Decimal('1234.56')
    assert result[0].period_end == date(2015, 11, 30)


def test_parse_saldo_end_of_month_skips_rows_with_bad_balance():
    rows = [SALDO_HEADER, ['TestBank', 'Konto X', 'r', '0', 'ROR', 'nie-liczba', 42338, '0', 'K', '0', '0', '0']]
    assert parse_saldo_end_of_month(rows) == []


# --- build_migration_report ---

def test_report_matches_account_by_nrb_to_existing_app_account():
    dict_accounts = [DictAccount('Konto z Lwem', '11111111111111111111111111', 'ING', True)]
    balances = [MonthlyBalance('Konto z Lwem', Decimal('100.00'), date(2020, 1, 31))]
    app_by_nrb = {'11111111111111111111111111': 'Moje ING'}

    report = build_migration_report(dict_accounts, balances, app_by_nrb)

    assert report.matched_to_existing == [('Konto z Lwem', 'Moje ING')]
    assert report.missing_in_app == []
    assert report.shared_nrb_groups == []


def test_report_flags_account_missing_in_app():
    dict_accounts = [DictAccount('Fundusz X', '22222222222222222222222222', 'ING', True)]
    report = build_migration_report(dict_accounts, [], {})

    assert report.missing_in_app == dict_accounts
    assert report.matched_to_existing == []


def test_report_flags_shared_nrb_as_ambiguous_not_auto_consolidated():
    """Kilka wpisów słownika pod jednym IBAN (np. przemianowane sub-cele) trafia
    do shared_nrb_groups do RĘCZNEJ decyzji — nigdy nie jest cicho konsolidowane."""
    dict_accounts = [
        DictAccount('Cel A (zamknięty)', '33333333333333333333333333', 'ING', False),
        DictAccount('Cel B (aktualny)', '33333333333333333333333333', 'ING', True),
    ]
    report = build_migration_report(dict_accounts, [], {})

    assert len(report.shared_nrb_groups) == 1
    group = report.shared_nrb_groups[0]
    assert set(group.account_names) == {'Cel A (zamknięty)', 'Cel B (aktualny)'}
    assert group.open_account_name == 'Cel B (aktualny)'
    assert report.matched_to_existing == []
    assert report.missing_in_app == []


def test_report_flags_shared_nrb_with_multiple_open_entries_as_fully_ambiguous():
    """Gdy więcej niż jeden wpis w grupie jest 'otwarty', nawet nazwa 'aktualna'
    nie jest oczywista — open_account_name zostaje None, wymaga decyzji człowieka."""
    dict_accounts = [
        DictAccount('Cel A', '44444444444444444444444444', 'ING', True),
        DictAccount('Cel B', '44444444444444444444444444', 'ING', True),
    ]
    report = build_migration_report(dict_accounts, [], {})
    assert report.shared_nrb_groups[0].open_account_name is None


def test_report_flags_balance_without_dictionary_entry():
    balances = [MonthlyBalance('Duch z Excela', Decimal('50.00'), date(2019, 5, 31))]
    report = build_migration_report([], balances, {})
    assert report.excel_names_without_dict_entry == ['Duch z Excela']


def test_report_computes_period_range_per_account():
    balances = [
        MonthlyBalance('Konto X', Decimal('10'), date(2018, 1, 31)),
        MonthlyBalance('Konto X', Decimal('20'), date(2020, 6, 30)),
        MonthlyBalance('Konto X', Decimal('15'), date(2019, 3, 31)),
    ]
    report = build_migration_report([], balances, {})
    assert report.account_periods['Konto X'] == (date(2018, 1, 31), date(2020, 6, 30))


# --- read_xlsx_sheet_rows (integracyjny, na syntetycznym mini-xlsx) ---

def _make_minimal_xlsx(sheet_name: str, rows: list[list[str]]) -> bytes:
    """Buduje minimalny, poprawny plik .xlsx z jednym arkuszem — bez shared strings,
    same inline stringi jako typ 'str' niewspierany; dla prostoty testu wartości
    zapisujemy jako liczby/teksty inline typu 'inlineStr' pominięte — używamy
    prostych wartości liczbowych, bo to wystarcza do zweryfikowania mapowania
    kolumn i wierszy (shared strings są już pokryte testem manualnym na realnym
    pliku, patrz analiza w sesji)."""
    sheet_xml_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, val in enumerate(row):
            col_letter = chr(ord('A') + c_idx)
            cells.append(f'<c r="{col_letter}{r_idx}"><v>{val}</v></c>')
        sheet_xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_xml_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '</Types>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('xl/workbook.xml', workbook_xml)
        z.writestr('xl/_rels/workbook.xml.rels', rels_xml)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)
    return buf.getvalue()


def test_read_xlsx_sheet_rows_reads_numeric_grid(tmp_path):
    xlsx_bytes = _make_minimal_xlsx('DaneTestowe', [['1', '2', '3'], ['4', '5', '6']])
    path = tmp_path / 'synthetic.xlsx'
    path.write_bytes(xlsx_bytes)

    rows = read_xlsx_sheet_rows(str(path), 'DaneTestowe')

    assert rows == [['1', '2', '3'], ['4', '5', '6']]


def test_read_xlsx_sheet_rows_unknown_sheet_raises(tmp_path):
    xlsx_bytes = _make_minimal_xlsx('Istniejący', [['1']])
    path = tmp_path / 'synthetic.xlsx'
    path.write_bytes(xlsx_bytes)

    try:
        read_xlsx_sheet_rows(str(path), 'Nieistniejący')
        assert False, "powinien rzucić ValueError"
    except ValueError as e:
        assert 'Nieistniejący' in str(e)
