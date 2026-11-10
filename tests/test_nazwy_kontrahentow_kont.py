"""Nazwy kontrahentów przelewów wewnętrznych („Moje konto: X”) po zmianie nazwy konta.

Kontrahent niesie nazwę konta, do którego prowadzi przelew. Zmiana nazwy konta ma ją zmienić
razem z nim, a gdy z historii zostało dwóch kontrahentów jednego konta, aplikacja wybiera
między nimi zawsze tak samo: aktywny przed wyłączonym, potem najniższe id. Dane sprzed tej
poprawki wyrównuje komenda `flask fix-transfer-contractors`.
"""
import logging
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, Transaction
from app.services.account_service import update_account
from app.services.budget_service import _internal_transfer_proposal, create_transaction


def _konto(token, nazwa):
    konto = Account(name=nazwa, bank_name="Bank", balance=Decimal("0.00"), user_token=token)
    db.session.add(konto)
    db.session.commit()
    return konto


def _kontrahent(token, nazwa, konto=None, aktywny=True):
    kontrahent = Contractor(name=nazwa, user_token=token, is_active=aktywny,
                            linked_account_id=konto.id if konto else None)
    db.session.add(kontrahent)
    db.session.commit()
    return kontrahent


# --- Zmiana nazwy konta przemianowuje jego kontrahenta ---

def test_zmiana_nazwy_konta_przemianowuje_kontrahenta_przelewow(logged_in_client, test_user):
    """Po zmianie nazwy konta jego kontrahent nie zostaje z „Moje konto: <stara nazwa>”."""
    konto = _konto(test_user.token, "Wakacje")
    kontrahent = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)

    resp = logged_in_client.put(f'/api/accounts/{konto.id}', json={'name': 'Wakacje 2027'})

    assert resp.status_code == 200
    db.session.expire_all()
    po_zmianie = db.session.get(Contractor, kontrahent.id)
    assert po_zmianie.name == "Moje konto: Wakacje 2027"
    assert po_zmianie.linked_account_id == konto.id
    assert db.session.query(Contractor).filter_by(user_token=test_user.token).count() == 1


def test_zmiana_nazwy_konta_przemianowuje_tez_wylaczonego_kontrahenta(app, test_user):
    konto = _konto(test_user.token, "Wakacje")
    wylaczony = _kontrahent(test_user.token, "Moje konto: Wakacje", konto, aktywny=False)

    update_account(test_user.token, konto.id, {'name': 'Wakacje 2027'})

    assert wylaczony.name == "Moje konto: Wakacje 2027"
    assert wylaczony.is_active is False


def test_zmiana_nazwy_konta_nie_rusza_nazw_ustawionych_inaczej(app, test_user, other_user):
    token = test_user.token
    konto, inne_konto = _konto(token, "Wakacje"), _konto(token, "Inne")
    wlasna_nazwa = _kontrahent(token, "Skarbonka na wakacje", konto)
    inne_powiazanie = _kontrahent(token, "Moje konto: Wakacje", inne_konto)
    bez_powiazania = _kontrahent(token, "Moje konto: Wakacje")
    # Błąd danych: kontrahent innego użytkownika powiązany z naszym kontem. Zakres po
    # user_token jest jedyną barierą przed dopisaniem naszej nazwy do cudzych danych.
    cudzy = _kontrahent(other_user.token, "Moje konto: Wakacje", konto)

    update_account(token, konto.id, {'name': 'Wakacje 2027'})

    assert wlasna_nazwa.name == "Skarbonka na wakacje"
    assert inne_powiazanie.name == "Moje konto: Wakacje"
    assert bez_powiazania.name == "Moje konto: Wakacje"
    assert cudzy.name == "Moje konto: Wakacje"


def test_kolizja_z_aktywnym_kontrahentem_zostawia_stara_nazwe(app, test_user, caplog):
    """Dwóch aktywnych kontrahentów o jednej nazwie to pułapka: pole kontrahenta wybiera po
    nazwie, więc przelew mógłby trafić na tego, który nie jest powiązany z kontem (#215).
    Zmiana nazwy konta przechodzi, a jego kontrahent zostaje przy starej nazwie."""
    caplog.set_level(logging.WARNING, logger='app')
    konto = _konto(test_user.token, "Skarbonka Stara")
    swoj = _kontrahent(test_user.token, "Moje konto: Skarbonka Stara", konto)
    zajmujacy = _kontrahent(test_user.token, "Moje konto: Skarbonka Nowa")

    po_zmianie = update_account(test_user.token, konto.id, {'name': 'Skarbonka Nowa'})

    assert po_zmianie.name == "Skarbonka Nowa"
    assert swoj.name == "Moje konto: Skarbonka Stara"
    assert zajmujacy.name == "Moje konto: Skarbonka Nowa"
    assert caplog.records, "pominięcie przemianowania powinno zostawić ślad w logu"
    assert "Skarbonka" not in "\n".join(r.getMessage() for r in caplog.records)  # tylko identyfikatory (A10)


def test_wylaczony_kontrahent_o_nowej_nazwie_nie_blokuje_przemianowania(app, test_user):
    konto = _konto(test_user.token, "Wakacje")
    swoj = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)
    _kontrahent(test_user.token, "Moje konto: Wakacje 2027", aktywny=False)

    update_account(test_user.token, konto.id, {'name': 'Wakacje 2027'})

    assert swoj.name == "Moje konto: Wakacje 2027"


def test_kontrahent_innego_uzytkownika_o_nowej_nazwie_nie_jest_kolizja(app, test_user, other_user):
    konto = _konto(test_user.token, "Wakacje")
    swoj = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)
    _kontrahent(other_user.token, "Moje konto: Wakacje 2027")

    update_account(test_user.token, konto.id, {'name': 'Wakacje 2027'})

    assert swoj.name == "Moje konto: Wakacje 2027"


def test_za_dluga_nazwa_kontrahenta_nie_blokuje_zmiany_nazwy_konta(app, test_user):
    """Konto może mieć nazwę do 100 znaków, a kontrahent razem z prefiksem „Moje konto: ” też
    mieści się tylko w 100. Przekroczenie dałoby błąd bazy i zablokowało zmianę nazwy konta."""
    konto = _konto(test_user.token, "Wakacje")
    kontrahent = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)
    dluga_nazwa = "W" * 95

    update_account(test_user.token, konto.id, {'name': dluga_nazwa})

    assert konto.name == dluga_nazwa
    assert kontrahent.name == "Moje konto: Wakacje"


def test_nieudana_edycja_konta_nie_przemianowuje_kontrahenta(app, test_user):
    """Zmiana nazwy i błędny numer rachunku w jednym zapisie: nic się nie zmienia."""
    konto = _konto(test_user.token, "Wakacje")
    kontrahent = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)

    try:
        update_account(test_user.token, konto.id, {'name': 'Wakacje 2027', 'account_number': '123'})
    except ValueError:
        pass

    db.session.expire_all()
    assert db.session.get(Account, konto.id).name == "Wakacje"
    assert db.session.get(Contractor, kontrahent.id).name == "Moje konto: Wakacje"


# --- Wybór kontrahenta konta jest deterministyczny ---

def test_propozycja_przelewu_bierze_aktywnego_kontrahenta_konta(app, test_user):
    """Starszy, wyłączony kontrahent po zmianie nazwy konta nie może wygrywać z aktualnym:
    front nie dostaje wyłączonych, a zatwierdzenie nie rozpoznałoby przelewu."""
    konto = _konto(test_user.token, "Wakacje 2027")
    _kontrahent(test_user.token, "Moje konto: Wakacje", konto, aktywny=False)
    aktualny = _kontrahent(test_user.token, "Moje konto: Wakacje 2027", konto)

    _, kontrahent_id = _internal_transfer_proposal(test_user.token, konto)

    assert kontrahent_id == aktualny.id


def test_wybor_kontrahenta_konta_wsrod_aktywnych_bierze_najnizsze_id(app, test_user):
    konto = _konto(test_user.token, "Wakacje")
    pierwszy = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)
    _kontrahent(test_user.token, "Moje konto: Wakacje", konto)

    _, kontrahent_id = _internal_transfer_proposal(test_user.token, konto)

    assert kontrahent_id == pierwszy.id


def test_druga_noga_przelewu_dostaje_aktywnego_kontrahenta_konta_zrodlowego(app, test_user):
    """Lustro na koncie docelowym wskazuje kontrahenta reprezentującego konto źródłowe —
    ma to być ten aktywny, a nie wyłączony ślad po starej nazwie."""
    token = test_user.token
    zrodlo, cel = _konto(token, "Konto A"), _konto(token, "Konto B")
    przelew = Category(name="Przelew wewnętrzny", type="transfer")
    db.session.add(przelew)
    db.session.commit()
    _kontrahent(token, "Moje konto: A", zrodlo, aktywny=False)
    aktualny = _kontrahent(token, "Moje konto: Konto A", zrodlo)
    do_celu = _kontrahent(token, "Moje konto: Konto B", cel)

    create_transaction(token, zrodlo.id, Decimal("100.00"), "Przelew", date(2026, 11, 1),
                       category_id=przelew.id, contractor_id=do_celu.id)

    lustro = db.session.query(Transaction).filter_by(account_id=cel.id).one()
    assert lustro.contractor_id == aktualny.id


def test_post_kontrahenta_przelewu_nie_wskrzesza_wylaczonego_gdy_jest_aktywny(logged_in_client, test_user):
    konto = _konto(test_user.token, "Wakacje 2027")
    wylaczony = _kontrahent(test_user.token, "Moje konto: Wakacje", konto, aktywny=False)
    aktualny = _kontrahent(test_user.token, "Moje konto: Wakacje 2027", konto)

    resp = logged_in_client.post('/api/contractors', json={
        'name': 'Moje konto: Wakacje 2027', 'rules': '', 'category': None})

    assert resp.get_json()['id'] == aktualny.id
    db.session.expire_all()
    assert db.session.get(Contractor, wylaczony.id).is_active is False


# --- Naprawa danych sprzed poprawki: flask fix-transfer-contractors ---

def _stan_sprzed_poprawki(token):
    """Konto z kontrahentem po starej nazwie i konto z dwoma kontrahentami: wyłączonym,
    po starej nazwie, i aktualnym."""
    wakacje = _konto(token, "Wakacje 2027")
    zalegly = _kontrahent(token, "Moje konto: Wakacje", wakacje)
    glowne = _konto(token, "Konto główne")
    wylaczony = _kontrahent(token, "Moje konto: Główne", glowne, aktywny=False)
    aktualny = _kontrahent(token, "Moje konto: Konto główne", glowne)
    return zalegly, wylaczony, aktualny


def test_naprawa_przemianowuje_przestarzale_nazwy(app, test_user):
    from app.services.contractor_service import ujednolic_nazwy_kontrahentow_kont
    zalegly, wylaczony, aktualny = _stan_sprzed_poprawki(test_user.token)

    zmienione, pominiete = ujednolic_nazwy_kontrahentow_kont(zapisz=True)

    assert zalegly.name == "Moje konto: Wakacje 2027"
    assert wylaczony.name == "Moje konto: Konto główne"
    assert wylaczony.is_active is False
    assert aktualny.name == "Moje konto: Konto główne"
    assert {z['kontrahent_id'] for z in zmienione} == {zalegly.id, wylaczony.id}
    assert pominiete == []


def test_naprawa_w_trybie_probnym_pokazuje_zmiany_i_niczego_nie_zapisuje(app, test_user):
    from app.services.contractor_service import ujednolic_nazwy_kontrahentow_kont
    zalegly, wylaczony, _ = _stan_sprzed_poprawki(test_user.token)

    zmienione, _ = ujednolic_nazwy_kontrahentow_kont(zapisz=False)

    assert {z['kontrahent_id'] for z in zmienione} == {zalegly.id, wylaczony.id}
    db.session.expire_all()
    assert zalegly.name == "Moje konto: Wakacje"
    assert wylaczony.name == "Moje konto: Główne"


def test_naprawa_jest_idempotentna(app, test_user):
    from app.services.contractor_service import ujednolic_nazwy_kontrahentow_kont
    _stan_sprzed_poprawki(test_user.token)
    ujednolic_nazwy_kontrahentow_kont(zapisz=True)

    zmienione, pominiete = ujednolic_nazwy_kontrahentow_kont(zapisz=True)

    assert zmienione == [] and pominiete == []


def test_naprawa_nie_rusza_nazw_recznych_ani_niepowiazanych(app, test_user):
    from app.services.contractor_service import ujednolic_nazwy_kontrahentow_kont
    konto = _konto(test_user.token, "Wakacje 2027")
    wlasna_nazwa = _kontrahent(test_user.token, "Skarbonka na wakacje", konto)
    bez_powiazania = _kontrahent(test_user.token, "Moje konto: Wakacje")

    zmienione, pominiete = ujednolic_nazwy_kontrahentow_kont(zapisz=True)

    assert (wlasna_nazwa.name, bez_powiazania.name) == ("Skarbonka na wakacje", "Moje konto: Wakacje")
    assert zmienione == [] and pominiete == []


def test_naprawa_nie_przenosi_nazwy_cudzego_konta(app, test_user, other_user):
    """Kontrahent jednego użytkownika wskazujący na konto drugiego (błąd danych) nie może
    dostać nazwy cudzego konta."""
    from app.services.contractor_service import ujednolic_nazwy_kontrahentow_kont
    cudze_konto = _konto(other_user.token, "Konto sekretne")
    wadliwy = _kontrahent(test_user.token, "Moje konto: Cokolwiek", cudze_konto)

    zmienione, _ = ujednolic_nazwy_kontrahentow_kont(zapisz=True)

    assert zmienione == []
    assert wadliwy.name == "Moje konto: Cokolwiek"


def test_naprawa_pomija_drugiego_aktywnego_o_tej_samej_nazwie(app, test_user):
    """Dwaj aktywni kontrahenci tego samego konta po starej nazwie: pierwszy dostaje nową,
    drugi zostaje i trafia na listę do ręcznego rozstrzygnięcia."""
    from app.services.contractor_service import ujednolic_nazwy_kontrahentow_kont
    konto = _konto(test_user.token, "Wakacje 2027")
    pierwszy = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)
    drugi = _kontrahent(test_user.token, "Moje konto: Wakacje", konto)

    zmienione, pominiete = ujednolic_nazwy_kontrahentow_kont(zapisz=True)

    assert pierwszy.name == "Moje konto: Wakacje 2027"
    assert drugi.name == "Moje konto: Wakacje"
    assert [z['kontrahent_id'] for z in zmienione] == [pierwszy.id]
    assert [p['kontrahent_id'] for p in pominiete] == [drugi.id]


def test_komenda_pokazuje_zmiany_i_w_trybie_probnym_niczego_nie_zapisuje(app, test_user):
    zalegly, _, _ = _stan_sprzed_poprawki(test_user.token)

    wynik = app.test_cli_runner().invoke(args=['fix-transfer-contractors', '--dry-run'])

    assert wynik.exit_code == 0
    assert "Moje konto: Wakacje -> Moje konto: Wakacje 2027" in wynik.output
    db.session.expire_all()
    assert zalegly.name == "Moje konto: Wakacje"


def test_komenda_bez_potwierdzenia_nic_nie_zapisuje(app, test_user):
    zalegly, _, _ = _stan_sprzed_poprawki(test_user.token)

    wynik = app.test_cli_runner().invoke(args=['fix-transfer-contractors'], input='n\n')

    assert 'Przerwano' in wynik.output
    db.session.expire_all()
    assert zalegly.name == "Moje konto: Wakacje"


def test_komenda_z_yes_przemianowuje_kontrahentow(app, test_user):
    zalegly, wylaczony, _ = _stan_sprzed_poprawki(test_user.token)

    wynik = app.test_cli_runner().invoke(args=['fix-transfer-contractors', '--yes'])

    assert wynik.exit_code == 0
    db.session.expire_all()
    assert zalegly.name == "Moje konto: Wakacje 2027"
    assert wylaczony.name == "Moje konto: Konto główne"


def test_komenda_gdy_nazwy_sa_aktualne(app, test_user):
    konto = _konto(test_user.token, "Wakacje")
    _kontrahent(test_user.token, "Moje konto: Wakacje", konto)

    wynik = app.test_cli_runner().invoke(args=['fix-transfer-contractors', '--yes'])

    assert wynik.exit_code == 0
    assert 'aktualne' in wynik.output
