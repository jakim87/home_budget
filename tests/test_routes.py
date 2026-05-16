import pytest
from datetime import date
from app import db
from app.models import User, Account, Category, Transaction, TransactionArchive

def test_api_init_returns_data_from_db(client, app):
    # SETUP - przygotowanie danych w wyizolowanej bazie testowej
    user = User(username="testuser", email="test@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    account = Account(name="Konto Testowe", bank_name="Bank", balance=100.0, user_id=user.id)
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
        user_id=user.id
    )
    db.session.add(tx)
    db.session.commit()

    # ACTION - symulujemy zapytanie GET od przeglądarki do naszego API
    response = client.get('/api/init')
    data = response.get_json()

    # ASSERT - sprawdzamy, czy odpowiedź jest poprawna i zawiera nasze dane
    assert response.status_code == 200
    assert 'categories' in data
    assert 'transactions' in data

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
        user = User(username="deluser", email="del@test.com", password_hash="hash")
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
    response = client.delete(f'/api/transactions/{tx_id}')
    assert response.status_code == 200

    # ASSERT - weryfikacja przeniesienia w bazie danych
    with app.app_context():
        assert db.session.get(Transaction, tx_id) is None
        archive = db.session.query(TransactionArchive).filter_by(original_id=tx_id).first()
        assert archive is not None
        assert archive.title == "Transakcja do usunięcia"