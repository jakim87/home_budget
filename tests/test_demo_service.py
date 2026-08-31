"""Testy konta demo — odtwarzania danych pokazowych i współdzielonego czyszczenia.

Najważniejsze dwa niezmienniki: odtworzenie ma być idempotentne (nocny timer
uruchamia je codziennie, nie wolno mnożyć danych) oraz salda kont muszą się
zgadzać z sumą transakcji — demo pokazuje liczby, więc błąd tutaj jest widoczny
dla każdego zwiedzającego.
"""
from datetime import date
from decimal import Decimal

from app import db
from app.models import Account, Category, Contractor, RecurringTransaction, Transaction, User
from app.services.budget_service import parse_ing_csv
from app.services.demo_service import (
    DEMO_ACCOUNTS,
    DEMO_CONTRACTORS,
    DEMO_TRANSFER_TARGETS,
    SAMPLE_STATEMENT_ROWS,
    build_sample_statement_csv,
    seed_demo,
    wipe_user_data,
)
from app.services.statement_parsers import decode_statement_bytes, detect_bank_and_format


def _counts(token):
    return {
        'accounts': db.session.query(Account).filter_by(user_token=token).count(),
        'categories': db.session.query(Category).filter_by(user_token=token).count(),
        'contractors': db.session.query(Contractor).filter_by(user_token=token).count(),
        'transactions': db.session.query(Transaction).filter_by(user_token=token).count(),
        'recurring': db.session.query(RecurringTransaction).filter_by(user_token=token).count(),
    }


def _demo_user():
    return db.session.query(User).filter_by(username='demo').first()


def test_seed_demo_tworzy_konto_i_dane(app):
    summary = seed_demo('demo', 'demo-do-ogladania')

    user = _demo_user()
    assert user is not None
    assert summary['accounts'] == len(DEMO_ACCOUNTS)
    assert summary['transactions'] > 0

    counts = _counts(user.token)
    assert counts['accounts'] == len(DEMO_ACCOUNTS)
    assert counts['recurring'] == 1

    # Kontrahenci ze słownika + po jednym na każdy cel przelewu + jeden zwrotny
    # ("Moje konto: Konto osobiste"), którego zakłada sama aplikacja, żeby na koncie
    # docelowym było widać źródło przelewu.
    nazwy = {c.name for c in db.session.query(Contractor).filter_by(user_token=user.token).all()}
    for cel in DEMO_TRANSFER_TARGETS:
        assert f'Moje konto: {cel}' in nazwy
    assert 'Moje konto: Konto osobiste' in nazwy
    assert counts['contractors'] == len(DEMO_CONTRACTORS) + len(DEMO_TRANSFER_TARGETS) + 1


def test_seed_demo_jest_idempotentne(app):
    """Nocny timer uruchamia to codziennie — drugie wywołanie nie może zdublować danych."""
    seed_demo('demo', 'demo-do-ogladania')
    pierwsze = _counts(_demo_user().token)

    seed_demo('demo', 'demo-do-ogladania')
    drugie = _counts(_demo_user().token)

    assert pierwsze == drugie
    assert db.session.query(User).filter_by(username='demo').count() == 1


def test_salda_kont_zgadzaja_sie_z_transakcjami(app):
    """Saldo każdego konta = suma jego transakcji. Demo pokazuje liczby, więc muszą się spinać."""
    seed_demo('demo', 'demo-do-ogladania')
    token = _demo_user().token

    for account in db.session.query(Account).filter_by(user_token=token).all():
        suma = sum(
            (t.amount for t in db.session.query(Transaction).filter_by(account_id=account.id).all()),
            Decimal('0.00'),
        )
        assert Decimal(account.balance) == suma, f"Rozjazd salda na koncie {account.name}"


def test_przelew_wewnetrzny_ma_obie_nogi(app):
    """Przelew na oszczędności to sygnaturowa funkcja aplikacji — demo musi ją pokazywać."""
    seed_demo('demo', 'demo-do-ogladania')
    token = _demo_user().token

    transfery = db.session.query(Transaction).filter(
        Transaction.user_token == token,
        Transaction.title == 'Odkładam na wakacje',
    ).all()
    assert transfery, "Brak transakcji przelewu wewnętrznego"

    for tx in transfery:
        assert tx.linked_transaction_id is not None, "Przelew bez drugiej nogi"
        druga = db.session.get(Transaction, tx.linked_transaction_id)
        assert druga is not None
        assert druga.amount == -tx.amount


def test_odtworzenie_czysci_zmiany_zwiedzajacego(app):
    """Zwiedzający ma pełne prawa zapisu — porządek robi dopiero odtworzenie."""
    seed_demo('demo', 'demo-do-ogladania')
    token = _demo_user().token

    db.session.add(Account(name='Konto śmieciowe', bank_name='X', balance=Decimal('0.00'), user_token=token))
    db.session.add(Category(name='Kategoria śmieciowa', type='expense', user_token=token))
    db.session.commit()

    seed_demo('demo', 'demo-do-ogladania')

    nazwy_kont = {a.name for a in db.session.query(Account).filter_by(user_token=token).all()}
    nazwy_kat = {c.name for c in db.session.query(Category).filter_by(user_token=token).all()}
    assert 'Konto śmieciowe' not in nazwy_kont
    assert 'Kategoria śmieciowa' not in nazwy_kat


def test_przykladowy_wyciag_przechodzi_detekcje_i_parser(app):
    """Plik oferowany do pobrania musi dać się zaimportować — inaczej demo kompromituje.

    Idzie tą samą drogą co prawdziwy upload: detekcja banku po zawartości, dekodowanie,
    parser ING. Sprawdza też, że reguły kontrahentów łapią pozycje z wyciągu — to jest
    właściwy sens pokazu, nie samo wczytanie pliku.
    """
    seed_demo('demo', 'demo-do-ogladania')
    user = _demo_user()
    konto = db.session.query(Account).filter_by(user_token=user.token, name='Konto osobiste').first()

    raw = build_sample_statement_csv().encode('utf-8-sig')
    assert detect_bank_and_format(raw, 'przykladowy-wyciag-ing.csv') == ('ing', 'csv')

    wynik = parse_ing_csv(decode_statement_bytes(raw), user.token, main_account_id=konto.id)
    assert len(wynik['transactions']) == len(SAMPLE_STATEMENT_ROWS)
    assert wynik['skipped_count'] == 0

    # Kontrahenci demo mają reguły dopasowania — część pozycji ma się rozpoznać sama,
    # a DECATHLON celowo nie, żeby było widać krok ręcznej kategoryzacji.
    opisy = {t['contractor'] for t in wynik['transactions']}
    assert any('BIEDRONKA' in o for o in opisy)
    assert any('DECATHLON' in o for o in opisy)


def test_przykladowy_wyciag_tylko_w_trybie_demo(app, logged_in_client):
    """Poza trybem demo endpoint nie istnieje — to nie jest funkcja produkcyjna."""
    app.config['DEMO_ENABLED'] = False
    assert logged_in_client.get('/api/demo/przykladowy-wyciag.csv').status_code == 404

    app.config['DEMO_ENABLED'] = True
    odpowiedz = logged_in_client.get('/api/demo/przykladowy-wyciag.csv')
    assert odpowiedz.status_code == 200
    assert 'attachment' in odpowiedz.headers['Content-Disposition']
    # BOM: prawdziwe eksporty z ING też go mają, a decode_statement_bytes go oczekuje.
    assert odpowiedz.data.startswith(b'\xef\xbb\xbf')


def test_wipe_nie_rusza_danych_innego_uzytkownika(app, test_user, other_user):
    """wipe_user_data to surowy SQL filtrowany tokenem — jedyna bariera przed cudzymi danymi."""
    for user in (test_user, other_user):
        acc = Account(name=f'Konto {user.username}', bank_name='X',
                      balance=Decimal('100.00'), user_token=user.token)
        db.session.add(acc)
        db.session.flush()
        db.session.add(Transaction(date=date.today(), amount=Decimal('100.00'),
                                   title='Wpłata', account_id=acc.id, user_token=user.token))
    db.session.commit()

    wipe_user_data(test_user.token)

    assert db.session.query(Transaction).filter_by(user_token=test_user.token).count() == 0
    assert db.session.query(Transaction).filter_by(user_token=other_user.token).count() == 1
    # Konta zostają, ale z wyzerowanym saldem — tylko u czyszczonego użytkownika.
    czyszczone = db.session.query(Account).filter_by(user_token=test_user.token).first()
    nietkniete = db.session.query(Account).filter_by(user_token=other_user.token).first()
    assert Decimal(czyszczone.balance) == Decimal('0.00')
    assert Decimal(nietkniete.balance) == Decimal('100.00')
