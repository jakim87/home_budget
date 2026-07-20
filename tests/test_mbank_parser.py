from decimal import Decimal
from datetime import date
import pytest
from app import db
from app.models import User, Account

from app.services.budget_service import parse_mbank_csv

# Próbka ZANONIMIZOWANA — zmyślone nazwiska, numery kont i kwoty.
# Zachowuje realną strukturę eksportu mBank (śmieciowy nagłówek, kolumny
# #Data operacji/#Opis operacji/#Rachunek/#Kategoria/#Kwota, kwota z sufiksem PLN
# i przecinkiem dziesiętnym, numer konta kontrahenta zaszyty w opisie).
MBANK_CSV = """mBank S.A. Bankowość Detaliczna;
\t\tSkrytka Pocztowa 2108;
\t\t90-959 Łódź 2;
\t\twww.mBank.pl;

#Klient;
JAN TESTOWY KOWALSKI;

Lista operacji;

#Za okres:;
01.06.2026;30.06.2026;

#zgodnie z wybranymi filtrami wyszukiwania;
      #dla rachunków:;
      Kowalski - 11111111111111111111111111;

      #Waluta;#Wpływy;#Wydatki;
PLN;440,00;-565,50;

#Data operacji;#Opis operacji;#Rachunek;#Kategoria;#Kwota;
2026-06-30;"FIRMA TESTOWA SP Z OO                       PRZELEW ZEWNĘTRZNY PRZYCHODZĄCY                    99888877776666555544443333  ";"Kowalski 1111 ... 1111";"Wpływy - inne";440,00 PLN;;
2026-06-25;"PRZELEW NA CELE                             PRZELEW WŁASNY                                     22222222222222222222222222  ";"Kowalski 1111 ... 1111";"Lokaty";-440,00 PLN;;
2026-06-01;"SKLEPIK TESTOWY WARSZAWA                    PŁATNOŚĆ KARTĄ                                     ";"Kowalski 1111 ... 1111";"Zakupy";-125,50 PLN;;


"""


@pytest.fixture
def mbank_user(app):
    """Użytkownik z jednym kontem docelowym dla importu mBank (jednokontowy)."""
    with app.app_context():
        user = User(username="mbank_user", email="mbank@user.com", password_hash="a")
        acc = Account(user=user, name="mBank ROR", bank_name="mBank",
                      account_number="PL11111111111111111111111111")
        db.session.add_all([user, acc])
        db.session.commit()
        return user.token, acc.id


def test_parse_mbank_csv_basic(app, mbank_user):
    """Poprawnie parsuje wiersze, pomija śmieciowy nagłówek, przypisuje wybrane konto."""
    user_token, acc_id = mbank_user
    with app.app_context():
        result = parse_mbank_csv(MBANK_CSV, user_token, main_account_id=acc_id)

    txs = result['transactions']
    assert len(txs) == 3
    assert all(t['account_id'] == acc_id for t in txs)
    assert result['skipped_count'] == 0


def test_parse_mbank_amounts_signs_and_decimals(app, mbank_user):
    """Kwoty: sufiks ' PLN' usunięty, przecinek → kropka, znak zachowany, Decimal."""
    user_token, acc_id = mbank_user
    with app.app_context():
        txs = parse_mbank_csv(MBANK_CSV, user_token, main_account_id=acc_id)['transactions']

    assert txs[0]['amount'] == Decimal("440.00")
    assert txs[1]['amount'] == Decimal("-440.00")
    assert txs[2]['amount'] == Decimal("-125.50")
    assert all(isinstance(t['amount'], Decimal) for t in txs)


def test_parse_mbank_date_and_polish_chars(app, mbank_user):
    """Data ISO parsowana; polskie znaki w tytule zachowane."""
    user_token, acc_id = mbank_user
    with app.app_context():
        txs = parse_mbank_csv(MBANK_CSV, user_token, main_account_id=acc_id)['transactions']

    assert txs[0]['date'] == date(2026, 6, 30)
    assert "ZEWNĘTRZNY" in txs[0]['title']
    assert "PŁATNOŚĆ" in txs[2]['title']


def test_parse_mbank_extracts_counterparty_account(app, mbank_user):
    """Numer konta kontrahenta (26 cyfr) wyciągnięty z opisu; brak → None."""
    user_token, acc_id = mbank_user
    with app.app_context():
        txs = parse_mbank_csv(MBANK_CSV, user_token, main_account_id=acc_id)['transactions']

    assert txs[0]['counterparty_account'] == "99888877776666555544443333"
    assert txs[1]['counterparty_account'] == "22222222222222222222222222"
    assert txs[2]['counterparty_account'] is None


def test_parse_mbank_title_whitespace_collapsed(app, mbank_user):
    """Wielokrotne spacje w opisie mBank są zwijane do pojedynczych — czytelny tytuł."""
    user_token, acc_id = mbank_user
    with app.app_context():
        txs = parse_mbank_csv(MBANK_CSV, user_token, main_account_id=acc_id)['transactions']

    assert "  " not in txs[0]['title']  # brak podwójnych spacji
    assert txs[0]['title'].startswith("FIRMA TESTOWA SP Z OO")


def test_parse_mbank_requires_account(app, mbank_user):
    """Plik jednokontowy bez wskazanego konta docelowego → ValueError."""
    user_token, _ = mbank_user
    with app.app_context():
        with pytest.raises(ValueError):
            parse_mbank_csv(MBANK_CSV, user_token, main_account_id=None)
