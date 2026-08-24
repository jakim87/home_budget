"""Systematyczne testy autoryzacji (IDOR): zalogowany użytkownik B (intruz) próbuje
modyfikować zasoby użytkownika A (testuser) po ID. Każdy test sprawdza dwie rzeczy:
odpowiedź HTTP z błędem ORAZ brak zmiany stanu w bazie."""
import pytest
from datetime import date
from decimal import Decimal

from app import db
from app.models import (
    Account, Budget, Category, Contractor, Transaction, TransactionStaging,
    TransactionArchive, RecurringTransaction, PlannedTransaction, Frequency,
    StatementImport,
)
from tests.conftest import login_as


@pytest.fixture
def owner_data(app, test_user):
    """Komplet zasobów należących do testuser — cele ataku."""
    account = Account(name="Konto Ofiary", bank_name="Bank", balance=Decimal("1000.00"), user_token=test_user.token)
    category = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, category])
    db.session.commit()

    contractor = Contractor(name="Biedronka", user_token=test_user.token, default_category_id=category.id)
    db.session.add(contractor)
    db.session.commit()

    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-50.00"),
                     account_id=account.id, category_id=category.id, user_token=test_user.token)
    stg = TransactionStaging(date=date(2024, 1, 11), amount=Decimal("-20.00"), title="Staging",
                             status="pending", user_token=test_user.token, account_id=account.id)
    rec = RecurringTransaction(user_token=test_user.token, account_id=account.id, title="Czynsz",
                               amount=Decimal("-100.00"), frequency=Frequency.MONTHLY, day_of_month=1,
                               interval=1, start_date=date(2024, 1, 1), next_run_date=date(2024, 6, 1))
    planned = PlannedTransaction(user_token=test_user.token, account_id=account.id, title="Ubezpieczenie",
                                 amount=Decimal("-300.00"), execution_date=date(2024, 7, 1), status="pending")
    db.session.add_all([tx, stg, rec, planned])
    db.session.commit()

    return {
        'account': account, 'category': category, 'contractor': contractor,
        'tx': tx, 'stg': stg, 'rec': rec, 'planned': planned,
    }


@pytest.fixture
def intruder_client(client, owner_data, other_user):
    """Klient zalogowany jako intruz (other_user), z gotowymi zasobami ofiary."""
    login_as(client, "intruz")
    return client


def test_intruder_cannot_update_transaction(intruder_client, owner_data):
    tx = owner_data['tx']
    resp = intruder_client.put(f'/api/transactions/{tx.id}', json={'title': 'PRZEJĘTE', 'amount': '999.00'})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx.id).title == "Zakupy"
    assert db.session.get(Transaction, tx.id).amount == Decimal("-50.00")


def test_intruder_cannot_delete_transaction(intruder_client, owner_data):
    tx = owner_data['tx']
    resp = intruder_client.delete(f'/api/transactions/{tx.id}')
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx.id) is not None
    assert db.session.query(TransactionArchive).filter_by(original_id=tx.id).count() == 0


def test_intruder_cannot_update_account(intruder_client, owner_data):
    acc = owner_data['account']
    resp = intruder_client.put(f'/api/accounts/{acc.id}', json={'name': 'PRZEJĘTE'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Account, acc.id).name == "Konto Ofiary"


def test_intruder_cannot_delete_account(intruder_client, owner_data):
    acc = owner_data['account']
    resp = intruder_client.delete(f'/api/accounts/{acc.id}')
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Account, acc.id).is_active is True


def test_intruder_cannot_reconcile_account(intruder_client, owner_data):
    acc = owner_data['account']
    resp = intruder_client.post(f'/api/accounts/{acc.id}/reconcile', json={'new_balance': '0.00'})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Account, acc.id).balance == Decimal("1000.00")
    # Nie powstała transakcja korygująca na cudzym koncie
    assert db.session.query(Transaction).filter_by(account_id=acc.id, title="Uzgadnianie salda").count() == 0


def test_intruder_cannot_update_contractor(intruder_client, owner_data):
    cont = owner_data['contractor']
    resp = intruder_client.put(f'/api/contractors/{cont.id}', json={'name': 'PRZEJĘTE'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Contractor, cont.id).name == "Biedronka"


def test_intruder_cannot_delete_contractor(intruder_client, owner_data):
    cont = owner_data['contractor']
    resp = intruder_client.delete(f'/api/contractors/{cont.id}')
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Contractor, cont.id).is_active is True


def test_intruder_cannot_update_recurring(intruder_client, owner_data):
    rec = owner_data['rec']
    resp = intruder_client.put(f'/api/recurring-transactions/{rec.id}', json={'title': 'PRZEJĘTE'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(RecurringTransaction, rec.id).title == "Czynsz"


def test_intruder_cannot_delete_planned(intruder_client, owner_data):
    planned = owner_data['planned']
    resp = intruder_client.delete(f'/api/planned-transactions/{planned.id}')
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(PlannedTransaction, planned.id) is not None


def test_intruder_cannot_approve_staging(intruder_client, owner_data):
    stg = owner_data['stg']
    cont = owner_data['contractor']
    resp = intruder_client.post(f'/api/staging/{stg.id}/approve',
                                json={'category': 'Jedzenie', 'contractor_id': cont.id})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg.id).status == "pending"


def test_intruder_cannot_accept_staging_contractor(intruder_client, owner_data):
    stg = owner_data['stg']
    resp = intruder_client.post(f'/api/staging/{stg.id}/accept-contractor', json={'name': 'Nowy'})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg.id).proposed_contractor_id is None


def test_intruder_cannot_dismiss_staging_as_duplicate(intruder_client, owner_data):
    """Cudzy wiersz stagingu nie może zostać odrzucony jako duplikat."""
    stg = owner_data['stg']
    tx = owner_data['tx']
    resp = intruder_client.post(f'/api/staging/{stg.id}/duplicate-of', json={'transaction_id': tx.id})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(TransactionStaging, stg.id) is not None


def test_intruder_cannot_dismiss_own_staging_against_foreign_transaction(intruder_client, owner_data, other_user):
    """Intruz na WŁASNYM wierszu stagingu wskazuje CUDZĄ transakcję — odmowa, wiersz zostaje."""
    my_acc = Account(name="Konto Intruza", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    db.session.add(my_acc)
    db.session.commit()
    my_stg = TransactionStaging(date=date(2024, 1, 10), amount=Decimal("-50.00"), title="Mój staging",
                                status="pending", user_token=other_user.token, account_id=my_acc.id)
    db.session.add(my_stg)
    db.session.commit()

    resp = intruder_client.post(f'/api/staging/{my_stg.id}/duplicate-of',
                                json={'transaction_id': owner_data['tx'].id})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(TransactionStaging, my_stg.id) is not None
    assert db.session.get(Transaction, owner_data['tx'].id) is not None


def test_intruder_cannot_create_transaction_with_foreign_contractor(intruder_client, owner_data, other_user):
    """Intruz podaje CUDZY contractor_id przy tworzeniu własnej transakcji — kontrahent
    nie może zostać podpięty (a jego nazwa nie może wyciec w odpowiedzi)."""
    my_acc = Account(name="Konto Intruza", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    db.session.add(my_acc)
    db.session.commit()

    resp = intruder_client.post('/api/transactions', json={
        'title': 'Test', 'amount': '-10.00', 'date': '2024-01-15',
        'account_id': my_acc.id, 'contractor_id': owner_data['contractor'].id,
    })
    # Kontrahent jest walidowany w create_transaction — cudze ID odrzucone jako błąd,
    # transakcja w ogóle nie powstaje (patrz #127).
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.query(Transaction).filter_by(account_id=my_acc.id).count() == 0


def test_intruder_cannot_set_foreign_contractor_on_own_transaction(intruder_client, owner_data, other_user):
    """Intruz edytuje WŁASNĄ transakcję, ale podaje CUDZY contractor_id — odrzucone (#127).

    Regresja: przed poprawką PUT zwracał 200 i podpinał cudzego kontrahenta, którego
    nazwa potem wyciekała do intruza przez `contractor_name` w /api/init. Ten kształt
    luki — własny zasób, cudze ID w treści żądania — omijał wszystkie testy IDOR
    sprawdzające dostęp po ID w adresie."""
    my_acc = Account(name="Konto Intruza", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    db.session.add(my_acc)
    db.session.commit()
    my_tx = Transaction(date=date(2024, 1, 15), title="Moja transakcja", amount=Decimal("-10.00"),
                        account_id=my_acc.id, user_token=other_user.token)
    db.session.add(my_tx)
    db.session.commit()

    resp = intruder_client.put(f'/api/transactions/{my_tx.id}', json={'contractor_id': owner_data['contractor'].id})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, my_tx.id).contractor_id is None


def test_intruder_cannot_set_foreign_category_on_recurring_or_planned(intruder_client, owner_data, test_user, other_user):
    """Intruz zakłada WŁASNĄ transakcję cykliczną/zaplanowaną, ale podaje CUDZY
    PRYWATNY category_id — odrzucone (#127, issue macierzysty tej rodziny luk).

    Kategoria musi być prywatna (user_token != NULL) — globalne kategorie (owner_data
    tworzy taką domyślnie) są celowo widoczne dla wszystkich, więc nie testują luki.

    Regresja: przed poprawką POST zwracał 201 i zapisywał cudzy category_id wprost do
    definicji harmonogramu — obie ścieżki brały ID liczbą ze schematu, bez sprawdzenia
    właściciela."""
    my_acc = Account(name="Konto Intruza", bank_name="Bank", balance=Decimal("0.00"), user_token=other_user.token)
    private_cat = Category(name="Prywatna kategoria ofiary", type="expense", user_token=test_user.token)
    db.session.add_all([my_acc, private_cat])
    db.session.commit()
    foreign_cat_id = private_cat.id

    resp_rec = intruder_client.post('/api/recurring-transactions/', json={
        'account_id': my_acc.id, 'category_id': foreign_cat_id, 'title': 'Test cykliczny',
        'amount': '-100.00', 'frequency': 'monthly', 'day_of_month': 5,
        'start_date': '2024-01-01',
    })
    assert resp_rec.status_code == 400
    db.session.expire_all()
    assert db.session.query(RecurringTransaction).filter_by(user_token=other_user.token).count() == 0

    resp_planned = intruder_client.post('/api/planned-transactions/', json={
        'account_id': my_acc.id, 'category_id': foreign_cat_id, 'title': 'Test zaplanowany',
        'amount': '-50.00', 'execution_date': '2024-07-01',
    })
    assert resp_planned.status_code == 400
    db.session.expire_all()
    assert db.session.query(PlannedTransaction).filter_by(user_token=other_user.token).count() == 0


def test_intruder_cannot_import_to_foreign_account(intruder_client, owner_data, other_user):
    """Intruz wgrywa wyciąg wskazując CUDZE account_id w formularzu — odrzucone (#127).

    Regresja: przed poprawką import CSV bez wykrywalnego IBAN-u (ING, plik jednokontowy)
    w ogóle nie sprawdzał właściciela konta — powstawał wiersz stagingu ORAZ wpis
    w statement_imports na cudzym koncie. Ten drugi jest groźniejszy: to sygnał pokrycia
    dla account_has_statement_imports(), więc zatrucie go po cichu wyłączało generowanie
    lustra przelewu wewnętrznego na koncie ofiary — błędne saldo bez komunikatu."""
    import io
    victim_acc = owner_data['account']
    csv_content = (
        "Data transakcji;Dane kontrahenta;Tytuł;Nr rachunku;Kwota transakcji (waluta rachunku)\n"
        "2024-01-05;SKLEP;Zakupy;;-25,00\n"
    )
    resp = intruder_client.post(
        '/api/import/ing',
        data={'file': (io.BytesIO(csv_content.encode('utf-8')), 'wyciag.csv'),
              'account_id': str(victim_acc.id)},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 400
    db.session.expire_all()
    # Filtr po user_token intruza (nie account_id samo w sobie) — owner_data już
    # zakłada jeden legalny wiersz stagingu na tym koncie dla właściciela.
    assert db.session.query(TransactionStaging).filter_by(
        user_token=other_user.token, account_id=victim_acc.id
    ).count() == 0
    assert db.session.query(StatementImport).filter_by(
        user_token=other_user.token, account_id=victim_acc.id
    ).count() == 0


def test_intruder_sees_only_own_data_in_init(intruder_client, owner_data):
    resp = intruder_client.get('/api/init')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['transactions'] == []
    assert data['accounts'] == []
    assert all(c['name'] != 'Biedronka' for c in data['contractors'])


def test_dev_reset_wipes_only_current_user_data(intruder_client, owner_data, test_user, other_user):
    """POST /api/dev/reset kasuje WYŁĄCZNIE dane wołającego — dane ofiary nietknięte.

    Najbardziej destrukcyjny endpoint w aplikacji (kasuje transakcje, staging, archiwum,
    harmonogramy, budżety, kontrahentów i zeruje salda) — przez długi czas bez żadnego
    testu. Sprawdzamy obie strony: że reset faktycznie zadziałał u wołającego ORAZ że
    nie ruszył cudzych wierszy w żadnej z tych tabel.

    Uwaga: reset NIE czyści statement_imports — patrz #136."""
    # Ofiara dostaje jeszcze archiwum i budżet — obu owner_data nie zakłada,
    # a reset ich dotyka.
    victim_archive = TransactionArchive(original_id=999, title="Usunięta", amount=Decimal("-30.00"),
                                        date=date(2024, 1, 5), account_id=owner_data['account'].id,
                                        user_token=test_user.token)
    victim_budget = Budget(amount=Decimal("500.00"), month=1, year=2024,
                           category_id=owner_data['category'].id, user_token=test_user.token)
    # Dane intruza — muszą zniknąć, inaczej test przeszedłby na resecie, który nic nie robi.
    my_acc = Account(name="Konto Intruza", bank_name="Bank", balance=Decimal("300.00"), user_token=other_user.token)
    db.session.add_all([victim_archive, victim_budget, my_acc])
    db.session.commit()
    my_tx = Transaction(date=date(2024, 2, 1), title="Moja transakcja", amount=Decimal("-15.00"),
                        account_id=my_acc.id, user_token=other_user.token)
    my_stg = TransactionStaging(date=date(2024, 2, 2), amount=Decimal("-5.00"), title="Mój staging",
                                status="pending", user_token=other_user.token, account_id=my_acc.id)
    db.session.add_all([my_tx, my_stg])
    db.session.commit()

    resp = intruder_client.post('/api/dev/reset')
    assert resp.status_code == 200

    db.session.expire_all()
    # Dane intruza wyczyszczone, saldo wyzerowane.
    assert db.session.query(Transaction).filter_by(user_token=other_user.token).count() == 0
    assert db.session.query(TransactionStaging).filter_by(user_token=other_user.token).count() == 0
    assert db.session.get(Account, my_acc.id).balance == Decimal("0.00")

    # Dane ofiary w komplecie i bez zmian.
    assert db.session.get(Transaction, owner_data['tx'].id) is not None
    assert db.session.get(TransactionStaging, owner_data['stg'].id) is not None
    assert db.session.get(RecurringTransaction, owner_data['rec'].id) is not None
    assert db.session.get(PlannedTransaction, owner_data['planned'].id) is not None
    assert db.session.get(Contractor, owner_data['contractor'].id) is not None
    assert db.session.get(TransactionArchive, victim_archive.id) is not None
    assert db.session.get(Budget, victim_budget.id) is not None
    assert db.session.get(Account, owner_data['account'].id).balance == Decimal("1000.00")
    # Kategoria ofiary nietknięta wraz z powiązaniem — reset celowo nie rusza słownika.
    assert db.session.get(Category, owner_data['category'].id) is not None
    assert db.session.get(Transaction, owner_data['tx'].id).category_id == owner_data['category'].id


def test_intruder_cannot_delete_foreign_category(intruder_client, owner_data, test_user):
    """Kategoria prywatna ofiary nie może zostać usunięta przez intruza.

    Endpoint adresuje kategorię NAZWĄ, nie ID — dlatego intruz nie musi niczego
    zgadywać, wystarczy że zna nazwę (a nazwy są typowe: "Jedzenie", "Paliwo").
    """
    wlasna = Category(name="Prywatna Ofiary", type="expense", user_token=test_user.token)
    db.session.add(wlasna)
    db.session.commit()
    cat_id = wlasna.id

    resp = intruder_client.delete('/api/categories/Prywatna Ofiary')

    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Category, cat_id).is_active is True


def test_intruder_cannot_delete_global_category(intruder_client, owner_data):
    """Kategoria globalna (user_token IS NULL) jest współdzielona — nikt jej nie usuwa.

    Wcześniej dowolny użytkownik mógł dezaktywować kategorię widoczną dla wszystkich.
    """
    globalna = owner_data['category']  # tworzona bez user_token = globalna
    assert globalna.user_token is None
    cat_id = globalna.id

    resp = intruder_client.delete(f'/api/categories/{globalna.name}')

    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Category, cat_id).is_active is True
