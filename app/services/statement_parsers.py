"""Detekcja banku/formatu wyciągu oraz parsery formatów innych niż CSV.

Każdy parser zwraca ten sam kształt co parse_ing_csv / parse_mbank_csv
(budget_service.py): {'transactions': [...], 'csv_accounts': [...],
'skipped_count': int} — dzięki temu dalszy przepływ (save_transactions_to_staging,
autokategoryzacja, staging) jest wspólny dla wszystkich banków i formatów.

Dodatkowo parsery zwracają, gdy da się je wyczytać z nagłówka wyciągu:
  'period_start' / 'period_end' — zakres dat wyciągu (pod historię importów
      i wykrywanie nakładających się okresów),
  'statement_ibans' — numery rachunków, których dotyczy plik (pod walidację
      konta i analizę pokrycia przy imporcie wielu plików).
"""
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from bs4 import BeautifulSoup

from app.services.budget_service import (
    _MBANK_ACCOUNT_RE,
    build_ing_account_maps,
    resolve_ing_account_label,
)

logger = logging.getLogger(__name__)

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
        if 'Lista transakcji' in text or 'Wybrane rachunki' in text:
            return 'ing', 'pdf'
        if 'Lista operacji' in text or 'Listaoperacji' in text or 'mBank S.A. Bankowo' in text:
            return 'mbank', 'pdf'
        return None, 'pdf'

    try:
        text = decode_statement_bytes(raw)
    except UnicodeDecodeError:
        return None, None

    lowered = text.lower()
    if '<html' in lowered[:2000]:
        if 'mbank' in lowered or 'bre.pl' in lowered:
            return 'mbank', 'html'
        return None, 'html'

    # CSV — po charakterystycznych nagłówkach kolumn
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
    if bank != 'mbank':
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
        raise ValueError("Wyciąg mBank dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

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


def parse_mbank_pdf(raw: bytes, user_token: str, main_account_id: Optional[int] = None) -> dict:
    """Parsuje 'Lista operacji' mBanku w PDF (jednokontowa, tekstowa — nie skan).

    Ekstrakcja tekstu przez PyMuPDF (fitz) — wbudowane parsery zachowują
    polskie znaki. Blok transakcji zaczyna się od linii z datą ISO; kwota to
    ostatnie wystąpienie 'N,NN PLN' w bloku; numer rachunku kontrahenta to
    ciąg 26 cyfr we własnej linii.
    """
    if main_account_id is None:
        raise ValueError("Wyciąg mBank dotyczy jednego konta — proszę wybrać konto docelowe przed importem.")

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
    resolve_ing_account_label w budget_service.py) — ING pokazuje w treści
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
    matched_ibans = {info['iban'] for info in accounts_info if info['matched']}
    is_multi_account = bool(account_entries)

    if not is_multi_account and main_account_id is None:
        raise ValueError("Plik PDF zawiera jedno konto — proszę wybrać konto docelowe przed importem.")

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

        # Pomiń stronę "wpływu" (+) przelewu wewnętrznego między śledzonymi
        # kontami w OBRĘBIE TEGO SAMEGO PLIKU (jak w CSV) — lustro powstanie
        # automatycznie przy zatwierdzeniu strony "wypływu" (-).
        if (is_multi_account and amount > 0 and counterparty_account
                and counterparty_account in ibans_set
                and counterparty_account in matched_ibans):
            skipped_count += 1
            continue

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
