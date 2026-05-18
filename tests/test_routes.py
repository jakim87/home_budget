import io
from datetime import date
from app import db
from app.models import User, Account, Category, Transaction, TransactionArchive, TransactionStaging, Contractor
from werkzeug.security import generate_password_hash

def login_user_helper(client, username="testuser", password="password"):
    return client.post('/api/login', json={'username': username, 'password': password})

def test_api_init_returns_data_from_db(client, app):
    # SETUP - przygotowanie danych w wyizolowanej bazie testowej
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    account = Account(name="Konto Testowe", bank_name="Bank", balance=100.0, user_id=user_id)
    db.session.add(account)
    db.session.commit()

    cat_expense = Category(name="Jedzenie", type="expense")
    cat_income = Category(name="Wypłata", type="income")
    db.session.add_all([cat_expense, cat_income])
    db.session.commit()

    tx = Transaction(
        date=date(2023, 10, 15),
        title="Zakupy w Biedronce",
        amount=150.50,
        account_id=account.id,
        category_id=cat_expense.id,
        user_id=user_id
    )
    db.session.add(tx)
    db.session.commit()

    # ACTION - symulujemy zapytanie GET od przeglądarki do naszego API
    login_user_helper(client)
    response = client.get('/api/init')
    data = response.get_json()

    # ASSERT - sprawdzamy, czy odpowiedź jest poprawna i zawiera nasze dane
    assert response.status_code == 200
    assert 'categories' in data
    assert 'transactions' in data
    assert 'contractors' in data
    assert 'accounts' in data

    # Sprawdzamy, czy pobrano zapisane kategorie z bazy
    categories = data['categories']
    category_names = [c['name'] for c in categories]
    assert "Jedzenie" in category_names
    assert "Wypłata" in category_names

    # Sprawdzamy, czy pobrano transakcję z bazy i czy ma odpowiednie pola
    transactions = data['transactions']
    assert len(transactions) == 1
    assert transactions[0]['desc'] == "Zakupy w Biedronce"
    assert transactions[0]['amount'] == 150.50
    assert transactions[0]['category'] == "Jedzenie"
    assert transactions[0]['date'] == "2023-10-15"

def test_api_add_category(client, app):
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
    login_user_helper(client)
    # ACTION - symulujemy wysłanie nowej kategorii z formularza na stronie
    response = client.post('/api/categories', json={
        'name': 'Hobby',
        'type': 'expense'
    })

    # ASSERT - sprawdzamy poprawność odpowiedzi
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Hobby'

    # Sprawdzamy czy nowa kategoria faktycznie istnieje w bazie
    with app.app_context():
        cat = db.session.query(Category).filter_by(name='Hobby').first()
        assert cat is not None

def test_delete_transaction_archives_and_removes(client, app):
    # SETUP - wstawienie transakcji, którą będziemy usuwać
    with app.app_context():
        user = User(username="testuser", email="del@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        account = Account(name="DelKonto", bank_name="Bank", balance=100.0, user_id=user.id)
        db.session.add(account)
        db.session.commit()
        tx = Transaction(date=date(2023, 5, 10), title="Transakcja do usunięcia", amount=100.0, account_id=account.id, user_id=user.id)
        db.session.add(tx)
        db.session.commit()
        tx_id = tx.id

    # ACTION - Symulujemy wciśnięcie kosza przez użytkownika
    login_user_helper(client)
    response = client.delete(f'/api/transactions/{tx_id}')
    assert response.status_code == 200

    # ASSERT - weryfikacja przeniesienia w bazie danych
    with app.app_context():
        assert db.session.get(Transaction, tx_id) is None
        archive = db.session.query(TransactionArchive).filter_by(original_id=tx_id).first()
        assert archive is not None
        assert archive.title == "Transakcja do usunięcia"

def test_delete_category_soft_delete(client, app):
    # SETUP - dodanie testowej kategorii
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
    login_user_helper(client)
    with app.app_context():
        cat = Category(name="DoUsuniecia", type="expense", is_active=True)
        db.session.add(cat)
        db.session.commit()

    # ACTION - symulacja wciśnięcia przycisku "Usuń" dla tej kategorii
    response = client.delete('/api/categories/DoUsuniecia')
    assert response.status_code == 200

    # ASSERT - sprawdzamy, czy w bazie ustawiono is_active = False (soft delete)
    with app.app_context():
        cat_in_db = db.session.query(Category).filter_by(name="DoUsuniecia").first()
        assert cat_in_db is not None  # Rekord nadal fizycznie istnieje w bazie!
        assert cat_in_db.is_active is False  # Ale jest oznaczony jako nieaktywny

def test_update_transaction_splits(client, app):
    # SETUP - tworzymy transakcję do podziału
    with app.app_context():
        user = User(username="testuser", email="split@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        
        account = Account(name="KontoSplit", bank_name="Bank", balance=100.0, user_id=user.id)
        cat_main = Category(name="Glowna", type="expense")
        cat_split1 = Category(name="Czesc1", type="expense")
        cat_split2 = Category(name="Czesc2", type="expense")
        db.session.add_all([account, cat_main, cat_split1, cat_split2])
        db.session.commit()
        
        tx = Transaction(
            date=date(2023, 11, 1),
            title="Wielkie Zakupy",
            amount=200.00,
            account_id=account.id,
            category_id=cat_main.id,
            user_id=user.id
        )
        db.session.add(tx)
        db.session.commit()
        tx_id = tx.id

    # ACTION - wysyłamy żądanie PUT z podziałami
    login_user_helper(client)
    response = client.put(f'/api/transactions/{tx_id}', json={
        'splits': [
            {'amount': 150.0, 'desc': 'Spożywcze', 'category': 'Czesc1'},
            {'amount': 50.0, 'desc': 'Chemia', 'category': 'Czesc2'}
        ]
    })
    
    # ASSERT
    assert response.status_code == 200
    
    with app.app_context():
        tx_in_db = db.session.get(Transaction, tx_id)
        assert len(tx_in_db.splits) == 2
        assert tx_in_db.splits[0].amount == 150.0
        assert tx_in_db.splits[0].desc == 'Spożywcze'
        assert tx_in_db.splits[0].category.name == 'Czesc1'

def test_import_ing_csv_endpoint(client, app):
    """Testuje wgrywanie pliku CSV z ING przez endpoint API."""
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        account = Account(name="Test Konto", user_id=user.id)
        db.session.add(account)
        db.session.commit()
        acc_id = account.id
    login_user_helper(client)
    # SETUP - wirtualny plik CSV
    csv_content = """Data transakcji;Data księgowania;Dane kontrahenta;Tytuł;Konto;Bank;Szczegóły;NrTx;Kwota;Waluta
2023-10-25;2023-10-25;Pracodawca;Wypłata;;Bank;;;12500,50;PLN
2023-10-28;2023-10-28;;Opłata za kartę;;Bank;;;-7,00;PLN
"""
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'test_ing.csv'),
        'account_id': acc_id
    }

    # ACTION - symulacja wgrania pliku w formularzu (multipart/form-data)
    response = client.post('/api/import/ing', data=data, content_type='multipart/form-data')

    # ASSERT
    assert response.status_code == 201
    resp_data = response.get_json()
    assert resp_data['count'] == 2

    with app.app_context():
        staged = db.session.query(TransactionStaging).all()
        assert len(staged) == 2
        assert staged[0].title == "Wypłata"

def test_get_pending_staging_transactions(client, app):
    """Testuje pobieranie oczekujących (pending) transakcji ze stagingu."""
    # SETUP
    with app.app_context():
        user = User(username="testuser", email="stg@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()

        stg1 = TransactionStaging(date=date(2023, 11, 1), amount=100.0, title="Pending TX", status="pending", user_id=user.id)
        stg2 = TransactionStaging(date=date(2023, 11, 2), amount=200.0, title="Approved TX", status="approved", user_id=user.id)
        db.session.add_all([stg1, stg2])
        db.session.commit()

    # ACTION
    login_user_helper(client)
    response = client.get('/api/staging/pending')
    
    # ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['title'] == "Pending TX"
    assert data[0]['status'] == "pending"

def test_approve_staging_transaction(client, app):
    """Testuje zatwierdzanie transakcji ze stagingu i przeniesienie jej do głównej tabeli."""
    # SETUP
    with app.app_context():
        user = User(username="testuser", email="appr@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()

        account = Account(name="Konto Appr", bank_name="Bank", balance=100.0, user_id=user.id)
        cat = Category(name="Jedzenie", type="expense")
        db.session.add_all([account, cat])
        db.session.commit()

        cont = Contractor(name="Biedronka", user_id=user.id)
        db.session.add(cont)
        db.session.commit()

        stg = TransactionStaging(date=date(2023, 11, 5), amount=-50.0, title="Zakupy", status="pending", user_id=user.id, account_id=account.id, proposed_category_id=cat.id)
        db.session.add(stg)
        db.session.commit()
        stg_id = stg.id
        cont_id = cont.id
        account_id = account.id

    # ACTION - Próba zatwierdzenia bez kontrahenta
    login_user_helper(client)
    resp_fail = client.post(f'/api/staging/{stg_id}/approve', json={'category': 'Jedzenie'})
    assert resp_fail.status_code == 400

    # ACTION - Wysyłamy poprawne żądanie zatwierdzenia transakcji
    response = client.post(f'/api/staging/{stg_id}/approve', json={'category': 'Jedzenie', 'contractor_id': cont_id})
    assert response.status_code == 200

    # ASSERT
    with app.app_context():
        # 1. Rekord powinien zostać usunięty z poczekalni (przeniesiony)
        assert db.session.get(TransactionStaging, stg_id) is None
        # 2. Transakcja główna powinna powstać
        new_tx = db.session.query(Transaction).filter_by(title="Zakupy").first()
        assert new_tx is not None
        # 3. Saldo powinno zostać przeliczone przez serwis
        assert float(db.session.get(Account, account_id).balance) == 50.0

def test_clear_staging_transactions(client, app):
    """Testuje masowe usuwanie (odrzucanie) transakcji ze stagingu."""
    with app.app_context():
        user = User(username="testuser", email="clear@test.com", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()

        stg1 = TransactionStaging(date=date(2023, 11, 1), amount=100.0, title="T1", status="pending", user_id=user.id)
        stg2 = TransactionStaging(date=date(2023, 11, 2), amount=200.0, title="T2", status="pending", user_id=user.id)
        db.session.add_all([stg1, stg2])
        db.session.commit()
        user_id = user.id

    # ACTION
    login_user_helper(client)
    response = client.delete('/api/staging/pending')
    assert response.status_code == 200

    # ASSERT
    with app.app_context():
        staged = db.session.query(TransactionStaging).filter_by(user_id=user_id, status='pending').all()
        assert len(staged) == 0