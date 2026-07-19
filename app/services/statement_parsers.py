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
import io
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from bs4 import BeautifulSoup

from app.services.budget_service import _MBANK_ACCOUNT_RE

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_PERIOD_RE = re.compile(r'od\s*(\d{4}-\d{2}-\d{2})\s*do\s*(\d{4}-\d{2}-\d{2})')
_AMOUNT_PLN_RE = re.compile(r'(-?\d[\d \xa0]*,\d{2})\s*PLN')


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
