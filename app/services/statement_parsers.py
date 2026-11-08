"""Detekcja banku/formatu wyciągu oraz parsery wszystkich obsługiwanych formatów.

Każdy parser zwraca ten sam kształt: {'transactions': [...], 'csv_accounts': [...],
'skipped_count': int} — dzięki temu dalszy przepływ (save_transactions_to_staging,
autokategoryzacja, staging) jest wspólny dla wszystkich banków i formatów.

Dodatkowo parsery zwracają, gdy da się je wyczytać z nagłówka wyciągu:
  'period_start' / 'period_end' — zakres dat wyciągu (pod historię importów
      i wykrywanie nakładających się okresów),
  'statement_ibans' — numery rachunków, których dotyczy plik (pod walidację
      konta i analizę pokrycia przy imporcie wielu plików).
"""
import csv
import io
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from bs4 import BeautifulSoup

from app import db
from app.models import Account, Transaction, TransactionStaging
from app.services.budget_service import _normalize_acc_num

logger = logging.getLogger(__name__)


class BrakKontaError(ValueError):
    """Plik dotyczy jednego konta, nie niesie jego numeru, a konta nie wskazano.

    Osobna klasa, bo strona importu reaguje na nią inaczej niż na resztę błędów:
    pokazuje przy pliku wybór konta i „Wgraj ponownie" (blueprint dokłada needs_account).
    """


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

def build_ing_account_maps(
    account_entries: list[tuple[str, str]], user_token: str
) -> tuple[list[dict], dict[str, Optional[int]], dict[str, int], set[str]]:
    """Dopasowuje etykiety kont ING (z sekcji 'Wybrane rachunki' — wspólnej dla
    CSV i PDF) do kont użytkownika w apce, po numerze rachunku.

    account_entries: lista (etykieta_produktowa, znormalizowany_iban).

    Zwraca (accounts_info, name_to_account_id, db_name_to_account_id, ibans_set):
    - accounts_info: do wyświetlenia w UI po imporcie (jak dotąd 'csv_accounts').
    - name_to_account_id: etykieta -> account_id (pierwsze dopasowanie wygrywa
      przy duplikatach nazw — ING potrafi nazwać kilka różnych kont tą samą
      generyczną etykietą produktową, np. "Otwarte Konto Oszczędnościowe").
    - db_name_to_account_id: fallback po WŁASNEJ nazwie konta w apce
      (case-insensitive) — ING w wierszu transakcji/bloku PDF pokazuje
      przemianowane konto (np. "Wakacje") inaczej niż w nagłówku.
    - ibans_set: wszystkie znormalizowane IBAN-y z pliku, do wykrywania
      przelewów wewnętrznych w obrębie tego samego pliku.
    """
    db_accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).all()
    iban_to_account = {_normalize_acc_num(a.account_number): a for a in db_accounts if a.account_number}

    ibans_set: set[str] = {iban for _, iban in account_entries}
    accounts_info: list[dict] = []
    name_to_account_id: dict[str, Optional[int]] = {}

    for name, iban in account_entries:
        db_acc = iban_to_account.get(iban)
        accounts_info.append({
            'csv_name': name,
            'iban': iban,
            'account_id': db_acc.id if db_acc else None,
            'account_name': db_acc.name if db_acc else None,
            'matched': db_acc is not None,
        })
        # Przy duplikatach nazw zachowujemy pierwsze dopasowanie; reszta jest
        # obsługiwana przez fallback po nazwie konta w DB.
        if name not in name_to_account_id:
            name_to_account_id[name] = db_acc.id if db_acc else None

    db_name_to_account_id: dict[str, int] = {
        acc.name.lower(): acc.id
        for acc in db_accounts
        if acc.account_number and _normalize_acc_num(acc.account_number) in ibans_set
    }
    return accounts_info, name_to_account_id, db_name_to_account_id, ibans_set


def resolve_ing_account_label(
    konto_raw: str,
    name_to_account_id: dict[str, Optional[int]],
    db_name_to_account_id: dict[str, int],
) -> tuple[bool, Optional[int]]:
    """Rozwiązuje etykietę konta (kolumna 'Konto' w CSV albo blok w PDF) na
    account_id, tym samym dwuetapowym algorytmem dla obu formatów:
    1. dopasowanie po nazwie produktowej z 'Wybrane rachunki',
    2. fallback po własnej nazwie konta w apce (case-insensitive).

    Zwraca (rozpoznane_jako_znane_apce_konto, account_id_lub_None). Pierwszy
    element == False oznacza podkonto/cel spoza słownika (np. "iPad 3k") —
    pomijamy, nie zgadujemy. Drugi element None przy pierwszym == True
    oznacza: etykieta jest w pliku, ale to konto nie istnieje w apce.
    """
    konto_clean = re.sub(r'\s*\([^)]*\)\s*$', '', konto_raw).strip()

    for lookup_key in (konto_raw, konto_clean):
        if lookup_key in name_to_account_id:
            return True, name_to_account_id[lookup_key]

    fallback_id = db_name_to_account_id.get(konto_clean.lower())
    if fallback_id is not None:
        return True, fallback_id

    return False, None


def parse_ing_csv(file_content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """
    Parsuje plik CSV z ING.

    Plik wielokontowy (ma sekcję 'Wybrane rachunki' i kolumnę 'Konto'):
      — automatycznie wykrywa konto źródłowe każdej transakcji na podstawie kolumny 'Konto'.
      — transakcje z kont nieznanych aplikacji (brak account_number) są pomijane.
      — obie nogi przelewu wewnętrznego wchodzą do importu; wiąże je ze sobą
        zatwierdzanie stagingu (handle_internal_transfer), a nie parser.

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

    # 2. Dopasuj konta z CSV do kont w bazie danych (po numerze IBAN) — wspólne
    # z parserem PDF, patrz build_ing_account_maps.
    csv_accounts_info, csv_name_to_account_id, db_name_to_account_id, _ = (
        build_ing_account_maps(csv_accounts_entries, user_token)
    )

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
    is_multi_account = 'Konto' in header_map and bool(csv_accounts_entries)

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
        raise BrakKontaError("Plik CSV zawiera jedno konto — proszę wybrać konto docelowe przed importem.")

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
                in_csv_accounts, matched_id = resolve_ing_account_label(
                    konto_raw, csv_name_to_account_id, db_name_to_account_id
                )

                if not in_csv_accounts:
                    # Podkonto / cel oszczędnościowy (np. "iPad 3k") — pomiń
                    skipped_count += 1
                    continue
                if matched_id is None:
                    # Konto z CSV nie istnieje w aplikacji — pomiń
                    skipped_count += 1
                    continue

                parsed_row['account_id'] = matched_id
            else:
                parsed_row['account_id'] = main_account_id

            transactions.append(parsed_row)
        except (ValueError, StopIteration, IndexError) as e:
            if line.strip() and line.strip()[0].isdigit():
                # Logujemy sam powód, NIE treść wiersza — wiersz z wyciągu zawiera
                # kontrahenta, tytuł, kwotę i numer konta, czyli dane finansowe (A10).
                logger.warning("Odrzucono wiersz CSV przy imporcie (user_token=%s): %s", user_token, e)
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
        raise BrakKontaError("Plik CSV z mBanku dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

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
    category_col = header_map.get('Kategoria')

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
        bank_category = parts[category_col].strip() if category_col is not None and category_col < len(parts) else ''
        amount_str = parts[amount_col].strip() if amount_col < len(parts) else ''

        if not amount_str.replace('PLN', '').strip():
            continue
        amount = _clean_amount(amount_str)
        if amount is None:
            logger.warning("Odrzucono wiersz mBank CSV — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue

        try:
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                tx_date = datetime.strptime(date_str, '%d.%m.%Y').date()
            except ValueError:
                logger.warning("Odrzucono wiersz mBank — nieznany format daty (user_token=%s)", user_token)
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
            'bank_category': bank_category or None,
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

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_PERIOD_RE = re.compile(r'od\s*(\d{4}-\d{2}-\d{2})\s*do\s*(\d{4}-\d{2}-\d{2})')
_AMOUNT_PLN_RE = re.compile(r'(-?\d[\d \xa0]*,\d{2})\s*PLN')

_ING_DATE_RE = re.compile(r'^\d{2}\.\d{2}\.\d{4}$')
_ING_PERIOD_RE = re.compile(r'(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})')
_ANY_26_DIGITS_RE = re.compile(r'(?<!\d)\d{26}(?!\d)')
_KWOTA_PLATNOSCI_RE = re.compile(r'^kwota płatności\s*:?\s*$', re.IGNORECASE)


def decode_statement_bytes(raw: bytes) -> str:
    """Dekoduje bajty wyciągu: UTF-8(-sig) z fallbackiem na windows-1250.

    Ta sama kolejność co w endpoincie importu CSV — polskie banki eksportują
    w jednym z tych dwóch kodowań.
    """
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('windows-1250')


def detect_bank_and_format(raw: bytes, filename: str = '') -> tuple[Optional[str], Optional[str]]:
    """Rozpoznaje (bank, format) po zawartości pliku, nie po rozszerzeniu.

    Zwraca np. ('mbank', 'html'); (None, None) gdy nie rozpoznano —
    wtedy użytkownik musi wybrać ręcznie.
    """
    if raw.startswith(b'%PDF'):
        try:
            import fitz
            with fitz.open(stream=raw, filetype='pdf') as doc:
                text = doc[0].get_text() if len(doc) else ''
        except Exception as e:
            logger.warning("Detekcja PDF nie powiodła się: %s", e)
            return None, 'pdf'
        # Markery STRUKTURALNE nagłówka, nie substring nazwy banku — nazwa
        # 'mBank' może wystąpić w danych KONTRAHENTA na wyciągu innego banku.
        # ING najpierw: 'Lista transakcji' / 'Wybrane rachunki' to jego
        # unikalne nagłówki (mBank używa 'Lista operacji' / 'dla rachunków').
        # Millennium przed ING: też ma 'Lista transakcji'. Adres strony, nie nazwa
        # banku — 'Bank Millennium SA' bywa kontrahentem na cudzych wyciągach.
        if 'www.bankmillennium.pl' in text:
            return 'millennium', 'pdf'
        if 'Lista transakcji' in text or 'Wybrane rachunki' in text:
            return 'ing', 'pdf'
        if 'Lista operacji' in text or 'Listaoperacji' in text or 'mBank S.A. Bankowo' in text:
            return 'mbank', 'pdf'
        # Na końcu: nazwa Revoluta bywa kontrahentem na wyciągach innych banków.
        if 'Revolut Bank UAB' in text:
            return 'revolut', 'pdf'
        return None, 'pdf'

    try:
        text = decode_statement_bytes(raw)
    except UnicodeDecodeError:
        return None, None

    lowered = text.lower()
    if '<html' in lowered[:2000]:
        if 'mbank' in lowered or 'bre.pl' in lowered:
            # Drugi eksport HTML mBanku (spotkany na rachunku celowym) — inny
            # układ kolumn, więc osobny parser; zwykły wziąłby saldo za kwotę.
            if _MBANK_ZESTAWIENIE_MARKER in text:
                return 'mbank', 'html-zest'
            return 'mbank', 'html'
        if 'millennium' in lowered:
            return 'millennium', 'html'
        return None, 'html'

    # CSV — po charakterystycznych nagłówkach kolumn. Pekao i Millennium przed ING:
    # Pekao ma 'Data księgowania', Millennium 'Data transakcji' — tak jak ING.
    if text.startswith(_REVOLUT_HEADER_MARKER):
        return 'revolut', 'csv'
    if _PEKAO_HEADER_MARKER in text[:500]:
        return 'pekao', 'csv'
    if _MILLENNIUM_HEADER_MARKER in text[:500]:
        return 'millennium', 'csv'
    if '#Data operacji' in text or text.lstrip().startswith('mBank S.A.'):
        return 'mbank', 'csv'
    if 'Data transakcji' in text:
        return 'ing', 'csv'
    return None, None


def extract_statement_ibans(raw: bytes, bank: Optional[str], fmt: Optional[str]) -> list[str]:
    """Lekka ekstrakcja numerów rachunków, których dotyczy wyciąg — bez pełnego
    parsowania. Używane do automatycznego rozpoznania konta przy imporcie
    (zanim parser dostanie main_account_id).

    mBank: nagłówek 'dla rachunków: <nazwisko> - <26 cyfr>' występuje we
    wszystkich trzech formatach PRZED pierwszą transakcją, więc pierwsze
    wystąpienie 26-cyfrowego ciągu to rachunek wyciągu.
    ING: pliki wielokontowe same przypisują konta (sekcja 'Wybrane rachunki'),
    więc nie ma potrzeby rozpoznawania — zwracamy pustą listę.
    """
    if bank == 'pekao':
        try:
            rows = _pekao_rows(decode_statement_bytes(raw))
            return [_pekao_own_and_other(next(rows))[0]]
        except (UnicodeDecodeError, StopIteration, KeyError):
            return []
    if bank == 'millennium' and fmt == 'csv':
        try:
            rows = _millennium_rows(decode_statement_bytes(raw))
            ibans = set(filter(None, map(_millennium_iban, rows)))
        except (UnicodeDecodeError, KeyError):
            return []
        # Plik z kilkoma rachunkami parser rozdziela sam, wiersz po wierszu — jak ING.
        return list(ibans) if len(ibans) == 1 else []
    if bank != 'mbank':
        return []
    if fmt == 'html-zest':
        try:
            return _mbank_zestawienie_ibans(BeautifulSoup(decode_statement_bytes(raw), 'html.parser').get_text(' '))
        except UnicodeDecodeError:
            return []
    if fmt == 'pdf':
        try:
            import fitz
            with fitz.open(stream=raw, filetype='pdf') as doc:
                text = doc[0].get_text() if len(doc) else ''
        except Exception:
            return []
    else:
        try:
            text = decode_statement_bytes(raw)
        except UnicodeDecodeError:
            return []
    m = _MBANK_ACCOUNT_RE.search(text)
    return [m.group(0)] if m else []


def _clean_amount(amount_str: str) -> Optional[Decimal]:
    """'1 210,00 PLN' → Decimal('1210.00'); None gdy nie-kwota."""
    cleaned = (amount_str
               .replace('PLN', '')
               .replace('\xa0', '')
               .replace(' ', '')
               .replace(',', '.')
               .strip())
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _extract_period(text: str) -> tuple[Optional[object], Optional[object]]:
    m = _PERIOD_RE.search(text)
    if not m:
        return None, None
    try:
        start = datetime.strptime(m.group(1), '%Y-%m-%d').date()
        end = datetime.strptime(m.group(2), '%Y-%m-%d').date()
        return start, end
    except ValueError:
        return None, None


def parse_mbank_html(content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Zestawienie operacji' mBanku w HTML (jednokontowe).

    HTML jest bogatszy niż CSV mBanku: opis operacji jest rozbity <br> na
    części — [0] czytelny tytuł, [1..] szczegóły (kontrahent/adres/typ),
    ostatnia bywa numerem rachunku kontrahenta. CSV skleja to w jeden blob.
    """
    if main_account_id is None:
        raise BrakKontaError("Wyciąg mBank dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

    soup = BeautifulSoup(content, 'html.parser')
    full_text = soup.get_text(' ')
    period_start, period_end = _extract_period(full_text)
    statement_ibans = _MBANK_ACCOUNT_RE.findall(full_text)[:1]

    transactions: list[dict] = []
    skipped_count = 0

    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 5:
            continue
        date_str = tds[0].get_text(strip=True)
        if not _DATE_RE.match(date_str):
            continue

        try:
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            skipped_count += 1
            continue

        amount = _clean_amount(tds[4].get_text(strip=True))
        if amount is None:
            logger.warning("Odrzucono wiersz mBank HTML — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue

        desc_td = tds[1]
        parts = [re.sub(r'\s+', ' ', s).strip() for s in desc_td.strings]
        parts = [p for p in parts if p]

        desc_full = ' '.join(parts)
        acc_match = _MBANK_ACCOUNT_RE.search(desc_full)
        counterparty_account = acc_match.group(0) if acc_match else None

        title = parts[0] if parts else ''
        # Szczegóły (bez części będącej samym numerem rachunku) — do analizy
        # słów kluczowych kontrahenta.
        detail_parts = [p for p in parts[1:] if not _MBANK_ACCOUNT_RE.fullmatch(p)]
        contractor = ' '.join(detail_parts) or None

        transactions.append({
            'date': tx_date,
            'contractor': contractor,
            'title': title,
            'amount': amount,
            'counterparty_account': counterparty_account,
            'account_id': main_account_id,
            'bank_category': tds[3].get_text(strip=True) or None,
        })

    logger.info(
        "Import HTML mBank zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': [],
        'skipped_count': skipped_count,
        'period_start': period_start,
        'period_end': period_end,
        'statement_ibans': statement_ibans,
    }


_MBANK_ZESTAWIENIE_MARKER = 'Elektroniczne zestawienie operacji'
# W tym eksporcie numer rachunku stoi w nagłówku ze spacjami: '29 1140 2004 ...'.
_MBANK_ZESTAWIENIE_IBAN_RE = re.compile(r'Numer rachunku\s*((?:\d\s*){26})')


def _mbank_zestawienie_ibans(full_text: str) -> list[str]:
    m = _MBANK_ZESTAWIENIE_IBAN_RE.search(full_text)
    return [re.sub(r'\s', '', m.group(1))] if m else []


def parse_mbank_zestawienie_html(content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Elektroniczne zestawienie operacji' mBanku w HTML (jednokontowe).

    Inny eksport niż 'Lista operacji' z parse_mbank_html: kolumny to
    Data księgowania | Data operacji | Opis | Kwota | Saldo po operacji —
    bez kategorii i bez rachunku. Data transakcji = data operacji, jak
    w pozostałych formatach mBanku.
    """
    if main_account_id is None:
        raise BrakKontaError("Wyciąg mBank dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

    soup = BeautifulSoup(content, 'html.parser')
    full_text = soup.get_text(' ')
    period_start, period_end = _extract_period(full_text)

    transactions: list[dict] = []
    skipped_count = 0

    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) != 5:
            continue
        booking_str, date_str = tds[0].get_text(strip=True), tds[1].get_text(strip=True)
        if not (_DATE_RE.match(booking_str) and _DATE_RE.match(date_str)):
            continue

        try:
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            skipped_count += 1
            continue

        amount = _clean_amount(tds[3].get_text(strip=True))
        if amount is None:
            logger.warning("Odrzucono wiersz mBank HTML (zestawienie) — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue

        parts = [re.sub(r'\s+', ' ', s).strip() for s in tds[2].strings]
        parts = [p for p in parts if p]
        acc_match = _MBANK_ACCOUNT_RE.search(' '.join(parts))
        detail_parts = [p for p in parts[1:] if not _MBANK_ACCOUNT_RE.fullmatch(p)]

        transactions.append({
            'date': tx_date,
            'contractor': ' '.join(detail_parts) or None,
            'title': parts[0] if parts else '',
            'amount': amount,
            'counterparty_account': acc_match.group(0) if acc_match else None,
            'account_id': main_account_id,
            'bank_category': None,
        })

    logger.info(
        "Import HTML mBank (zestawienie) zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': [],
        'skipped_count': skipped_count,
        'period_start': period_start,
        'period_end': period_end,
        'statement_ibans': _mbank_zestawienie_ibans(full_text),
    }


def parse_mbank_pdf(raw: bytes, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Lista operacji' mBanku w PDF (jednokontowa, tekstowa — nie skan).

    Ekstrakcja tekstu przez PyMuPDF (fitz) — wbudowane parsery zachowują
    polskie znaki. Blok transakcji zaczyna się od linii z datą ISO; kwota to
    ostatnie wystąpienie 'N,NN PLN' w bloku; numer rachunku kontrahenta to
    ciąg 26 cyfr we własnej linii.
    """
    if main_account_id is None:
        raise BrakKontaError("Wyciąg mBank dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

    import fitz
    with fitz.open(stream=raw, filetype='pdf') as doc:
        text = '\n'.join(page.get_text() for page in doc)

    period_start, period_end = _extract_period(text)
    lines = [l.strip() for l in text.splitlines()]

    # Numer rachunku wyciągu: pierwszy 26-cyfrowy PRZED pierwszą linią transakcji
    statement_ibans: list[str] = []
    first_tx_idx = next(
        (i for i, l in enumerate(lines) if re.match(r'^\d{4}-\d{2}-\d{2}\b', l)), len(lines)
    )
    for l in lines[:first_tx_idx]:
        m = _MBANK_ACCOUNT_RE.search(l)
        if m:
            statement_ibans = [m.group(0)]
            break

    transactions: list[dict] = []
    skipped_count = 0

    # Podziel na bloki: od linii z datą do następnej linii z datą
    block: list[str] = []
    blocks: list[list[str]] = []
    for l in lines[first_tx_idx:]:
        if re.match(r'^\d{4}-\d{2}-\d{2}\b', l):
            if block:
                blocks.append(block)
            block = [l]
        elif block:
            block.append(l)
    if block:
        blocks.append(block)

    for blk in blocks:
        first = blk[0]
        date_str = first[:10]
        try:
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            skipped_count += 1
            continue

        blk_text = ' '.join(blk)
        amount_matches = _AMOUNT_PLN_RE.findall(blk_text)
        if not amount_matches:
            skipped_count += 1
            continue
        amount = _clean_amount(amount_matches[-1])
        if amount is None:
            logger.warning("Odrzucono blok mBank PDF — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue

        acc_match = _MBANK_ACCOUNT_RE.search(blk_text)
        counterparty_account = acc_match.group(0) if acc_match else None

        title = re.sub(r'\s+', ' ', first[10:]).strip()
        detail_lines = [
            l for l in blk[1:]
            if not _MBANK_ACCOUNT_RE.fullmatch(l) and not _AMOUNT_PLN_RE.search(l)
        ]
        # Realny układ PDF: data bywa we WŁASNEJ linii — wtedy tytułem jest
        # pierwsza linia szczegółów (odpowiednik części [0] z HTML).
        if not title and detail_lines:
            title = detail_lines.pop(0)
        contractor = re.sub(r'\s+', ' ', ' '.join(detail_lines)).strip() or None

        transactions.append({
            'date': tx_date,
            'contractor': contractor,
            'title': title,
            'amount': amount,
            'counterparty_account': counterparty_account,
            'account_id': main_account_id,
        })

    logger.info(
        "Import PDF mBank zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': [],
        'skipped_count': skipped_count,
        'period_start': period_start,
        'period_end': period_end,
        'statement_ibans': statement_ibans,
    }


def _extract_ing_pdf_period(text: str) -> tuple[Optional[object], Optional[object]]:
    m = _ING_PERIOD_RE.search(text)
    if not m:
        return None, None
    try:
        start = datetime.strptime(m.group(1), '%d.%m.%Y').date()
        end = datetime.strptime(m.group(2), '%d.%m.%Y').date()
        return start, end
    except ValueError:
        return None, None


_ING_ACCOUNT_LABEL_RE = re.compile(r'^.+\([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{2,4}\)$')


def _extract_ing_pdf_accounts(lines: list[str]) -> list[tuple[str, str]]:
    """Parsuje sekcję 'Wybrane rachunki' nagłówka: N etykiet produktowych
    ('KONTO Z LWEM Direct (PLN)') i N numerów IBAN w TEJ SAMEJ kolejności
    ('45 1050 1025 1000 0091 0293 0329').

    Nagłówek PDF ma dwie kolumny (dane użytkownika + wybrane rachunki)
    spłaszczone przez ekstrakcję tekstu do jednej sekwencji linii — między
    'Wybrane rachunki' a pierwszą etykietą konta wtrąca się blok imię/adres
    użytkownika (zmienna liczba linii). Dlatego NIE zakładamy stałej pozycji:
    skanujemy cały obszar nagłówka i zbieramy WSZYSTKIE linie pasujące do
    kształtu etykiety/IBAN, ignorując resztę."""
    try:
        start = next(i for i, l in enumerate(lines) if 'Wybrane rachunki' in l)
    except StopIteration:
        return []
    try:
        end = next(
            i for i in range(start, len(lines))
            if 'Zastosowane kryteria' in lines[i] or 'Data transakcji' in lines[i]
        )
    except StopIteration:
        end = len(lines)

    region = lines[start:end]
    labels = [
        re.sub(r'\s*\([^)]*\)\s*$', '', l).strip()
        for l in region if _ING_ACCOUNT_LABEL_RE.match(l)
    ]
    # Numery IBAN w nagłówku bywają rozdzielone twardą spacją (\xa0), nie zwykłą
    # — \s w re (domyślnie Unicode dla wzorców str) łapie oba warianty.
    ibans = []
    for l in region:
        compact = re.sub(r'\s+', '', l)
        if len(compact) == 26 and compact.isdigit():
            ibans.append(compact)

    return list(zip(labels, ibans))


def parse_ing_pdf(raw: bytes, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Lista transakcji' ING w PDF (zwykle wielokontowa, tekstowa).

    Tabela spłaszczona do tekstu przez PyMuPDF: blok transakcji zaczyna się od
    DWÓCH KOLEJNYCH linii z datą DD.MM.YYYY (data transakcji + księgowania) —
    ten podwójny wzorzec odróżnia START bloku od dat powtarzających się w
    środku (np. przy płatnościach kartą). Blok kończy się dwiema ostatnimi
    liniami-kwotami: [kwota transakcji, saldo po transakcji] — brane OD KOŃCA,
    nie od początku, bo transakcje walutowe mają wcześniejszą, dodatkową kwotę
    referencyjną w PLN ('Kwota: X PLN' obok oryginalnej kwoty w EUR/USD).
    Etykieta konta to linie MIĘDZY tymi dwiema kwotami.

    Rozpoznawanie kont dzieli logikę z parserem CSV (build_ing_account_maps /
    resolve_ing_account_label wyżej w tym module) — ING pokazuje w treści
    transakcji przemianowane konto (np. "Wakacje") inaczej niż w nagłówku
    ("Otwarte Konto Oszczędnościowe"), identycznie jak w CSV.

    Tytuł/kontrahent to uproszczenie MVP (pierwsza linia opisu = tytuł, reszta
    = kontrahent-blob) — pełny rozkład na kolumny "Tytuł" vs "Dane kontrahenta"
    nie jest w pełni odtwarzalny z płaskiego tekstu PDF dla wszystkich typów
    operacji (ten sam kompromis co blob mBank CSV, patrz IDEAS.md).
    """
    import fitz
    with fitz.open(stream=raw, filetype='pdf') as doc:
        text = '\n'.join(page.get_text() for page in doc)

    period_start, period_end = _extract_ing_pdf_period(text)
    lines = [l.strip() for l in text.splitlines()]

    account_entries = _extract_ing_pdf_accounts(lines)
    accounts_info, name_to_account_id, db_name_to_account_id, ibans_set = (
        build_ing_account_maps(account_entries, user_token)
    )
    is_multi_account = bool(account_entries)

    if not is_multi_account and main_account_id is None:
        raise BrakKontaError("Plik PDF zawiera jedno konto — proszę wybrać konto docelowe przed importem.")

    starts = [i for i in range(len(lines) - 1) if _ING_DATE_RE.match(lines[i]) and _ING_DATE_RE.match(lines[i + 1])]
    if not starts:
        raise ValueError("Nie rozpoznano żadnej transakcji w pliku PDF ING (brak par dat DD.MM.RRRR).")

    transactions: list[dict] = []
    skipped_count = 0

    for idx, s in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        block = [l for l in lines[s:end] if l]

        try:
            tx_date = datetime.strptime(block[0], '%d.%m.%Y').date()
        except ValueError:
            skipped_count += 1
            continue

        amount_line_idx = [i for i, l in enumerate(block) if _AMOUNT_PLN_RE.search(l)]
        if len(amount_line_idx) < 2:
            skipped_count += 1
            continue

        amount_idx, balance_idx = amount_line_idx[-2], amount_line_idx[-1]
        amount = _clean_amount(_AMOUNT_PLN_RE.search(block[amount_idx]).group(1))
        if amount is None:
            logger.warning("Odrzucono blok ING PDF — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue

        # Płatności kartą w walucie obcej czasem wstawiają między kwotą PLN
        # a etykietą konta parę linii "kwota płatności:" + kwota w walucie
        # oryginalnej (np. "-10,00 EUR") — trzeba je pominąć, inaczej wpadają
        # do etykiety konta i psują dopasowanie.
        konto_lines = block[amount_idx + 1:balance_idx]
        cleaned_konto_lines = []
        skip_next = False
        for line in konto_lines:
            if skip_next:
                skip_next = False
                continue
            if _KWOTA_PLATNOSCI_RE.match(line):
                skip_next = True
                continue
            cleaned_konto_lines.append(line)
        konto_raw = ' '.join(cleaned_konto_lines).strip()
        if is_multi_account:
            in_known_accounts, matched_id = resolve_ing_account_label(
                konto_raw, name_to_account_id, db_name_to_account_id
            )
            if not in_known_accounts:
                # Podkonto/cel spoza słownika (np. "iPad 3k") — pomiń, nie zgadujemy.
                skipped_count += 1
                continue
            if matched_id is None:
                skipped_count += 1
                continue
            account_id = matched_id
        else:
            account_id = main_account_id

        desc_lines = block[2:amount_idx]
        title = desc_lines[0] if desc_lines else ''
        contractor = ' '.join(desc_lines[1:]).strip() or None

        desc_text = ' '.join(desc_lines)
        acc_match = _ANY_26_DIGITS_RE.search(desc_text)
        counterparty_account = acc_match.group(0) if acc_match else None

        transactions.append({
            'date': tx_date,
            'contractor': contractor,
            'title': title,
            'amount': amount,
            'counterparty_account': counterparty_account,
            'account_id': account_id,
        })

    logger.info(
        "Import PDF ING zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': accounts_info,
        'skipped_count': skipped_count,
        'period_start': period_start,
        'period_end': period_end,
        'statement_ibans': list(ibans_set),
    }


_PEKAO_HEADER_MARKER = 'Nadawca / Odbiorca;Adres nadawcy / odbiorcy'


def _pekao_rows(content: str):
    """Wiersze CSV Pekao jako słowniki; pomija linie bez daty (puste/stopka)."""
    reader = csv.DictReader(io.StringIO(content), delimiter=';')
    return (r for r in reader if _ING_DATE_RE.match((r.get('Data księgowania') or '').strip()))


def _pekao_own_and_other(row: dict) -> tuple[str, str]:
    """(rachunek wyciągu, rachunek kontrahenta). Pekao nie ma numeru konta
    w nagłówku — własny rachunek jest źródłowym przy wydatku, docelowym przy
    wpływie. Apostrof to zabezpieczenie eksportu przed Excelem."""
    src = row['Rachunek źródłowy'].strip().lstrip("'")
    dst = row['Rachunek docelowy'].strip().lstrip("'")
    return (src, dst) if row['Kwota operacji'].strip().startswith('-') else (dst, src)


def parse_pekao_csv(content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Historię operacji' Pekao w CSV (jednokontowe, UTF-8, średnik).

    Kolumna 'Kategoria' jest opcjonalna w eksporcie — trafia do 'bank_category'
    jako podpowiedź (#192). Brak salda po operacji.
    """
    if main_account_id is None:
        raise BrakKontaError("Wyciąg Pekao dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

    transactions: list[dict] = []
    skipped_count = 0
    ibans_set = set()

    for row in _pekao_rows(content):
        amount = _clean_amount(row['Kwota operacji'])
        if amount is None:
            logger.warning("Odrzucono wiersz Pekao CSV — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue
        try:
            tx_date = datetime.strptime(row['Data księgowania'].strip(), '%d.%m.%Y').date()
        except ValueError:
            skipped_count += 1
            continue

        own, other = _pekao_own_and_other(row)
        if own:
            ibans_set.add(own)
        # Nazwy z terminali kartowych mają miasto dopełnione spacjami.
        contractor = re.sub(r'\s+', ' ', row['Nadawca / Odbiorca']).strip() or None
        title = row['Tytułem'].strip() or row['Typ operacji'].strip()

        transactions.append({
            'date': tx_date,
            'contractor': contractor,
            'title': title,
            'amount': amount,
            'counterparty_account': other or None,
            'account_id': main_account_id,
            'bank_category': (row.get('Kategoria') or '').strip() or None,
        })

    dates = [t['date'] for t in transactions]
    logger.info(
        "Import CSV Pekao zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': [],
        'skipped_count': skipped_count,
        'period_start': min(dates, default=None),
        'period_end': max(dates, default=None),
        'statement_ibans': list(ibans_set),
    }


_MILLENNIUM_HEADER_MARKER = '"Numer rachunku/karty","Data transakcji"'


def _millennium_rows(content: str):
    """Wiersze CSV Millennium jako słowniki; pomija linie bez daty."""
    reader = csv.DictReader(io.StringIO(content))
    return (r for r in reader if _DATE_RE.match((r.get('Data transakcji') or '').strip()))


def _millennium_iban(row: dict) -> Optional[str]:
    """Numer rachunku wyciągu z wiersza; None, gdy w kolumnie jest numer karty."""
    num = row['Numer rachunku/karty'].replace(' ', '')
    return num if len(_normalize_acc_num(num)) == 26 else None


def parse_millennium_csv(content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Listę transakcji' Millennium w CSV (UTF-8, przecinek).

    Plik może obejmować kilka rachunków (kolumna 'Numer rachunku/karty'). Wtedy
    każdy wiersz trafia na konto o numerze z tego wiersza, a wiersze rachunku bez
    konta w aplikacji są pomijane — jak w wielokontowym ING. Przy jednym rachunku
    wszystko idzie na main_account_id (jego zgodność z numerem sprawdził już
    resolve_statement_account); na nie idą też wiersze z numerem karty — przy
    kilku rachunkach tylko wtedy, gdy wybrane konto jest jednym z nich.

    Pola wielowierszowe (nazwa + adres kontrahenta, opis) bank skleja niełamliwą
    spacją. Brak kategorii z banku.
    """
    rows = list(_millennium_rows(content))
    file_ibans = list(dict.fromkeys(filter(None, map(_millennium_iban, rows))))
    csv_accounts: list[dict] = []
    iban_to_account_id: dict[str, Optional[int]] = {}
    if len(file_ibans) > 1:
        csv_accounts, iban_to_account_id, _, _ = build_ing_account_maps(
            [(iban, _normalize_acc_num(iban)) for iban in file_ibans], user_token
        )
        # Wiersze kart idą na wybrane konto, a resolve_statement_account nie miał
        # przy kilku rachunkach z czym go porównać — sprawdzamy tutaj (#181).
        if main_account_id is not None and main_account_id not in iban_to_account_id.values():
            raise ValueError("Wybrane konto nie jest żadnym z rachunków w tym wyciągu Millennium. "
                             "Wybierz konto, do którego należy karta, albo pozostaw wybór automatyczny.")

    transactions: list[dict] = []
    skipped_count = 0
    ibans_set = set()

    for row in rows:
        # Obcięty wiersz: DictReader daje None — kolumny kwot są za wszystkimi
        # pozostałymi, więc jeśli kwota jest, to reszta wiersza też.
        amount = _clean_amount(row['Obciążenia'] or row['Uznania'] or '')
        if amount is None:
            logger.warning("Odrzucono wiersz Millennium CSV — nieprawidłowa kwota (user_token=%s)", user_token)
            skipped_count += 1
            continue

        iban = _millennium_iban(row)
        if iban:
            ibans_set.add(iban)
        if iban and iban_to_account_id:
            account_id = iban_to_account_id[iban]
            if account_id is None:
                skipped_count += 1
                continue
        elif main_account_id is None:
            if iban_to_account_id:
                raise BrakKontaError("Wyciąg Millennium zawiera operacje kartą bez numeru rachunku — "
                                     "wybierz konto, do którego należy karta.")
            raise BrakKontaError("Wyciąg Millennium dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")
        else:
            account_id = main_account_id
        contractor = row['Odbiorca/Zleceniodawca'].split('\xa0')[0].strip() or None
        title = row['Opis'].replace('\xa0', ' ').strip() or row['Rodzaj transakcji'].strip()

        transactions.append({
            'date': datetime.strptime(row['Data transakcji'].strip(), '%Y-%m-%d').date(),
            'contractor': contractor,
            'title': title,
            'amount': amount,
            'counterparty_account': row['Na konto/Z konta'].replace(' ', '') or None,
            'account_id': account_id,
            'bank_category': None,
        })

    dates = [t['date'] for t in transactions]
    logger.info(
        "Import CSV Millennium zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': csv_accounts,
        'skipped_count': skipped_count,
        'period_start': min(dates, default=None),
        'period_end': max(dates, default=None),
        'statement_ibans': list(ibans_set),
    }


_REVOLUT_HEADER_MARKER = 'Rodzaj,Produkt,Data rozpoczęcia,Data zrealizowania'
_REVOLUT_ZAKONCZONA = 'ZAKOŃCZONO'
_REVOLUT_WYMIANA_RE = re.compile(r'^Wymiana na ([A-Z]{3})$')


def _revolut_ma_druga_noge(konto: Account, tytul: str, dzien, kwota: Decimal) -> bool:
    """Czy na koncie jest już (zaksięgowana albo w poczekalni) druga noga tej wymiany:
    ten sam tytuł ze znacznikiem czasu co do sekundy, ten sam dzień, przeciwny znak."""
    for model in (Transaction, TransactionStaging):
        q = db.session.query(model.id).filter(
            model.user_token == konto.user_token, model.account_id == konto.id,
            model.title == tytul, model.date == dzien,
            model.amount > 0 if kwota < 0 else model.amount < 0,
        )
        if model is TransactionStaging:
            q = q.filter(model.status == 'pending')
        if q.first():
            return True
    return False


def _revolut_subkonto_wymiany(opis: str, konto: Account, tytul: str, dzien, kwota: Decimal) -> Optional[int]:
    """Konto po drugiej stronie wymiany walut albo None, gdy nie da się go wskazać.

    Subkonta walutowe Revoluta to w aplikacji osobne konta tego samego banku
    (bank_name). Opis mówi tylko, NA jaką walutę wymieniono: w pliku PLN
    „Wymiana na EUR" wskazuje subkonto EUR, ale w pliku EUR ten sam opis nie mówi,
    skąd przyszły pieniądze. Przy kilku możliwych subkontach rozstrzyga druga noga,
    jeśli już ją mamy (#216); bez niej nie zgadujemy.
    """
    m = _REVOLUT_WYMIANA_RE.match(opis)
    if not m or not konto.bank_name:
        return None
    kandydaci = [
        a for a in db.session.query(Account).filter(
            Account.user_token == konto.user_token, Account.is_active.is_(True), Account.id != konto.id
        )
        if (a.bank_name or '').lower() == konto.bank_name.lower() and (a.currency or 'PLN') != konto.currency
    ]
    if m.group(1) != konto.currency:
        kandydaci = [a for a in kandydaci if a.currency == m.group(1)]
    if len(kandydaci) > 1:
        kandydaci = [a for a in kandydaci if _revolut_ma_druga_noge(a, tytul, dzien, kwota)]
    return kandydaci[0].id if len(kandydaci) == 1 else None


def parse_revolut_csv(content: str, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje wyciąg Revolut w CSV (jedno subkonto walutowe, UTF-8, przecinek).

    - Plik nie ma numeru rachunku — konto wybiera użytkownik, a kolumna 'Waluta'
      musi zgadzać się z walutą konta.
    - Data = data realizacji; w tej kolejności narasta saldo w pliku.
    - Pomija operacje niezakończone (oczekujące, cofnięte) — nie ruszyły salda.
    - Opłata to osobna transakcja (widoczna w Raportach), nie pomniejszenie kwoty.
    - Tytuł niesie znacznik czasu rozpoczęcia co do sekundy: dwie identyczne
      płatności tego samego dnia nie zleją się przy deduplikacji importu, a obie
      nogi wymiany walut mają ten sam tytuł, po którym są parowane.
    """
    if main_account_id is None:
        raise BrakKontaError("Wyciąg Revolut dotyczy jednego subkonta walutowego — proszę wybrać konto docelowe przed importem.")
    konto = db.session.query(Account).filter_by(id=main_account_id, user_token=user_token).first()
    if konto is None:
        raise ValueError("Wybrane konto nie istnieje lub brak uprawnień.")

    transactions: list[dict] = []
    skipped_count = 0

    for row in csv.DictReader(io.StringIO(content)):
        if row.get('State') != _REVOLUT_ZAKONCZONA or not row.get('Data zrealizowania'):
            skipped_count += 1
            continue
        if row['Waluta'] != (konto.currency or 'PLN'):
            raise ValueError(
                f"Wyciąg jest w {row['Waluta']}, a konto '{konto.name}' prowadzone jest w "
                f"{konto.currency or 'PLN'}. Wybierz subkonto w walucie wyciągu."
            )
        try:
            amount = Decimal(row['Kwota'])
            fee = Decimal(row['Opłata'] or '0')
            tx_date = datetime.strptime(row['Data zrealizowania'][:10], '%Y-%m-%d').date()
        except (InvalidOperation, ValueError):
            logger.warning("Odrzucono wiersz Revolut CSV — nieprawidłowa kwota lub data (user_token=%s)", user_token)
            skipped_count += 1
            continue

        opis = row['Opis'].strip()
        title = f"{row['Rodzaj'].strip()} {row['Data rozpoczęcia'].strip()}"
        transactions.append({
            'date': tx_date,
            'contractor': opis or None,
            'title': title,
            'amount': amount,
            'counterparty_account': None,
            'account_id': main_account_id,
            'bank_category': None,
            'transfer_account_id': _revolut_subkonto_wymiany(opis, konto, title, tx_date, amount),
        })
        if fee:
            transactions.append({
                'date': tx_date,
                'contractor': 'Revolut',
                'title': f"Opłata: {title}",
                'amount': -fee,
                'counterparty_account': None,
                'account_id': main_account_id,
                'bank_category': None,
            })

    dates = [t['date'] for t in transactions]
    logger.info(
        "Import CSV Revolut zakończony (user_token=%s): sparsowano %d transakcji, pominięto %d",
        user_token, len(transactions), skipped_count
    )
    return {
        'transactions': transactions,
        'csv_accounts': [],
        'skipped_count': skipped_count,
        'period_start': min(dates, default=None),
        'period_end': max(dates, default=None),
        'statement_ibans': [],
    }
