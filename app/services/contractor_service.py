import logging

from app import db
from app.models import Account, Contractor, Category
from app.services.category_service import find_by_name as find_category_by_name

logger = logging.getLogger(__name__)

PREFIKS_KONTA = "Moje konto: "
# Nazwa konta z prefiksem musi się zmieścić w kolumnie kontrahenta (prefiks zabiera 12 znaków).
_MAKS_DLUGOSC_NAZWY = Contractor.__table__.c.name.type.length


def find_owned(user_token, contractor_id):
    """Kontrahent o danym ID należący do użytkownika, albo None.

    Celowo BEZ filtra is_active — transakcja z historycznym, wyłączonym kontrahentem
    jest dozwolona (patrz budget_service.create_transaction). Jedyne miejsce, w którym
    kontrahent jest rozwiązywany po ID, żeby nie dało się podpiąć cudzego (patrz #127).
    """
    if not contractor_id:
        return None
    return db.session.query(Contractor).filter_by(id=contractor_id, user_token=user_token).first()


def kontrahent_konta(user_token, account_id):
    """Kontrahent „Moje konto: X” powiązany z kontem albo None.

    Kontrahentów jednego konta bywa kilku: po zmianie nazwy konta (sprzed przemianowywania
    ich razem z nim) został stary, często wyłączony, obok aktualnego. Wybór jest zawsze ten
    sam — aktywny przed wyłączonym, potem najniższe id. „Pierwszy z bazy” bez porządku bywał
    wyłączonym, którego front nie zna, i zatwierdzony przelew przestawał być rozpoznawany.
    """
    return db.session.query(Contractor).filter_by(
        user_token=user_token, linked_account_id=account_id
    ).order_by(Contractor.is_active.desc(), Contractor.id).first()


def _own_account_contractor(user_token, name):
    """(konto, istniejący kontrahent) dla nazwy „Moje konto: X”; (None, None) dla każdej innej.

    Kontrahent przelewu wewnętrznego jest jeden na konto i niesie linked_account_id —
    parowanie nóg szuka po nim. Drugi o tej samej nazwie, bez powiązania, zbierałby
    przelewy, których nic nigdy nie sparuje (#215).
    """
    prefix = PREFIKS_KONTA
    if not name.startswith(prefix):
        return None, None
    konta = db.session.query(Account).filter_by(
        user_token=user_token, name=name[len(prefix):], is_active=True
    ).all()
    if len(konta) != 1:
        return None, None
    cont = kontrahent_konta(user_token, konta[0].id) or db.session.query(Contractor).filter_by(
        user_token=user_token, name=name, is_active=True
    ).first()
    return konta[0], cont


def create_contractor(user_token, data):
    try:
        category = find_category_by_name(user_token, data.get('category'))
        konto, istniejacy = _own_account_contractor(user_token, data['name'])
        if istniejacy:
            istniejacy.is_active = True
            istniejacy.linked_account_id = konto.id
            db.session.commit()
            return istniejacy, (db.session.get(Category, istniejacy.default_category_id)
                                if istniejacy.default_category_id else None)
        new_cont = Contractor(
            name=data['name'],
            mapping_rules=data.get('rules'),
            default_category_id=category.id if category else None,
            user_token=user_token,
            linked_account_id=konto.id if konto else None
        )
        db.session.add(new_cont)
        db.session.commit()
        return new_cont, category
    except Exception:
        db.session.rollback()
        raise

def update_contractor(user_token, c_id, data):
    try:
        cont = db.session.query(Contractor).filter_by(id=c_id, user_token=user_token).first()
        if not cont:
            raise ValueError('Nie znaleziono kontrahenta.')
        cont.name = data.get('name', cont.name)
        cont.mapping_rules = data.get('rules', cont.mapping_rules)

        # Kategorię zmieniamy TYLKO gdy klucz jest obecny w żądaniu. Inaczej częściowa
        # edycja (PUT bez pola 'category') cicho kasowałaby domyślną kategorię kontrahenta.
        category = None
        if 'category' in data:
            category = find_category_by_name(user_token, data.get('category'))
            cont.default_category_id = category.id if category else None
        elif cont.default_category_id:
            category = db.session.get(Category, cont.default_category_id)

        db.session.commit()
        return cont, category
    except Exception:
        db.session.rollback()
        raise

def soft_delete_contractor(user_token, c_id):
    try:
        cont = db.session.query(Contractor).filter_by(id=c_id, user_token=user_token).first()
        if not cont:
            raise ValueError('Nie znaleziono kontrahenta lub brak uprawnień.')
        cont.is_active = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _powod_odmowy_nazwy(kontrahent, nowa_nazwa):
    """Dlaczego kontrahent nie może przyjąć tej nazwy (tekst do komunikatu) albo None.

    Dwóch aktywnych kontrahentów o jednej nazwie to pułapka: pole kontrahenta w formularzu
    wybiera po nazwie, więc przelew mógłby trafić na tego, który nie jest powiązany z kontem,
    i nigdy by się nie sparował (#215). Wyłączeni nie kolidują — nie ma ich w słownikach.
    Druga przeszkoda to długość: nazwa konta z prefiksem może nie zmieścić się w kolumnie,
    a wtedy błąd bazy zablokowałby zmianę nazwy samego konta.
    """
    if len(nowa_nazwa) > _MAKS_DLUGOSC_NAZWY:
        return f"nowa nazwa przekracza {_MAKS_DLUGOSC_NAZWY} znaków"
    if kontrahent.is_active and db.session.query(Contractor.id).filter(
        Contractor.user_token == kontrahent.user_token,
        Contractor.is_active.is_(True),
        Contractor.name == nowa_nazwa,
        Contractor.id != kontrahent.id,
    ).first():
        return "inny aktywny kontrahent ma już tę nazwę"
    return None


def _przemianuj(kontrahent, nowa_nazwa):
    """Zmienia nazwę kontrahenta, o ile może ją przyjąć. Zwraca powód odmowy albo None.

    Odmowa nie jest błędem: kontrahent zostaje przy starej nazwie (przelewy idą po powiązaniu
    z kontem, nie po nazwie), a w logu ląduje wyłącznie identyfikator i stały tekst (A10).
    """
    powod = _powod_odmowy_nazwy(kontrahent, nowa_nazwa)
    if powod:
        logger.warning("Kontrahent #%s konta #%s zostaje przy starej nazwie: %s.",
                       kontrahent.id, kontrahent.linked_account_id, powod)
    else:
        kontrahent.name = nowa_nazwa
    return powod


def przemianuj_kontrahentow_konta(user_token, konto, stara_nazwa):
    """Po zmianie nazwy konta nadaje jego kontrahentom nazwę „Moje konto: <nowa nazwa>”.

    Rusza tylko kontrahentów powiązanych z tym kontem, których nazwa to dokładnie
    „Moje konto: <stara nazwa>” — nazwy ustawione inaczej zostają. Commit należy do
    wywołującego (update_account), żeby zmiana konta i kontrahenta była jedną transakcją.
    """
    kontrahenci = db.session.query(Contractor).filter_by(
        user_token=user_token, linked_account_id=konto.id, name=PREFIKS_KONTA + stara_nazwa
    ).order_by(Contractor.id).all()
    for kontrahent in kontrahenci:
        _przemianuj(kontrahent, PREFIKS_KONTA + konto.name)


def ujednolic_nazwy_kontrahentow_kont(zapisz):
    """Wyrównuje nazwy kontrahentów „Moje konto: X” z nazwami kont, z którymi są powiązani.

    Naprawa danych sprzed przemianowywania kontrahenta przy zmianie nazwy konta. Bierze
    kontrahentów powiązanych z kontem tego samego użytkownika, których nazwa zaczyna się od
    „Moje konto: ” (wyłączonych też, żeby stara nazwa nie została na starych wpisach); nazwy
    ustawione inaczej zostają. Bez `zapisz` nic nie trafia do bazy, a lista zmian jest
    dokładnie tą, którą zapisałby przebieg z `zapisz` — obie drogi idą tym samym kodem.

    Zwraca (zmienione, pominiete): listy słowników z identyfikatorami kontrahenta i konta
    oraz starą i nową nazwą; przy pominiętych także powód.
    """
    try:
        zmienione, pominiete = [], []
        pary = (
            db.session.query(Contractor, Account)
            .join(Account, Account.id == Contractor.linked_account_id)
            .filter(Account.user_token == Contractor.user_token,
                    Contractor.name.startswith(PREFIKS_KONTA))
            .order_by(Contractor.id)
            .all()
        )
        for kontrahent, konto in pary:
            nowa_nazwa = PREFIKS_KONTA + konto.name
            if kontrahent.name == nowa_nazwa:
                continue
            opis = {'kontrahent_id': kontrahent.id, 'konto_id': konto.id,
                    'aktywny': kontrahent.is_active,
                    'stara_nazwa': kontrahent.name, 'nowa_nazwa': nowa_nazwa}
            powod = _przemianuj(kontrahent, nowa_nazwa)
            if powod:
                pominiete.append({**opis, 'powod': powod})
            else:
                zmienione.append(opis)
        if zapisz:
            db.session.commit()
            logger.info("Nazwy kontrahentów kont ujednolicone: zmieniono %d, pominięto %d.",
                        len(zmienione), len(pominiete))
        else:
            db.session.rollback()
        return zmienione, pominiete
    except Exception:
        db.session.rollback()
        raise
