"""Kategoria nadana przez bank jako podpowiedź w poczekalni (#192).

Dopasowanie wyłącznie po nazwie istniejącej kategorii; brak odpowiednika = brak
podpowiedzi. Reguły kontrahenta i przelewy wewnętrzne mają pierwszeństwo.
"""
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, TransactionStaging
from app.services.budget_service import reanalyze_all_staging, save_transactions_to_staging


def _tx(bank_category, amount="-10.00", contractor="SKLEP NIEZNANY", **extra):
    return {'date': date(2026, 9, 1), 'amount': Decimal(amount), 'title': f'op {bank_category} {amount}',
            'contractor': contractor, 'account_id': None, 'counterparty_account': None,
            'bank_category': bank_category, **extra}


def _cat(user_token, name, type_='expense'):
    c = Category(name=name, type=type_, user_token=user_token)
    db.session.add(c)
    db.session.commit()
    return c


def _stage(user_token, tx):
    return save_transactions_to_staging([tx], user_token=user_token)[0]


def test_kategoria_banku_dopasowana_po_nazwie_bez_wielkosci_liter(app, test_user_token):
    paliwo = _cat(test_user_token, "paliwo")
    stg = _stage(test_user_token, _tx("Paliwo"))
    assert stg.proposed_category_id == paliwo.id
    assert stg.bank_category == "Paliwo"


def test_brak_odpowiednika_to_brak_podpowiedzi(app, test_user_token):
    stg = _stage(test_user_token, _tx("Gazety lub czasopisma"))
    assert stg.proposed_category_id is None
    assert stg.bank_category == "Gazety lub czasopisma"


def test_typ_kategorii_zgodny_ze_znakiem_kwoty(app, test_user_token):
    """Ta sama nazwa jako przychód i wydatek — wpływ dostaje przychód, wydatek wydatek."""
    wydatek = _cat(test_user_token, "Inne", 'expense')
    przychod = _cat(test_user_token, "Inne", 'income')
    assert _stage(test_user_token, _tx("Inne", "-5.00")).proposed_category_id == wydatek.id
    assert _stage(test_user_token, _tx("Inne", "5.00")).proposed_category_id == przychod.id


def test_kategoria_przelewu_nie_jest_podpowiadana(app, test_user_token):
    """Kategoria banku nie może oznaczyć operacji jako przelewu wewnętrznego."""
    _cat(test_user_token, "Przelew wewnętrzny", 'transfer')
    assert _stage(test_user_token, _tx("Przelew wewnętrzny")).proposed_category_id is None


def test_regula_kontrahenta_wygrywa_z_kategoria_banku(app, test_user_token):
    zakupy = _cat(test_user_token, "Zakupy")
    _cat(test_user_token, "Paliwo")
    db.session.add(Contractor(name="ORLEN", default_category_id=zakupy.id, user_token=test_user_token))
    db.session.commit()
    stg = _stage(test_user_token, _tx("Paliwo", contractor="ORLEN WARSZAWA"))
    assert stg.proposed_category_id == zakupy.id


def test_kontrahent_bez_kategorii_domyslnej_dostaje_kategorie_banku(app, test_user_token):
    paliwo = _cat(test_user_token, "Paliwo")
    orlen = Contractor(name="ORLEN", user_token=test_user_token)
    db.session.add(orlen)
    db.session.commit()
    stg = _stage(test_user_token, _tx("Paliwo", contractor="ORLEN WARSZAWA"))
    assert (stg.proposed_contractor_id, stg.proposed_category_id) == (orlen.id, paliwo.id)


def test_przelew_wewnetrzny_wygrywa_z_kategoria_banku(app, test_user_token):
    _cat(test_user_token, "Paliwo")
    db.session.add(Account(name="Oszczędności", bank_name="ING", user_token=test_user_token,
                           account_number="11111111111111111111111111"))
    db.session.commit()
    stg = _stage(test_user_token, _tx("Paliwo", counterparty_account="11111111111111111111111111"))
    assert db.session.get(Category, stg.proposed_category_id).type == 'transfer'


def test_reanaliza_dopasowuje_kategorie_dodana_po_imporcie(app, test_user_token):
    stg = _stage(test_user_token, _tx("Paliwo"))
    assert stg.proposed_category_id is None
    paliwo = _cat(test_user_token, "Paliwo")
    reanalyze_all_staging(test_user_token)
    assert db.session.get(TransactionStaging, stg.id).proposed_category_id == paliwo.id
