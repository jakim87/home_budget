"""Model transferów oparty na POKRYCIU wyciągami.

Reguła: jeśli konto docelowe dostaje własne wyciągi, druga noga przelewu przyjdzie
realnie z tego wyciągu — lustra generować NIE wolno (podwójne liczenie). Jeśli konto
nie ma własnych wyciągów (np. cel oszczędnościowy), lustro jest jedynym źródłem
drugiej strony i powstaje jak dotąd.

Noga bez pary zostaje widoczna jako niepowiązana (linked_transaction_id IS NULL)
— to jest "wiersz do zmapowania", który domknie się sam, gdy przyjdzie druga strona.
"""
from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Account, Category, Contractor, Transaction
from app.services.budget_service import create_transaction
from app.services.import_history_service import record_statement_import


@pytest.fixture
def two_accounts(app, test_user):
    """Konta A i B + kategoria transferowa + kontrahenci w obie strony."""
    acc_a = Account(name="Konto A", bank_name="mBank", balance=Decimal("1000.00"),
                    user_token=test_user.token)
    acc_b = Account(name="Konto B", bank_name="ING", balance=Decimal("500.00"),
                    user_token=test_user.token)
    cat = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add_all([acc_a, acc_b, cat])
    db.session.commit()

    cont_to_b = Contractor(name="Moje konto: Konto B", user_token=test_user.token,
                           default_category_id=cat.id, linked_account_id=acc_b.id)
    cont_to_a = Contractor(name="Moje konto: Konto A", user_token=test_user.token,
                           default_category_id=cat.id, linked_account_id=acc_a.id)
    db.session.add_all([cont_to_b, cont_to_a])
    db.session.commit()
    return test_user.token, acc_a, acc_b, cat, cont_to_b, cont_to_a


def _mark_has_statements(token, account_id, name="wyciag.csv"):
    """Oznacza konto jako dostające własne wyciągi (sygnał pokrycia)."""
    record_statement_import(
        user_token=token, filename=name, bank="mbank", file_format="csv",
        account_id=account_id, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
        transaction_count=1, skipped_count=0, batch_id="batch-test",
    )


def test_no_mirror_when_destination_has_own_statements(app, two_accounts):
    """Konto docelowe ma własne wyciągi → lustro NIE powstaje (druga noga przyjdzie realnie)."""
    token, acc_a, acc_b, cat, cont_to_b, _ = two_accounts
    _mark_has_statements(token, acc_b.id)

    tx = create_transaction(token, acc_a.id, Decimal("-300.00"), "Przelew A→B",
                            date(2026, 6, 10), category_id=cat.id, contractor_id=cont_to_b.id,
                            preserve_sign=True)

    assert db.session.query(Transaction).filter_by(account_id=acc_b.id).count() == 0
    assert tx.linked_transaction_id is None, "noga bez pary zostaje niepowiązana (do zmapowania)"
    # Saldo konta docelowego nietknięte — zmieni je dopiero jego własny wyciąg.
    assert db.session.get(Account, acc_b.id).balance == Decimal("500.00")
    assert db.session.get(Account, acc_a.id).balance == Decimal("700.00")


def test_mirror_still_created_when_destination_has_no_statements(app, two_accounts):
    """Konto docelowe bez własnych wyciągów → lustro powstaje jak dotąd."""
    token, acc_a, acc_b, cat, cont_to_b, _ = two_accounts

    tx = create_transaction(token, acc_a.id, Decimal("-300.00"), "Przelew A→B",
                            date(2026, 6, 10), category_id=cat.id, contractor_id=cont_to_b.id,
                            preserve_sign=True)

    mirror = db.session.query(Transaction).filter_by(account_id=acc_b.id).one()
    assert mirror.amount == Decimal("300.00")
    assert mirror.linked_transaction_id == tx.id
    assert tx.linked_transaction_id == mirror.id
    assert db.session.get(Account, acc_b.id).balance == Decimal("800.00")


def test_both_real_legs_link_without_duplication(app, two_accounts):
    """Obie nogi z realnych wyciągów: powstają DWIE transakcje, powiązane, salda poprawne."""
    token, acc_a, acc_b, cat, cont_to_b, cont_to_a = two_accounts
    _mark_has_statements(token, acc_a.id, "a.csv")
    _mark_has_statements(token, acc_b.id, "b.csv")

    outflow = create_transaction(token, acc_a.id, Decimal("-300.00"), "Przelew A→B",
                                 date(2026, 6, 10), category_id=cat.id, contractor_id=cont_to_b.id,
                                 preserve_sign=True)
    inflow = create_transaction(token, acc_b.id, Decimal("300.00"), "Przelew A→B",
                                date(2026, 6, 10), category_id=cat.id, contractor_id=cont_to_a.id,
                                preserve_sign=True)

    assert db.session.query(Transaction).count() == 2, "żadnego sztucznego lustra"
    assert outflow.linked_transaction_id == inflow.id
    assert inflow.linked_transaction_id == outflow.id
    assert db.session.get(Account, acc_a.id).balance == Decimal("700.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("800.00")


def test_imported_inflow_leg_keeps_positive_sign(app, two_accounts):
    """Zaimportowana noga wpływu (+) NIE jest wymuszana na wypływ — wyciąg jest źródłem prawdy."""
    token, acc_a, acc_b, cat, _, cont_to_a = two_accounts
    _mark_has_statements(token, acc_a.id)

    inflow = create_transaction(token, acc_b.id, Decimal("300.00"), "Wpływ z A",
                                date(2026, 6, 10), category_id=cat.id, contractor_id=cont_to_a.id,
                                preserve_sign=True)

    assert inflow.amount == Decimal("300.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("800.00")


def test_legs_link_despite_booking_date_difference(app, two_accounts):
    """Różnica dat księgowania między bankami (2 dni) nie przeszkadza w powiązaniu nóg."""
    token, acc_a, acc_b, cat, cont_to_b, cont_to_a = two_accounts
    _mark_has_statements(token, acc_a.id, "a.csv")
    _mark_has_statements(token, acc_b.id, "b.csv")

    outflow = create_transaction(token, acc_a.id, Decimal("-300.00"), "Przelew A→B",
                                 date(2026, 6, 30), category_id=cat.id, contractor_id=cont_to_b.id,
                                 preserve_sign=True)
    inflow = create_transaction(token, acc_b.id, Decimal("300.00"), "Przelew A→B",
                                date(2026, 7, 2), category_id=cat.id, contractor_id=cont_to_a.id,
                                preserve_sign=True)

    assert outflow.linked_transaction_id == inflow.id
    assert inflow.linked_transaction_id == outflow.id
    assert db.session.query(Transaction).count() == 2


def test_unrelated_transaction_of_same_amount_is_not_linked(app, two_accounts):
    """Zwykły wpływ o tej samej kwocie (bez kontrahenta wskazującego na konto źródłowe)
    nie zostaje błędnie potraktowany jako druga noga przelewu."""
    token, acc_a, acc_b, cat, cont_to_b, _ = two_accounts
    _mark_has_statements(token, acc_b.id)
    zwykly = Category(name="Wynagrodzenie", type="income")
    db.session.add(zwykly)
    db.session.commit()

    obcy = create_transaction(token, acc_b.id, Decimal("300.00"), "Wypłata",
                              date(2026, 6, 10), category_id=zwykly.id, preserve_sign=True)
    outflow = create_transaction(token, acc_a.id, Decimal("-300.00"), "Przelew A→B",
                                 date(2026, 6, 10), category_id=cat.id, contractor_id=cont_to_b.id,
                                 preserve_sign=True)

    assert outflow.linked_transaction_id is None
    assert obcy.linked_transaction_id is None
