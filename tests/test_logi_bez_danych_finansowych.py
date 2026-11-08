"""Logi bez danych finansowych (audyt 2026-11-08, pkt 7; reguła A10).

Polityka prywatności wymienia w logach tylko żądanie, status, czas, użytkownika
i IP. Kwoty, nazwy kont i kategorii oraz surowe pola wyciągu to dane finansowe —
do logu trafiają wyłącznie identyfikatory.
"""
import logging
from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Account, Category, Contractor, TransactionStaging
from app.services import budget_plan_service
from app.services.budget_service import approve_staging_record, create_transaction
from app.services.statement_parsers import parse_mbank_csv
from app.services.import_history_service import record_statement_import
from app.services.transaction_service import bulk_update_category


@pytest.fixture
def logi(caplog):
    caplog.set_level(logging.DEBUG, logger='app')
    return caplog


def _w_logach(caplog, *frazy):
    tekst = "\n".join(r.getMessage() for r in caplog.records)
    return [f for f in frazy if f in tekst]


@pytest.fixture
def konto(app, test_user_token):
    a = Account(name="Skarbonka Zielona", bank_name="Bank", balance=Decimal("0.00"),
                user_token=test_user_token)
    db.session.add(a)
    db.session.commit()
    return a


def test_zatwierdzenie_poczekalni_nie_loguje_kwoty(logi, test_user_token, konto):
    sklep = Contractor(name="Sklep", user_token=test_user_token)
    kat = Category(name="Zakupy", type="expense")
    stg = TransactionStaging(date=date(2026, 11, 2), amount=Decimal("-4321.09"), title="Zakup",
                             status="pending", user_token=test_user_token, account_id=konto.id)
    db.session.add_all([sklep, kat, stg])
    db.session.commit()

    approve_staging_record(test_user_token, stg.id, {'category': 'Zakupy', 'contractor_id': sklep.id})

    assert _w_logach(logi, "4321") == []


def test_plan_budzetu_nie_loguje_nazwy_kategorii_ani_kwoty(logi, app, test_user_token):
    kat = Category(name="Wakacje Bali", type="expense", user_token=test_user_token)
    db.session.add(kat)
    db.session.commit()

    budget_plan_service.ustaw_plan(test_user_token, 2026, 11, kat.id, Decimal("7777.77"))

    assert _w_logach(logi, "Wakacje Bali", "7777") == []


def test_zbiorcza_zmiana_kategorii_nie_loguje_nazwy(logi, test_user_token, konto):
    kat = Category(name="Wakacje Bali", type="expense", user_token=test_user_token)
    db.session.add(kat)
    db.session.commit()
    tx = create_transaction(test_user_token, konto.id, Decimal("-1.00"), "x", date(2026, 11, 1))

    bulk_update_category(test_user_token, [tx.id], "Wakacje Bali")

    assert _w_logach(logi, "Wakacje Bali") == []


def test_parser_mbank_nie_loguje_surowej_kwoty_ani_daty(logi, test_user_token, konto):
    csv = (
        "#Data operacji;#Opis operacji;#Rachunek;#Kategoria;#Kwota;\n"
        "2026-06-30;\"SKLEP\";\"Konto\";\"Zakupy\";98x76 PLN;;\n"
        "31/06/2026;\"SKLEP\";\"Konto\";\"Zakupy\";-12,00 PLN;;\n"
    )
    parse_mbank_csv(csv, test_user_token, main_account_id=konto.id)

    assert _w_logach(logi, "98x76", "31/06/2026") == []


def _przelew_na(test_user_token, zrodlo, cel):
    przelew = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add(przelew)
    db.session.commit()
    kontrahent = Contractor(name=f"Moje konto: {cel.name}", user_token=test_user_token,
                            default_category_id=przelew.id, linked_account_id=cel.id)
    db.session.add(kontrahent)
    db.session.commit()
    return create_transaction(test_user_token, zrodlo.id, Decimal("300.00"), "Na cel",
                              date(2026, 11, 1), category_id=przelew.id, contractor_id=kontrahent.id)


def test_przelew_na_konto_z_wyciagami_nie_loguje_nazwy_konta(logi, test_user_token, konto):
    cel = Account(name="Konto Tajne", bank_name="Bank", balance=Decimal("0.00"), user_token=test_user_token)
    db.session.add(cel)
    db.session.commit()
    record_statement_import(
        user_token=test_user_token, filename="c.csv", bank="ing", file_format="csv",
        account_id=cel.id, period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
        transaction_count=1, skipped_count=0, batch_id="batch-c",
    )

    _przelew_na(test_user_token, konto, cel)

    assert _w_logach(logi, "Konto Tajne", "Skarbonka Zielona") == []


def test_niejednoznaczna_nazwa_konta_nie_trafia_do_logu(logi, test_user_token, konto):
    """Kontrahent bez powiązania, dwa konta o tej samej nazwie — ostrzeżenie bez nazwy."""
    dwa = [Account(name="Konto Tajne", bank_name=b, balance=Decimal("0.00"), user_token=test_user_token)
           for b in ("Bank 1", "Bank 2")]
    db.session.add_all(dwa)
    przelew = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add(przelew)
    db.session.commit()
    kontrahent = Contractor(name="Moje konto: Konto Tajne", user_token=test_user_token,
                            default_category_id=przelew.id)
    db.session.add(kontrahent)
    db.session.commit()

    create_transaction(test_user_token, konto.id, Decimal("300.00"), "Na cel",
                       date(2026, 11, 1), category_id=przelew.id, contractor_id=kontrahent.id)

    assert logi.records, "ostrzeżenie o niejednoznacznej nazwie powinno powstać"
    assert _w_logach(logi, "Konto Tajne") == []
