import io
from datetime import date
from decimal import Decimal
from app import db
from app.models import Account, Category, Transaction, TransactionArchive, TransactionStaging, Contractor

def test_api_init_returns_data_from_db(logged_in_client, app, test_user_token):
    # SETUP
    account = Account(name="Konto Testowe", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    db.session.add(account)
    db.session.commit()

    cat_expense = Category(name="Jedzenie", type="expense")
    cat_income = Category(name="Wypłata", type="income")
    db.session.add_all([cat_expense, cat_income])
    db.session.commit()

    tx = Transaction(
        date=date(2023, 10, 15),
        title="Zakupy w Biedronce",
        amount=Decimal("150.50"),
        account_id=account.id,
        category_id=cat_expense.id,
        user_token=test_user_token
    )
    db.session.add(tx)
    db.session.commit()

    # ACTION
    response = logged_in_client.get('/api/init')
    data = response.get_json()

    # ASSERT
    assert response.status_code == 200
    assert 'categories' in data
    assert 'transactions' in data
    assert 'contractors' in data
    assert 'accounts' in data

    categories = data['categories']
    category_names = [c['name'] for c in categories]
    assert "Jedzenie" in category_names
    assert "Wypłata" in category_names

    transactions = data['transactions']
    assert len(transactions) == 1
    assert transactions[0]['desc'] == "Zakupy w Biedronce"
    assert transactions[0]['amount'] == 150.50  # kontrakt API: kwoty w JSON jako liczby
    assert transactions[0]['category'] == "Jedzenie"
    assert transactions[0]['date'] == "2023-10-15"

def test_api_add_category(logged_in_client, app):
    response = logged_in_client.post('/api/categories', json={
        'name': 'Hobby',
        'type': 'expense'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Hobby'

    cat = db.session.query(Category).filter_by(name='Hobby').first()
    assert cat is not None

def test_delete_transaction_archives_and_removes(logged_in_client, app, test_user_token):
    # SETUP
    account = Account(name="DelKonto", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    db.session.add(account)
    db.session.commit()
    tx = Transaction(date=date(2023, 5, 10), title="Transakcja do usunięcia", amount=Decimal("100.00"), account_id=account.id, user_token=test_user_token)
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id

    # ACTION
    response = logged_in_client.delete(f'/api/transactions/{tx_id}')
    assert response.status_code == 200

    # ASSERT
    assert db.session.get(Transaction, tx_id) is None
    archive = db.session.query(TransactionArchive).filter_by(original_id=tx_id).first()
    assert archive is not None
    assert archive.title == "Transakcja do usunięcia"

def test_delete_category_soft_delete(logged_in_client, app, test_user_token):
    # SETUP — kategoria własna użytkownika (globalnych nie da się usunąć)
    cat = Category(name="DoUsuniecia", type="expense", is_active=True, user_token=test_user_token)
    db.session.add(cat)
    db.session.commit()

    # ACTION
    response = logged_in_client.delete('/api/categories/DoUsuniecia')
    assert response.status_code == 200

    # ASSERT
    cat_in_db = db.session.query(Category).filter_by(name="DoUsuniecia").first()
    assert cat_in_db is not None
    assert cat_in_db.is_active is False

def test_update_transaction_splits(logged_in_client, app, test_user_token):
    # SETUP
    account = Account(name="KontoSplit", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    cat_main = Category(name="Glowna", type="expense")
    cat_split1 = Category(name="Czesc1", type="expense")
    cat_split2 = Category(name="Czesc2", type="expense")
    db.session.add_all([account, cat_main, cat_split1, cat_split2])
    db.session.commit()

    tx = Transaction(date=date(2023, 11, 1), title="Wielkie Zakupy", amount=Decimal("200.00"), account_id=account.id, category_id=cat_main.id, user_token=test_user_token)
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id

    # ACTION
    response = logged_in_client.put(f'/api/transactions/{tx_id}', json={
        'splits': [
            {'amount': 150.0, 'desc': 'Spożywcze', 'category': 'Czesc1'},
            {'amount': 50.0, 'desc': 'Chemia', 'category': 'Czesc2'}
        ]
    })

    # ASSERT
    assert response.status_code == 200

    tx_in_db = db.session.get(Transaction, tx_id)
    assert len(tx_in_db.splits) == 2
    assert tx_in_db.splits[0].amount == Decimal("150.00")
    assert tx_in_db.splits[0].desc == 'Spożywcze'
    assert tx_in_db.splits[0].category.name == 'Czesc1'

def test_update_transaction_rejects_malformed_amount(logged_in_client, app, test_user_token):
    """Błędna kwota w PUT to 400 (walidacja wejścia), nie 500.

    decimal.InvalidOperation NIE dziedziczy po ValueError, więc bez schematu
    Marshmallow ten przypadek wychodził globalnym handlerem jako 500 — patrz
    przegląd kodu 2026-08-16, punkt B4."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    db.session.add(account)
    db.session.commit()
    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-50.00"),
                     account_id=account.id, user_token=test_user_token)
    db.session.add(tx)
    db.session.commit()
    tx_id, old_balance = tx.id, account.balance

    response = logged_in_client.put(f'/api/transactions/{tx_id}', json={'amount': 'abc'})

    assert response.status_code == 400
    db.session.expire_all()
    # Saldo i kwota nietknięte — odrzucenie nastąpiło przed jakąkolwiek zmianą.
    assert db.session.get(Transaction, tx_id).amount == Decimal("-50.00")
    assert db.session.get(Account, account.id).balance == old_balance


def test_update_transaction_rejects_malformed_date(logged_in_client, app, test_user_token):
    """Błędny format daty w PUT to 400, a transakcja zostaje bez zmian."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    db.session.add(account)
    db.session.commit()
    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-50.00"),
                     account_id=account.id, user_token=test_user_token)
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id

    response = logged_in_client.put(f'/api/transactions/{tx_id}', json={'date': '10-01-2024'})

    assert response.status_code == 400
    db.session.expire_all()
    assert db.session.get(Transaction, tx_id).date == date(2024, 1, 10)


def test_update_transaction_accepts_valid_payload(logged_in_client, app, test_user_token):
    """Poprawny payload (data + kwota + komentarz) nadal przechodzi — walidacja
    nie może zablokować normalnej edycji inline z frontu."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    category = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, category])
    db.session.commit()
    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-50.00"),
                     account_id=account.id, category_id=category.id, user_token=test_user_token)
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id

    response = logged_in_client.put(f'/api/transactions/{tx_id}', json={
        'date': '2024-02-15', 'desc': 'Zakupy poprawione', 'amount': '-75.00',
        'category': 'Jedzenie', 'comment': 'komentarz',
    })

    assert response.status_code == 200
    db.session.expire_all()
    updated = db.session.get(Transaction, tx_id)
    assert updated.date == date(2024, 2, 15)
    assert updated.title == 'Zakupy poprawione'
    assert updated.amount == Decimal("-75.00")
    assert updated.comment == 'komentarz'
    # Saldo skorygowane o różnicę kwoty (-50 -> -75 to -25 na koncie).
    assert db.session.get(Account, account.id).balance == Decimal("75.00")


def test_partial_update_does_not_wipe_unsent_fields(logged_in_client, app, test_user_token):
    """Edycja częściowa rusza WYŁĄCZNIE pola obecne w żądaniu.

    Zabezpieczenie przed cichą utratą danych: gdyby schemat dowstawiał do żądania
    swoje `load_default` (splits=[], comment=None, contractor_id=None), to zmiana
    samej kwoty kasowałaby podziały, komentarz i kontrahenta. `partial=True` to
    dziś blokuje, ale to niejawne zachowanie Marshmallow — ten test je przypina."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    category = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, category])
    db.session.commit()
    contractor = Contractor(name="Biedronka", user_token=test_user_token)
    db.session.add(contractor)
    db.session.commit()

    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-100.00"),
                     account_id=account.id, category_id=category.id, user_token=test_user_token,
                     contractor_id=contractor.id, comment="ważny komentarz")
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id
    logged_in_client.put(f'/api/transactions/{tx_id}', json={
        'splits': [{'amount': 60.0, 'desc': 'Spożywcze', 'category': 'Jedzenie'}]
    })

    # ACTION — żądanie zawiera WYŁĄCZNIE kwotę
    response = logged_in_client.put(f'/api/transactions/{tx_id}', json={'amount': '-120.00'})

    assert response.status_code == 200
    db.session.expire_all()
    updated = db.session.get(Transaction, tx_id)
    assert updated.amount == Decimal("-120.00")
    assert updated.comment == "ważny komentarz"
    assert updated.contractor_id == contractor.id
    assert len(updated.splits) == 1
    assert updated.splits[0].desc == 'Spożywcze'


def test_update_transaction_splits_tolerate_client_side_ids(logged_in_client, app, test_user_token):
    """Front wysyła podziały ze swoim `id` (dla nowych wierszy tymczasowym, z Date.now()).
    Schemat ma je ignorować, nie odrzucać całego żądania."""
    account = Account(name="Konto", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    category = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, category])
    db.session.commit()
    tx = Transaction(date=date(2024, 1, 10), title="Zakupy", amount=Decimal("-100.00"),
                     account_id=account.id, category_id=category.id, user_token=test_user_token)
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id

    response = logged_in_client.put(f'/api/transactions/{tx_id}', json={
        'splits': [{'id': 1723800000000.123, 'amount': 40.0, 'desc': 'Nowa pozycja', 'category': 'Jedzenie'}]
    })

    assert response.status_code == 200
    db.session.expire_all()
    splits = db.session.get(Transaction, tx_id).splits
    assert len(splits) == 1
    # Klient nie decyduje o ID — baza nadaje własne.
    assert splits[0].id != 1723800000000
    assert splits[0].desc == 'Nowa pozycja'


def test_import_ing_csv_endpoint(logged_in_client, app, test_user_token):
    """Testuje wgrywanie pliku CSV z ING przez endpoint API."""
    account = Account(name="Test Konto", bank_name="Bank", user_token=test_user_token)
    db.session.add(account)
    db.session.commit()
    acc_id = account.id

    csv_content = """Data transakcji;Data księgowania;Dane kontrahenta;Tytuł;Nr rachunku;Konto;Bank;Szczegóły;NrTx;Kwota transakcji;Waluta
2023-10-25;2023-10-25;Pracodawca;Wypłata;;;Bank;;;12500,50;PLN
2023-10-28;2023-10-28;;Opłata za kartę;;;Bank;;;-7,00;PLN
"""
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'test_ing.csv'),
        'account_id': acc_id
    }

    response = logged_in_client.post('/api/import/ing', data=data, content_type='multipart/form-data')

    assert response.status_code == 201
    resp_data = response.get_json()
    assert resp_data['count'] == 2

    staged = db.session.query(TransactionStaging).all()
    assert len(staged) == 2
    assert staged[0].title == "Wypłata"

def test_get_pending_staging_transactions(logged_in_client, app, test_user_token):
    """Testuje pobieranie oczekujących (pending) transakcji ze stagingu."""
    # SETUP
    stg1 = TransactionStaging(date=date(2023, 11, 1), amount=Decimal("100.00"), title="Pending TX", status="pending", user_token=test_user_token)
    stg2 = TransactionStaging(date=date(2023, 11, 2), amount=Decimal("200.00"), title="Approved TX", status="approved", user_token=test_user_token)
    db.session.add_all([stg1, stg2])
    db.session.commit()

    # ACTION
    response = logged_in_client.get('/api/staging/pending')

    # ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['title'] == "Pending TX"
    assert data[0]['status'] == "pending"

def test_approve_staging_transaction(logged_in_client, app, test_user_token):
    """Testuje zatwierdzanie transakcji ze stagingu i przeniesienie jej do głównej tabeli."""
    # SETUP
    account = Account(name="Konto Appr", bank_name="Bank", balance=Decimal("100.00"), user_token=test_user_token)
    cat = Category(name="Jedzenie", type="expense")
    db.session.add_all([account, cat])
    db.session.commit()

    cont = Contractor(name="Biedronka", user_token=test_user_token)
    db.session.add(cont)
    db.session.commit()

    stg = TransactionStaging(date=date(2023, 11, 5), amount=Decimal("-50.00"), title="Zakupy", status="pending", user_token=test_user_token, account_id=account.id, proposed_category_id=cat.id)
    db.session.add(stg)
    db.session.commit()
    stg_id = stg.id
    cont_id = cont.id
    account_id = account.id

    # ACTION - Próba zatwierdzenia bez kontrahenta
    resp_fail = logged_in_client.post(f'/api/staging/{stg_id}/approve', json={'category': 'Jedzenie'})
    assert resp_fail.status_code == 400

    # ACTION - Wysyłamy poprawne żądanie zatwierdzenia transakcji
    response = logged_in_client.post(f'/api/staging/{stg_id}/approve', json={'category': 'Jedzenie', 'contractor_id': cont_id})
    assert response.status_code == 200

    # ASSERT
    assert db.session.get(TransactionStaging, stg_id) is None
    new_tx = db.session.query(Transaction).filter_by(title="Zakupy").first()
    assert new_tx is not None
    assert db.session.get(Account, account_id).balance == Decimal("50.00")

def test_clear_staging_transactions(logged_in_client, app, test_user_token):
    """Testuje masowe usuwanie (odrzucanie) transakcji ze stagingu."""
    stg1 = TransactionStaging(date=date(2023, 11, 1), amount=Decimal("100.00"), title="T1", status="pending", user_token=test_user_token)
    stg2 = TransactionStaging(date=date(2023, 11, 2), amount=Decimal("200.00"), title="T2", status="pending", user_token=test_user_token)
    db.session.add_all([stg1, stg2])
    db.session.commit()

    # ACTION
    response = logged_in_client.delete('/api/staging/pending')
    assert response.status_code == 200

    # ASSERT
    staged = db.session.query(TransactionStaging).filter_by(user_token=test_user_token, status='pending').all()
    assert len(staged) == 0
