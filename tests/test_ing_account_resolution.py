"""Wspólna logika dopasowania kont ING (nazwa produktowa -> account_id),
używana zarówno przez parser CSV jak i PDF (#106). Wydzielona z parse_ing_csv,
żeby oba formaty rozwiązywały etykiety kont IDENTYCZNIE."""
from app import db
from app.models import Account, User
from app.services.budget_service import build_ing_account_maps, resolve_ing_account_label


def test_build_ing_account_maps_matches_by_iban(app):
    user = User(username="ing_maps_user", email="im@test.com", password_hash="a")
    db.session.add(user)
    db.session.commit()
    acc = Account(name="Moje ING", bank_name="ING", user_token=user.token,
                 account_number="45 1050 1025 1000 0091 0293 0329")
    db.session.add(acc)
    db.session.commit()

    entries = [("KONTO Z LWEM Direct", "45105010251000009102930329")]
    info, name_map, db_name_map, ibans = build_ing_account_maps(entries, user.token)

    assert info == [{'csv_name': 'KONTO Z LWEM Direct', 'iban': '45105010251000009102930329',
                     'account_id': acc.id, 'account_name': 'Moje ING', 'matched': True}]
    assert name_map == {'KONTO Z LWEM Direct': acc.id}
    assert db_name_map == {'moje ing': acc.id}
    assert ibans == {'45105010251000009102930329'}


def test_build_ing_account_maps_unmatched_account_reported(app):
    user = User(username="ing_maps_user2", email="im2@test.com", password_hash="a")
    db.session.add(user)
    db.session.commit()

    entries = [("iPad 3k", "24105010251000009180015928")]
    info, name_map, db_name_map, ibans = build_ing_account_maps(entries, user.token)

    assert info[0]['matched'] is False
    assert info[0]['account_id'] is None
    assert name_map == {'iPad 3k': None}


def test_build_ing_account_maps_duplicate_labels_first_wins(app):
    """ING potrafi nazwać kilka różnych kont tą samą generyczną etykietą
    (np. 'Otwarte Konto Oszczędnościowe' x3) — pierwsze wystąpienie w nagłówku
    wygrywa w mapie po nazwie; reszta polega na fallbacku po nazwie w apce."""
    user = User(username="ing_maps_user3", email="im3@test.com", password_hash="a")
    db.session.add(user)
    db.session.commit()
    acc_a = Account(name="Konto A", bank_name="ING", user_token=user.token, account_number="11" * 13)
    acc_b = Account(name="Konto B", bank_name="ING", user_token=user.token, account_number="22" * 13)
    db.session.add_all([acc_a, acc_b])
    db.session.commit()

    entries = [
        ("Otwarte Konto Oszczędnościowe", "11" * 13),
        ("Otwarte Konto Oszczędnościowe", "22" * 13),
    ]
    info, name_map, db_name_map, ibans = build_ing_account_maps(entries, user.token)

    assert name_map == {'Otwarte Konto Oszczędnościowe': acc_a.id}
    assert len(info) == 2
    assert info[1]['iban'] == "22" * 13 and info[1]['matched'] is True


def test_resolve_ing_account_label_matches_by_product_name():
    name_map = {'Wakacje': 5}
    matched, account_id = resolve_ing_account_label('Wakacje', name_map, {})
    assert matched is True
    assert account_id == 5


def test_resolve_ing_account_label_strips_currency_suffix():
    name_map = {'Smart Saver': 7}
    matched, account_id = resolve_ing_account_label('Smart Saver (PLN)', name_map, {})
    assert matched is True
    assert account_id == 7


def test_resolve_ing_account_label_falls_back_to_app_account_name():
    """Etykieta z pliku ('Otwarte Konto Oszczędnościowe') nie pasuje do nazwy
    w apce ('Fundusz remontowy') — ale fallback po WŁASNEJ nazwie w apce łapie
    to, gdy blok/wiersz faktycznie pokazuje przemianowaną nazwę."""
    name_map = {'Otwarte Konto Oszczędnościowe': None}
    db_name_map = {'fundusz remontowy': 42}
    matched, account_id = resolve_ing_account_label('Fundusz remontowy', name_map, db_name_map)
    assert matched is True
    assert account_id == 42


def test_resolve_ing_account_label_unknown_subaccount_not_guessed():
    """Podkonto/cel spoza słownika (np. 'iPad 3k') — nie zgadujemy, jawnie
    zwracamy 'nierozpoznane', a nie jakiś domyślny/przybliżony account_id."""
    matched, account_id = resolve_ing_account_label('iPad 3k', {}, {})
    assert matched is False
    assert account_id is None
