"""Jednorazowa migracja historii sald z zewnętrznego arkusza XLSX (#110).

Dwie warstwy, celowo rozdzielone:
- read_xlsx_sheet_rows(): odczyt surowych wierszy z pliku — wyłącznie biblioteka
  standardowa (zipfile + ElementTree), NIE openpyxl. Ten konkretny plik zawiera
  cache tabeli przestawnej, na którym openpyxl 3.x wywala się (TypeError w
  Nested.from_tree — znany problem z pivot cache). Ręczny odczyt XML to omija
  i nie wymaga dodawania openpyxl jako zależności dla jednorazowej migracji.
- reszta modułu: czysta logika na już odczytanych wierszach (list[list]) —
  testowalna bez prawdziwego pliku, syntetycznymi danymi.
"""
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional
from xml.etree import ElementTree as ET

from app import db
from app.models import Account, Transaction
from app.services.budget_service import create_transaction, get_or_create_reconciliation_category

logger = logging.getLogger(__name__)

_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

# Polski numer rachunku bankowego (NRB) to dokładnie 26 cyfr, bez prefiksu kraju.
# Kolumna NRB_ING w źródłowym arkuszu bywa zapisana z wiodącym apostrofem
# (wymuszenie formatu tekstowego w Excelu) i spacją na końcu.
_NRB_RE = re.compile(r'^\d{26}$')


def _col_to_idx(ref: str) -> int:
    letters = ''.join(c for c in ref if c.isalpha())
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - ord('A') + 1)
    return n - 1


def _excel_serial_to_date(value) -> Optional[date]:
    """Konwertuje numer seryjny daty Excela (dni od 1899-12-30) na date."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not (20000 < f < 80000):  # sensowny zakres dat (~1954–2119) — odsiewa liczby-nie-daty
        return None
    return date(1899, 12, 30) + timedelta(days=f)


def clean_nrb(raw: Optional[str]) -> Optional[str]:
    """Czyści i waliduje numer rachunku z kolumny NRB_ING. Zwraca None, jeśli
    wartość nie jest prawdziwym 26-cyfrowym numerem (np. zastępczy identyfikator
    typu '1', '2' dla starych/niepełnych wpisów w słowniku).

    Wartości w źródłowym arkuszu bywają otoczone apostrofem PO OBU stronach
    (np. "'45105010251000009102930329 '") — wymuszenie formatu tekstowego
    w Excelu zapisane dosłownie w komórce, nie tylko jako prefiks."""
    if not raw:
        return None
    cleaned = raw.strip().strip("'").strip()
    return cleaned if _NRB_RE.match(cleaned) else None


def read_xlsx_sheet_rows(path: str, sheet_name: str) -> list[list]:
    """Czyta arkusz o podanej nazwie jako listę wierszy (lista list wartości komórek,
    indeksy kolumn liczone od 0, brakujące komórki jako None)."""
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rid_to_target = {r.get('Id'): r.get('Target') for r in rels}

        sheet_file = None
        for s in wb.find(f'{{{_NS}}}sheets'):
            if s.get('name') == sheet_name:
                rid = s.get(f'{{{_REL_NS}}}id')
                sheet_file = 'xl/' + rid_to_target[rid]
                break
        if sheet_file is None:
            raise ValueError(f"Nie znaleziono arkusza '{sheet_name}' w pliku {path}.")

        shared: list[str] = []
        try:
            sst = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in sst.findall(f'{{{_NS}}}si'):
                shared.append(''.join(t.text or '' for t in si.iter(f'{{{_NS}}}t')))
        except KeyError:
            pass

        root = ET.fromstring(z.read(sheet_file))
        sheet_data = root.find(f'{{{_NS}}}sheetData')
        rows: list[list] = []
        for r in sheet_data.findall(f'{{{_NS}}}row'):
            cells: dict[int, object] = {}
            for c in r.findall(f'{{{_NS}}}c'):
                ci = _col_to_idx(c.get('r'))
                v = c.find(f'{{{_NS}}}v')
                val = v.text if v is not None else None
                if c.get('t') == 's' and val is not None:
                    val = shared[int(val)]
                cells[ci] = val
            width = (max(cells) + 1) if cells else 0
            rows.append([cells.get(i) for i in range(width)])
        return rows


@dataclass
class DictAccount:
    """Wiersz ze słownika kont (arkusz Dictionaries), po filtrze NRB_ING."""
    account_name: str
    nrb: str
    bank_name: Optional[str]
    is_open: bool  # brak close_date = konto wciąż aktywne


def _header_index(header_row: list) -> dict[str, int]:
    """Mapuje nazwę kolumny na PIERWSZY indeks jej wystąpienia. Arkusz Dictionaries
    ma zduplikowaną kolumnę 'account_name' (indeks 0 — prawdziwa nazwa konta;
    dalszy indeks — resztka osobnej, niepowiązanej tabelki dopisanej po prawej
    stronie tego samego arkusza) — bierzemy pierwsze wystąpienie, żeby nie trafić
    przypadkiem w tę drugą, niepowiązaną kolumnę."""
    out: dict[str, int] = {}
    for i, name in enumerate(header_row):
        if name and name not in out:
            out[name] = i
    return out


def parse_dictionaries(rows: list[list]) -> list[DictAccount]:
    """Parsuje arkusz Dictionaries, zwraca TYLKO wiersze z prawdziwym 26-cyfrowym
    numerem rachunku (NRB_ING) — pozostałe (gotówka, konta z zastępczym numerem
    1-7) są poza zakresem tej migracji z decyzji użytkownika."""
    if not rows:
        return []
    header = _header_index(rows[0])
    required = ['account_name', 'NRB_ING', 'bank_name', 'close_date']
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"Arkusz Dictionaries: brak oczekiwanych kolumn: {missing}")

    out = []
    for row in rows[1:]:
        if not row or header['account_name'] >= len(row) or not row[header['account_name']]:
            continue
        nrb_raw = row[header['NRB_ING']] if header['NRB_ING'] < len(row) else None
        nrb = clean_nrb(nrb_raw)
        if not nrb:
            continue
        close_val = row[header['close_date']] if header['close_date'] < len(row) else None
        out.append(DictAccount(
            account_name=row[header['account_name']],
            nrb=nrb,
            bank_name=row[header['bank_name']] if header['bank_name'] < len(row) else None,
            is_open=close_val is None,
        ))
    return out


@dataclass
class MonthlyBalance:
    account_name: str
    balance: Decimal
    period_end: date


def parse_saldo_end_of_month(rows: list[list]) -> list[MonthlyBalance]:
    """Parsuje arkusz SaldoEndOfMonth (format długi: konto·miesiąc·saldo)."""
    if not rows:
        return []
    header = _header_index(rows[0])
    required = ['account_name', 'saldo_eom', 'date']
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"Arkusz SaldoEndOfMonth: brak oczekiwanych kolumn: {missing}")

    out = []
    for row in rows[1:]:
        if not row or header['account_name'] >= len(row) or not row[header['account_name']]:
            continue
        try:
            balance = Decimal(str(row[header['saldo_eom']]))
        except (InvalidOperation, TypeError):
            continue
        period_end = _excel_serial_to_date(row[header['date']] if header['date'] < len(row) else None)
        if period_end is None:
            continue
        out.append(MonthlyBalance(
            account_name=row[header['account_name']],
            balance=balance,
            period_end=period_end,
        ))
    return out


@dataclass
class NrbGroup:
    """Grupa wpisów słownika dzielących jeden fizyczny numer rachunku — do ręcznej
    weryfikacji użytkownika PRZED jakimkolwiek zapisem (nie zgadujemy konsolidacji)."""
    nrb: str
    account_names: list[str]
    open_account_name: Optional[str]  # nazwa wpisu bez close_date, jeśli dokładnie jeden


@dataclass
class MigrationReport:
    """Wynik Fazy A (tylko analiza, zero zapisu do bazy)."""
    matched_to_existing: list[tuple[str, str]] = field(default_factory=list)  # (nazwa w Excelu, nazwa konta w apce)
    missing_in_app: list[DictAccount] = field(default_factory=list)  # są w słowniku, nie ma w apce
    shared_nrb_groups: list[NrbGroup] = field(default_factory=list)  # niejednoznaczne — wymaga decyzji
    excel_names_without_dict_entry: list[str] = field(default_factory=list)  # są salda, brak w słowniku
    account_periods: dict[str, tuple[date, date]] = field(default_factory=dict)  # per nazwa w Excelu


def build_migration_report(
    dict_accounts: list[DictAccount],
    balances: list[MonthlyBalance],
    app_accounts_by_nrb: dict[str, str],  # znormalizowany NRB -> nazwa konta w apce
) -> MigrationReport:
    """Łączy słownik + salda + istniejące konta apki. Nie zapisuje niczego —
    tylko buduje raport do przeglądu przed Fazą B."""
    report = MigrationReport()

    # Grupowanie wpisów słownika po NRB — wykrycie współdzielonych rachunków.
    by_nrb: dict[str, list[DictAccount]] = {}
    for acc in dict_accounts:
        by_nrb.setdefault(acc.nrb, []).append(acc)

    dict_name_to_nrb = {acc.account_name: acc.nrb for acc in dict_accounts}

    for nrb, group in by_nrb.items():
        app_name = app_accounts_by_nrb.get(nrb)
        if len(group) > 1:
            open_entries = [a for a in group if a.is_open]
            report.shared_nrb_groups.append(NrbGroup(
                nrb=nrb,
                account_names=[a.account_name for a in group],
                open_account_name=open_entries[0].account_name if len(open_entries) == 1 else None,
            ))
            continue
        acc = group[0]
        if app_name:
            report.matched_to_existing.append((acc.account_name, app_name))
        else:
            report.missing_in_app.append(acc)

    # Okresy pokryte saldami per nazwa w Excelu + wykrycie sald bez wpisu w słowniku.
    periods: dict[str, list[date]] = {}
    for b in balances:
        periods.setdefault(b.account_name, []).append(b.period_end)
        if b.account_name not in dict_name_to_nrb:
            if b.account_name not in report.excel_names_without_dict_entry:
                report.excel_names_without_dict_entry.append(b.account_name)

    for name, dates in periods.items():
        report.account_periods[name] = (min(dates), max(dates))

    return report


@dataclass
class RebuildEntry:
    """Jeden miesiąc odbudowanej historii: docelowe saldo na koniec miesiąca +
    kwota transakcji "Uzgadnianie salda" potrzebna, by je osiągnąć (różnica
    względem poprzedniego miesiąca — dla pierwszego miesiąca to pełne saldo)."""
    entry_date: date
    balance: Decimal
    delta: Decimal


@dataclass
class AccountRebuildPlan:
    app_account_name: str
    excel_account_names: list[str]  # >1 przy współdzielonym NRB (np. Smart Saver)
    entries: list[RebuildEntry] = field(default_factory=list)


def plan_account_rebuild(
    app_account_name: str, excel_account_names: list[str], balances: list[MonthlyBalance]
) -> AccountRebuildPlan:
    """Buduje chronologiczny plan dla JEDNEGO konta w apce. Gdy excel_account_names
    ma więcej niż jedną nazwę (wspólny fizyczny rachunek pod kilkoma etykietami
    w Excelu — potwierdzone przez użytkownika jako bezpieczne, bez nakładania
    miesięcy), salda ze wszystkich nazw są scalane w jedną chronologiczną oś —
    etykiety z arkusza nie mają znaczenia, liczy się ciągłość fizycznego rachunku."""
    combined = sorted(
        (b for b in balances if b.account_name in excel_account_names),
        key=lambda b: b.period_end,
    )
    entries: list[RebuildEntry] = []
    previous = Decimal('0')
    for b in combined:
        entries.append(RebuildEntry(entry_date=b.period_end, balance=b.balance, delta=b.balance - previous))
        previous = b.balance
    return AccountRebuildPlan(app_account_name=app_account_name, excel_account_names=excel_account_names, entries=entries)


def build_rebuild_plans(
    report: MigrationReport,
    balances: list[MonthlyBalance],
    manual_merges: Optional[dict[str, list[str]]] = None,
) -> list[AccountRebuildPlan]:
    """Buduje plany odbudowy WYŁĄCZNIE dla kont już istniejących w apce
    (report.matched_to_existing) — nic tu nie tworzy nowych kont. manual_merges
    pozwala jawnie potwierdzić grupę współdzielonego NRB (np.
    {'Smart Saver': ['Sluchawki 1200', 'Telefon Ja', 'Robot czyszczący']}),
    nadpisując/uzupełniając automatyczne dopasowania z raportu."""
    manual_merges = manual_merges or {}
    grouped: dict[str, list[str]] = {}
    for excel_name, app_name in report.matched_to_existing:
        grouped.setdefault(app_name, []).append(excel_name)
    for app_name, excel_names in manual_merges.items():
        grouped[app_name] = excel_names

    return [plan_account_rebuild(app_name, excel_names, balances) for app_name, excel_names in grouped.items()]


@dataclass
class RebuildSummary:
    app_account_name: str
    account_id: int
    existing_tx_deleted: int
    new_tx_created: int
    first_date: Optional[date]
    last_date: Optional[date]
    final_balance: Optional[Decimal]


def execute_account_rebuild(
    user_token: str, account_id: int, plan: AccountRebuildPlan, dry_run: bool = True
) -> RebuildSummary:
    """Usuwa WSZYSTKIE istniejące transakcje danego konta i odtwarza historię
    z planu jako miesięczne transakcje "Uzgadnianie salda". Kategorie i
    kontrahenci NIE są ruszane — tylko transakcje tego jednego konta.

    dry_run=True (domyślnie): nic nie zapisuje, tylko liczy i zwraca podsumowanie.
    Nie wykonuje własnego commit — woła je kod wywołujący (jedna atomowa
    operacja na wszystkie konta naraz, patrz CLI).

    ŚWIADOMY WYJĄTEK od reguły "usunięte transakcje trafiają do TransactionArchive":
    kasujemy tu twardo, bez wpisu w archiwum. Archiwum służy audytowi decyzji
    użytkownika, a to jest jednorazowa migracja (#110) odtwarzająca historię konta
    od zera — zarchiwizowanie setek wierszy zaśmieciłoby audyt danymi, które z
    definicji mają zniknąć. Zabezpieczenie: domyślny dry_run i jawna flaga
    --execute w CLI."""
    existing = db.session.query(Transaction).filter_by(account_id=account_id, user_token=user_token).all()

    summary = RebuildSummary(
        app_account_name=plan.app_account_name,
        account_id=account_id,
        existing_tx_deleted=len(existing),
        new_tx_created=len(plan.entries),
        first_date=plan.entries[0].entry_date if plan.entries else None,
        last_date=plan.entries[-1].entry_date if plan.entries else None,
        final_balance=plan.entries[-1].balance if plan.entries else None,
    )
    if dry_run:
        return summary

    for tx in existing:
        db.session.delete(tx)
    db.session.flush()

    account = db.session.query(Account).filter_by(id=account_id, user_token=user_token).first()
    if not account:
        raise ValueError(f"Konto o ID {account_id} nie istnieje lub brak uprawnień.")
    account.balance = Decimal('0')
    db.session.flush()

    category = get_or_create_reconciliation_category()
    for entry in plan.entries:
        create_transaction(
            user_token=user_token, account_id=account_id, amount=entry.delta,
            title="Uzgadnianie salda", transaction_date=entry.entry_date,
            category_id=category.id, contractor="-",
            comment="Migracja historii z arkusza XLSX (#110)",
            commit=False,
            origin='excel',
        )

    return summary
