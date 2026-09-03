from app import db
from app.models import Transaction, TransactionArchive, TransactionSplit, Account
from app.services.category_service import find_by_name as find_category_by_name
from app.services.contractor_service import find_owned as find_contractor_owned
from datetime import date, datetime
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)

def _archive_and_remove_leg(leg: Transaction) -> None:
    """Cofa wpływ jednej transakcji na saldo konta, zapisuje ślad audytowy i usuwa
    ją z sesji. NIE commituje — wołający domyka wszystko jednym commitem."""
    account = db.session.get(Account, leg.account_id)
    if account:
        balance = account.balance if isinstance(account.balance, Decimal) else Decimal(str(account.balance))
        amount = leg.amount if isinstance(leg.amount, Decimal) else Decimal(str(leg.amount))
        account.balance = balance - amount

    # Pełny ślad audytowy — łącznie z podziałami, które kaskadowo znikają razem z transakcją.
    splits_payload = [
        {'amount': str(s.amount), 'desc': s.desc, 'category_id': s.category_id}
        for s in leg.splits
    ]
    db.session.add(TransactionArchive(
        original_id=leg.id,
        title=leg.title,
        amount=leg.amount,
        date=leg.date,
        account_id=leg.account_id,
        category_id=leg.category_id,
        contractor_id=leg.contractor_id,
        user_token=leg.user_token,
        comment=leg.comment,
        contractor_raw=leg.contractor,
        splits_json=json.dumps(splits_payload) if splits_payload else None
    ))
    db.session.delete(leg)


def archive_and_delete_transaction(user_token, tx_id):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_token=user_token).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje lub brak uprawnień.')

        # Przelew wewnętrzny to DWIE powiązane nogi. Usunięcie jednej bez drugiej
        # rozjeżdża Net Worth (outflow znika, inflow zostaje). Usuwamy obie nogi
        # atomowo — jeden przelew = jedna logiczna operacja.
        legs = [tx]
        if tx.linked_transaction_id:
            mirror = db.session.query(Transaction).filter_by(
                id=tx.linked_transaction_id, user_token=user_token
            ).first()
            if mirror:
                legs.append(mirror)

        # Rozwiąż wzajemne powiązanie przed usunięciem, żeby FK (ondelete=SET NULL)
        # nie próbował aktualizować wiersza już usuwanego w tym samym flushu.
        for leg in legs:
            leg.linked_transaction_id = None
        db.session.flush()

        for leg in legs:
            _archive_and_remove_leg(leg)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

def update_transaction(user_token, tx_id, data):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_token=user_token).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje.')

        if 'title' in data or 'desc' in data:
            tx.title = data.get('title') or data.get('desc', tx.title)
        if 'amount' in data:
            # Zmiana kwoty musi skorygować saldo konta o różnicę, inaczej saldo
            # trwale rozjeżdża się z sumą transakcji.
            new_amount = Decimal(str(data['amount']))
            old_amount = tx.amount if isinstance(tx.amount, Decimal) else Decimal(str(tx.amount))
            account = db.session.get(Account, tx.account_id)

            mirror = None
            if tx.linked_transaction_id:
                mirror = db.session.query(Transaction).filter_by(
                    id=tx.linked_transaction_id, user_token=user_token
                ).first()

            if mirror:
                # Noga przelewu wewnętrznego: zachowaj KIERUNEK znaku każdej nogi
                # (edytowana zachowuje swój, lustro dostaje przeciwny) i skoryguj
                # oba salda, inaczej rozjazd Net Worth o różnicę kwoty.
                magnitude = abs(new_amount)
                tx_new = -magnitude if old_amount < 0 else magnitude
                mirror_old = mirror.amount if isinstance(mirror.amount, Decimal) else Decimal(str(mirror.amount))
                mirror_new = -tx_new

                if account:
                    balance = account.balance if isinstance(account.balance, Decimal) else Decimal(str(account.balance))
                    account.balance = balance + (tx_new - old_amount)
                mirror_account = db.session.get(Account, mirror.account_id)
                if mirror_account:
                    m_bal = mirror_account.balance if isinstance(mirror_account.balance, Decimal) else Decimal(str(mirror_account.balance))
                    mirror_account.balance = m_bal + (mirror_new - mirror_old)
                tx.amount = tx_new
                mirror.amount = mirror_new
            else:
                if account:
                    balance = account.balance if isinstance(account.balance, Decimal) else Decimal(str(account.balance))
                    account.balance = balance + (new_amount - old_amount)
                tx.amount = new_amount
        if 'date' in data:
            # Z blueprintu przychodzi już obiekt date (schemat Marshmallow), ale
            # serwis bywa wołany też wprost z testów/CLI ze stringiem — przyjmujemy oba.
            raw_date = data['date']
            tx.date = raw_date if isinstance(raw_date, date) else datetime.strptime(raw_date, '%Y-%m-%d').date()
        if 'category' in data:
            cat = find_category_by_name(user_token, data['category'])
            # Podana, ale nierozpoznana nazwa to błąd — bez tego edycja po cichu
            # zostawiała starą kategorię i mimo to zwracała 200.
            if data['category'] and not cat:
                raise ValueError(f"Kategoria '{data['category']}' nie istnieje lub jest nieaktywna.")
            tx.category_id = cat.id if cat else tx.category_id
        if 'contractor_id' in data:
            cid = data.get('contractor_id')
            if cid:
                contractor = find_contractor_owned(user_token, int(cid))
                if not contractor:
                    raise ValueError(f"Kontrahent o ID {cid} nie istnieje lub brak uprawnień.")
                tx.contractor_id = contractor.id
            else:
                tx.contractor_id = None
        if 'comment' in data:
            tx.comment = data.get('comment') or None

        if 'splits' in data:
            tx.splits.clear()
            for split_data in data['splits']:
                cat = find_category_by_name(user_token, split_data.get('category'))
                tx.splits.append(TransactionSplit(
                    amount=Decimal(str(split_data.get('amount', 0))),
                    desc=split_data.get('desc', ''),
                    category_id=cat.id if cat else None
                ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _wlasne_transakcje(user_token, tx_ids):
    """Pobiera transakcje użytkownika po liście ID — albo rzuca ValueError.

    Zasada jest ostrzejsza niż przy operacji pojedynczej i to jest celowe:
    jeden obcy (albo nieistniejący) identyfikator unieważnia CAŁE żądanie.
    Przy operacji zbiorczej użytkownik nie ogląda każdego wiersza z osobna,
    więc ciche pominięcie części listy byłoby nie do zauważenia — a przy
    usuwaniu oznaczałoby, że nie wiadomo, co faktycznie zniknęło.
    """
    ids = list(dict.fromkeys(int(i) for i in tx_ids))
    if not ids:
        raise ValueError('Nie wskazano żadnej transakcji.')

    txs = db.session.query(Transaction).filter(
        Transaction.id.in_(ids), Transaction.user_token == user_token
    ).all()
    if len(txs) != len(ids):
        raise ValueError('Część transakcji nie istnieje lub brak uprawnień.')
    return txs


def bulk_update_category(user_token, tx_ids, category_name):
    """Ustawia jedną kategorię wielu transakcjom naraz.

    Przelewy wewnętrzne są POMIJANE, a ich liczba wraca w wyniku. Powód:
    zmiana kategorii przelewu na typ inny niż 'transfer' zostawiłaby w bazie
    parę wierszy powiązaną przez linked_transaction_id, która przelewem już
    nie jest — salda pozostają poprawne, ale niezmiennik parowania pęka.
    Pojedyncza edycja nadal na to pozwala; masowa nie, bo tam nikt nie patrzy
    na konkretny wiersz.

    Zwraca {'zmienione': int, 'pominiete_przelewy': int}.
    """
    try:
        category = find_category_by_name(user_token, category_name)
        if not category:
            raise ValueError('Kategoria nie istnieje lub brak uprawnień.')
        if category.type == 'transfer':
            raise ValueError(
                'Kategorii przelewu wewnętrznego nie można nadać zbiorczo — '
                'przelew wymaga wskazania konta docelowego.'
            )

        txs = _wlasne_transakcje(user_token, tx_ids)

        zmienione = 0
        pominiete = 0
        for tx in txs:
            # Dwa niezależne sygnały, że to przelew: sparowana druga noga
            # albo kategoria typu 'transfer' (noga bez pary — np. konto
            # docelowe spoza aplikacji).
            if tx.linked_transaction_id is not None or (tx.category and tx.category.type == 'transfer'):
                pominiete += 1
                continue
            tx.category_id = category.id
            zmienione += 1

        db.session.commit()
        logger.info("Zbiorcza zmiana kategorii na '%s': %s zmienionych, %s pominietych przelewow",
                    category.name, zmienione, pominiete)
        return {'zmienione': zmienione, 'pominiete_przelewy': pominiete}
    except Exception:
        db.session.rollback()
        raise


def bulk_delete_transactions(user_token, tx_ids):
    """Usuwa wiele transakcji naraz — z archiwizacją i korektą sald.

    Przelew wewnętrzny znika w całości, tak samo jak przy usuwaniu
    pojedynczym: wskazanie jednej nogi dokłada drugą. Inaczej wypływ
    zniknąłby, a wpływ został, i Net Worth przestałby się zgadzać.

    Zwraca {'usuniete': int, 'drugie_nogi': int}, gdzie 'drugie_nogi' to
    liczba nóg dołożonych automatycznie — czyli tych, których użytkownik
    NIE zaznaczył, a które i tak zniknęły. Musi trafić do komunikatu.
    """
    try:
        txs = _wlasne_transakcje(user_token, tx_ids)

        # Klucz to ID, więc noga wskazana przez użytkownika i ta sama noga
        # dołożona jako lustro nie policzą się dwa razy.
        do_usuniecia = {tx.id: tx for tx in txs}
        dolozone = 0
        for tx in txs:
            if tx.linked_transaction_id and tx.linked_transaction_id not in do_usuniecia:
                mirror = db.session.query(Transaction).filter_by(
                    id=tx.linked_transaction_id, user_token=user_token
                ).first()
                if mirror:
                    do_usuniecia[mirror.id] = mirror
                    dolozone += 1

        # Rozwiąż powiązania przed usunięciem — tak samo jak w operacji
        # pojedynczej, żeby FK (ondelete=SET NULL) nie aktualizował wiersza
        # usuwanego w tym samym flushu.
        for leg in do_usuniecia.values():
            leg.linked_transaction_id = None
        db.session.flush()

        for leg in do_usuniecia.values():
            _archive_and_remove_leg(leg)

        db.session.commit()
        logger.info("Zbiorcze usuniecie: %s transakcji (w tym %s drugich nog przelewow)",
                    len(do_usuniecia), dolozone)
        return {'usuniete': len(do_usuniecia), 'drugie_nogi': dolozone}
    except Exception:
        db.session.rollback()
        raise
