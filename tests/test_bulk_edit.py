"""Edycja zbiorcza transakcji — masowa zmiana kategorii i masowe usuwanie.

Dwie rzeczy, o które chodzi w tych testach:

1. Przelewy wewnętrzne. Usunięcie zabiera OBIE nogi (inaczej Net Worth się
   rozjeżdża), a masowa zmiana kategorii przelewy POMIJA — zmiana typu
   kategorii na inny niż 'transfer' zostawiłaby w bazie parę powiązaną przez
   linked_transaction_id, która przelewem już nie jest.
2. Cudze wiersze. Operacja zbiorcza to nowa powierzchnia na IDOR: jedno
   żądanie z listą ID. Obca pozycja na liście musi odrzucić CAŁĄ operację,
   a nie tylko siebie — inaczej można by po cichu skasować cudze dane
   i nigdy się o tym nie dowiedzieć.
"""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, Transaction, TransactionArchive
from app.services.budget_service import create_transaction
from app.services.transaction_service import bulk_delete_transactions, bulk_update_category


@pytest.fixture
def dane(app, test_user):
    """Konto z trzema zwykłymi transakcjami + kategorie zwykłe."""
    konto = Account(name="ROR", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user.token)
    zakupy = Category(name="Zakupy", type="expense")
    rachunki = Category(name="Rachunki", type="expense")
    db.session.add_all([konto, zakupy, rachunki])
    db.session.commit()

    txs = [
        create_transaction(test_user.token, konto.id, Decimal("-100.00"), f"Zakup {i}",
                           date(2026, 1, 10 + i), category_id=zakupy.id)
        for i in range(3)
    ]
    return test_user.token, konto, zakupy, rachunki, txs


@pytest.fixture
def przelew(app, test_user, dane):
    """Przelew wewnętrzny: dwie powiązane nogi na dwóch kontach."""
    token, konto_a, _, _, _ = dane
    konto_b = Account(name="Oszczędnościowe", bank_name="Bank", balance=Decimal("0.00"), user_token=token)
    kat = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add_all([konto_b, kat])
    db.session.commit()
    kontrahent = Contractor(name="Moje konto: Oszczędnościowe", user_token=token,
                            default_category_id=kat.id, linked_account_id=konto_b.id)
    db.session.add(kontrahent)
    db.session.commit()

    noga = create_transaction(token, konto_a.id, Decimal("500.00"), "Przelew na oszczędności",
                              date(2026, 1, 20), category_id=kat.id, contractor_id=kontrahent.id)
    db.session.refresh(noga)
    assert noga.linked_transaction_id is not None, "fixture wymaga sparowanego przelewu"
    return noga, konto_b, kat


# --- masowa zmiana kategorii ---

def test_zmiana_kategorii_obejmuje_wszystkie_wskazane(app, dane):
    token, _, _, rachunki, txs = dane

    wynik = bulk_update_category(token, [t.id for t in txs], "Rachunki")

    assert wynik['zmienione'] == 3
    assert wynik['pominiete_przelewy'] == 0
    for t in txs:
        db.session.refresh(t)
        assert t.category_id == rachunki.id


def test_zmiana_kategorii_pomija_przelewy_i_je_zglasza(app, dane, przelew):
    """Przelew zostaje nietknięty, reszta zaznaczenia zmieniona."""
    token, _, _, rachunki, txs = dane
    noga, _, kat_transfer = przelew

    wynik = bulk_update_category(token, [txs[0].id, noga.id], "Rachunki")

    assert wynik['zmienione'] == 1
    assert wynik['pominiete_przelewy'] == 1

    db.session.refresh(txs[0])
    db.session.refresh(noga)
    assert txs[0].category_id == rachunki.id
    assert noga.category_id == kat_transfer.id, "przelew nie mógł zmienić kategorii"
    assert noga.linked_transaction_id is not None, "parowanie przelewu musi zostać nienaruszone"


def test_nie_mozna_zbiorczo_ustawic_kategorii_przelewu(app, dane, przelew):
    token, _, _, _, txs = dane

    with pytest.raises(ValueError):
        bulk_update_category(token, [t.id for t in txs], "Przelew wewnętrzny")

    for t in txs:
        db.session.refresh(t)
        assert t.category.type == "expense", "żadna transakcja nie mogła zostać zmieniona"


def test_zmiana_kategorii_na_nieistniejaca_odrzucona(app, dane):
    token, _, zakupy, _, txs = dane

    with pytest.raises(ValueError):
        bulk_update_category(token, [t.id for t in txs], "Kategoria Której Nie Ma")

    db.session.refresh(txs[0])
    assert txs[0].category_id == zakupy.id


def test_zmiana_kategorii_cudzej_transakcji_odrzuca_cala_operacje(app, dane, other_user):
    """Jeden obcy ID unieważnia całe żądanie — także własne pozycje z listy."""
    token, _, zakupy, _, txs = dane
    obce_konto = Account(name="Obce", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    db.session.add(obce_konto)
    db.session.commit()
    obca = create_transaction(other_user.token, obce_konto.id, Decimal("-50.00"), "Nie moje",
                              date(2026, 1, 5), category_id=zakupy.id)

    with pytest.raises(ValueError):
        bulk_update_category(token, [txs[0].id, obca.id], "Rachunki")

    db.session.refresh(txs[0])
    db.session.refresh(obca)
    assert txs[0].category_id == zakupy.id, "własna transakcja też nie mogła się zmienić"
    assert obca.category_id == zakupy.id


# --- masowe usuwanie ---

def test_usuwanie_zbiorcze_archiwizuje_i_koryguje_saldo(app, dane):
    token, konto, _, _, txs = dane
    saldo_przed = konto.balance

    wynik = bulk_delete_transactions(token, [txs[0].id, txs[1].id])

    assert wynik['usuniete'] == 2
    assert db.session.query(Transaction).filter(Transaction.id.in_([txs[0].id, txs[1].id])).count() == 0
    assert db.session.query(TransactionArchive).count() == 2

    db.session.refresh(konto)
    # Dwie transakcje po -100 zł: cofnięcie ich podnosi saldo o 200 zł.
    assert konto.balance == saldo_przed + Decimal("200.00")


def test_usuniecie_jednej_nogi_przelewu_zabiera_druga(app, dane, przelew):
    token, _, _, _, _ = dane
    noga, _, _ = przelew
    id_lustra = noga.linked_transaction_id

    wynik = bulk_delete_transactions(token, [noga.id])

    assert wynik['usuniete'] == 2
    assert wynik['drugie_nogi'] == 1, "druga noga dołożona automatycznie musi być zgłoszona"
    assert db.session.get(Transaction, id_lustra) is None


def test_zaznaczenie_obu_nog_nie_liczy_ich_podwojnie(app, dane, przelew):
    """Obie nogi na liście — usunięcie ma się wykonać raz, bez błędu."""
    token, _, _, _, _ = dane
    noga, _, _ = przelew
    id_lustra = noga.linked_transaction_id

    wynik = bulk_delete_transactions(token, [noga.id, id_lustra])

    assert wynik['usuniete'] == 2
    assert wynik['drugie_nogi'] == 0, "nic nie zostało dołożone — obie nogi wskazał użytkownik"
    assert db.session.query(Transaction).count() == 3  # zostały trzy zwykłe


def test_usuwanie_cudzej_transakcji_odrzuca_cala_operacje(app, dane, other_user):
    token, konto, zakupy, _, txs = dane
    obce_konto = Account(name="Obce", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    db.session.add(obce_konto)
    db.session.commit()
    obca = create_transaction(other_user.token, obce_konto.id, Decimal("-50.00"), "Nie moje",
                              date(2026, 1, 5), category_id=zakupy.id)
    saldo_przed = konto.balance

    with pytest.raises(ValueError):
        bulk_delete_transactions(token, [txs[0].id, obca.id])

    assert db.session.get(Transaction, txs[0].id) is not None, "własna transakcja musi przetrwać"
    assert db.session.get(Transaction, obca.id) is not None
    assert db.session.query(TransactionArchive).count() == 0
    db.session.refresh(konto)
    assert konto.balance == saldo_przed, "saldo nie mogło drgnąć"


def test_pusta_lista_odrzucona(app, dane):
    token, _, _, _, _ = dane
    with pytest.raises(ValueError):
        bulk_delete_transactions(token, [])
    with pytest.raises(ValueError):
        bulk_update_category(token, [], "Rachunki")
