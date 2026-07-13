"""Przypadki brzegowe przelewów wewnętrznych ("Moje konto: {nazwa}").
Uzupełnia test_data_integrity.py (dedup luster, powiązanie po linked_account_id)
o scenariusze awaryjne: brak konta docelowego, fallback po nazwie, duplikaty nazw,
wymuszanie znaku i selektywne kasowanie stagingu."""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, Transaction, TransactionStaging
from app.services.budget_service import create_transaction


@pytest.fixture
def transfer_setup(app, test_user):
    """Konta A/B + kategoria transferowa + kontrahent transferowy A→B (z linkiem)."""
    acc_a = Account(name="Konto A", bank_name="Bank", balance=Decimal("2000.00"), user_token=test_user.token)
    acc_b = Account(name="Konto B", bank_name="Bank", balance=Decimal("0.00"), user_token=test_user.token)
    cat = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add_all([acc_a, acc_b, cat])
    db.session.commit()
    cont_to_b = Contractor(name="Moje konto: Konto B", user_token=test_user.token,
                           default_category_id=cat.id, linked_account_id=acc_b.id)
    db.session.add(cont_to_b)
    db.session.commit()
    return test_user.token, acc_a, acc_b, cat, cont_to_b


def test_transfer_without_destination_is_one_sided(app, test_user, transfer_setup):
    """Kontrahent wskazuje na nieistniejące konto — wypływ powstaje, lustra brak, bez wyjątku."""
    token, acc_a, acc_b, cat, _ = transfer_setup
    ghost = Contractor(name="Moje konto: Nieistniejące", user_token=token, default_category_id=cat.id)
    db.session.add(ghost)
    db.session.commit()

    tx = create_transaction(token, acc_a.id, Decimal("300.00"), "Przelew donikąd",
                            date(2024, 4, 1), category_id=cat.id, contractor_id=ghost.id)

    assert tx.amount == Decimal("-300.00")  # znak wymuszony mimo braku lustra
    assert db.session.query(Transaction).count() == 1
    assert db.session.get(Account, acc_a.id).balance == Decimal("1700.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("0.00")


def test_transfer_fallback_by_name_without_link(app, test_user, transfer_setup):
    """Stary kontrahent bez linked_account_id — dopasowanie po nazwie nadal tworzy lustro."""
    token, acc_a, acc_b, cat, cont_to_b = transfer_setup
    cont_to_b.linked_account_id = None
    db.session.commit()

    create_transaction(token, acc_a.id, Decimal("100.00"), "Przelew po nazwie",
                       date(2024, 4, 2), category_id=cat.id, contractor_id=cont_to_b.id)

    mirrors = db.session.query(Transaction).filter_by(account_id=acc_b.id).all()
    assert len(mirrors) == 1
    assert mirrors[0].amount == Decimal("100.00")
    assert db.session.get(Account, acc_b.id).balance == Decimal("100.00")


def test_transfer_ambiguous_account_name_skips_mirror(app, test_user, transfer_setup):
    """Dwa aktywne konta o tej samej nazwie i brak linku — nie zgadujemy, lustro pominięte."""
    token, acc_a, _, cat, _ = transfer_setup
    twin1 = Account(name="Bliźniak", bank_name="Bank", balance=Decimal("0.00"), user_token=token)
    twin2 = Account(name="Bliźniak", bank_name="Bank", balance=Decimal("0.00"), user_token=token)
    cont = Contractor(name="Moje konto: Bliźniak", user_token=token, default_category_id=cat.id)
    db.session.add_all([twin1, twin2, cont])
    db.session.commit()

    create_transaction(token, acc_a.id, Decimal("50.00"), "Przelew niejednoznaczny",
                       date(2024, 4, 3), category_id=cat.id, contractor_id=cont.id)

    assert db.session.query(Transaction).filter_by(account_id=twin1.id).count() == 0
    assert db.session.query(Transaction).filter_by(account_id=twin2.id).count() == 0
    assert db.session.get(Account, twin1.id).balance == Decimal("0.00")
    assert db.session.get(Account, twin2.id).balance == Decimal("0.00")


def test_transfer_coerces_positive_amount_to_outflow(app, test_user, transfer_setup):
    """Kwota dodatnia z kategorią transferową → strona źródłowa zapisana jako wypływ (-)."""
    token, acc_a, acc_b, cat, cont_to_b = transfer_setup

    tx = create_transaction(token, acc_a.id, Decimal("250.00"), "Przelew dodatni",
                            date(2024, 4, 4), category_id=cat.id, contractor_id=cont_to_b.id)

    assert tx.amount == Decimal("-250.00")
    assert db.session.get(Account, acc_a.id).balance == Decimal("1750.00")
    mirror = db.session.query(Transaction).filter_by(account_id=acc_b.id).one()
    assert mirror.amount == Decimal("250.00")
    assert mirror.linked_transaction_id == tx.id
    assert tx.linked_transaction_id == mirror.id


def test_transfer_deletes_only_matching_staging_row(app, test_user, transfer_setup):
    """Lustro kasuje TYLKO wiersz stagingu wskazujący na konto źródłowe — nie przypadkowy
    wpływ o tej samej kwocie i dacie."""
    token, acc_a, acc_b, cat, cont_to_b = transfer_setup
    # Kontrahent reprezentujący konto źródłowe (A) — na niego wskazuje staging strony wpływu
    cont_from_a = Contractor(name="Moje konto: Konto A", user_token=token,
                             default_category_id=cat.id, linked_account_id=acc_a.id)
    db.session.add(cont_from_a)
    db.session.commit()

    matching = TransactionStaging(date=date(2024, 4, 5), amount=Decimal("500.00"), title="Przelew",
                                  status="pending", user_token=token, account_id=acc_b.id,
                                  proposed_contractor_id=cont_from_a.id)
    unrelated = TransactionStaging(date=date(2024, 4, 5), amount=Decimal("500.00"), title="Zwrot od kolegi",
                                   status="pending", user_token=token, account_id=acc_b.id)
    db.session.add_all([matching, unrelated])
    db.session.commit()
    matching_id, unrelated_id = matching.id, unrelated.id

    create_transaction(token, acc_a.id, Decimal("500.00"), "Przelew",
                       date(2024, 4, 5), category_id=cat.id, contractor_id=cont_to_b.id)

    assert db.session.get(TransactionStaging, matching_id) is None      # skonsumowany przez lustro
    assert db.session.get(TransactionStaging, unrelated_id) is not None  # nietknięty


def test_transfer_source_contractor_gets_created_and_linked(app, test_user, transfer_setup):
    """Przy pierwszym przelewie A→B powstaje kontrahent 'Moje konto: Konto A'
    z twardym powiązaniem linked_account_id — widoczny na transakcji lustrzanej."""
    token, acc_a, acc_b, cat, cont_to_b = transfer_setup

    create_transaction(token, acc_a.id, Decimal("75.00"), "Pierwszy przelew",
                       date(2024, 4, 6), category_id=cat.id, contractor_id=cont_to_b.id)

    source_cont = db.session.query(Contractor).filter_by(user_token=token, name="Moje konto: Konto A").one()
    assert source_cont.linked_account_id == acc_a.id
    mirror = db.session.query(Transaction).filter_by(account_id=acc_b.id).one()
    assert mirror.contractor_id == source_cont.id
