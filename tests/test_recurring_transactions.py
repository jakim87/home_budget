import pytest
from datetime import date
from app import db
from app.models import User, Account, Category, RecurringTransaction, Frequency
from werkzeug.security import generate_password_hash
from decimal import Decimal

def login_user_helper(client, username="testuser", password="password"):
    return client.post('/api/login', json={'username': username, 'password': password})

@pytest.fixture
def setup_for_recurring(app, test_user_token):
    """Przygotowuje konto i kategorię dla testów transakcji cyklicznych."""
    with app.app_context():
        account = Account(name="Konto Cykliczne", bank_name="Bank", balance=1000.0, user_token=test_user_token)
        category = Category(name="Czynsz", type="expense")
        db.session.add_all([account, category])
        db.session.commit()
        return test_user_token, account.id, category.id

def test_api_add_recurring_transaction(client, app, setup_for_recurring):
    """
    (RED) Test - Sprawdza, czy można dodać definicję transakcji cyklicznej przez API.
    """
    user_token, account_id, category_id = setup_for_recurring
    login_user_helper(client)

    response = client.post('/api/recurring-transactions/', json={
        'title': 'Miesięczny czynsz',
        'amount': "-1500.00",
        'account_id': account_id,
        'category_id': category_id,
        'frequency': 'monthly',
        'day_of_month': 10,
        'start_date': '2024-06-01'
    })

    assert response.status_code == 201
    response_data = response.get_json()
    assert 'id' in response_data
    assert response_data['message'] == 'Recurring transaction created'

    with app.app_context():
        rec_tx = db.session.query(RecurringTransaction).filter_by(title='Miesięczny czynsz').first()
        assert rec_tx is not None
        assert rec_tx.id == response_data['id']
        assert rec_tx.user_token == user_token
        assert rec_tx.day_of_month == 10

def test_api_list_recurring_transactions(client, app, setup_for_recurring):
    """
    (RED) Test - Sprawdza, czy API poprawnie listuje definicje transakcji cyklicznych.
    """
    user_token, account_id, category_id = setup_for_recurring
    login_user_helper(client)

    with app.app_context():
        rt1 = RecurringTransaction(
            user_token=user_token,
            account_id=account_id,
            title="Czynsz",
            amount=Decimal("-1500.00"),
            frequency=Frequency.MONTHLY,
            day_of_month=10,
            start_date=date(2024, 1, 1),
            next_run_date=date(2024, 6, 10)
        )
        rt2 = RecurringTransaction(
            user_token=user_token,
            account_id=account_id,
            title="Abonament Netflix",
            amount=Decimal("-50.00"),
            frequency=Frequency.MONTHLY,
            day_of_month=20,
            start_date=date(2024, 1, 1),
            next_run_date=date(2024, 6, 20)
        )
        other_user = User(username="otheruser", email="other@test.com", password_hash=generate_password_hash("password"))
        db.session.add(other_user)
        db.session.commit()
        rt3 = RecurringTransaction(user_token=other_user.token, account_id=account_id, title="Inny Czynsz", amount=Decimal("-1000.00"), frequency=Frequency.MONTHLY, day_of_month=1, start_date=date(2024, 1, 1), next_run_date=date(2024, 6, 1))
        db.session.add_all([rt1, rt2, rt3])
        db.session.commit()

    response = client.get('/api/recurring-transactions/')

    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2

    titles = {item['title'] for item in data}
    assert "Czynsz" in titles
    assert "Abonament Netflix" in titles
    assert "Inny Czynsz" not in titles

    czynsz_data = next(item for item in data if item['title'] == 'Czynsz')
    assert czynsz_data['amount'] == "-1500.00"
    assert czynsz_data['frequency'] == 'monthly'

def test_api_update_recurring_transaction(client, app, setup_for_recurring):
    """
    (RED) Test - Sprawdza, czy można zaktualizować definicję transakcji cyklicznej przez API.
    """
    user_token, account_id, category_id = setup_for_recurring
    login_user_helper(client)

    with app.app_context():
        rec_tx = RecurringTransaction(
            user_token=user_token,
            account_id=account_id,
            title="Stary Czynsz",
            amount=Decimal("-1000.00"),
            frequency=Frequency.MONTHLY,
            day_of_month=5,
            start_date=date(2024, 1, 1),
            next_run_date=date(2024, 6, 5)
        )
        db.session.add(rec_tx)
        db.session.commit()
        rec_tx_id = rec_tx.id

    updated_data = {
        'title': 'Nowy Czynsz',
        'amount': "-1200.00",
        'day_of_month': 15,
        'is_active': False
    }
    response = client.put(f'/api/recurring-transactions/{rec_tx_id}', json=updated_data)

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == rec_tx_id
    assert response_data['title'] == 'Nowy Czynsz'
    assert response_data['amount'] == '-1200.00'
    assert response_data['is_active'] is False

    with app.app_context():
        updated_rec_tx = db.session.get(RecurringTransaction, rec_tx_id)
        assert updated_rec_tx.title == 'Nowy Czynsz'
        assert updated_rec_tx.amount == Decimal("-1200.00")
        assert updated_rec_tx.day_of_month == 15
        assert updated_rec_tx.is_active is False

def test_api_delete_recurring_transaction_blocked(client, app, setup_for_recurring):
    """
    Usunięcie transakcji cyklicznej przez API jest zablokowane (405).
    Zamiast tego użytkownik powinien ustawić datę zakończenia.
    """
    user_token, account_id, category_id = setup_for_recurring
    login_user_helper(client)

    with app.app_context():
        rec_tx = RecurringTransaction(
            user_token=user_token,
            account_id=account_id,
            title="Do zakończenia",
            amount=Decimal("-200.00"),
            frequency=Frequency.MONTHLY,
            day_of_month=1,
            start_date=date(2024, 1, 1),
            next_run_date=date(2024, 6, 1)
        )
        db.session.add(rec_tx)
        db.session.commit()
        rec_tx_id = rec_tx.id

    response = client.delete(f'/api/recurring-transactions/{rec_tx_id}')

    assert response.status_code == 405
    response_data = response.get_json()
    assert 'error' in response_data
    assert 'datę zakończenia' in response_data['error']

    with app.app_context():
        still_exists = db.session.get(RecurringTransaction, rec_tx_id)
        assert still_exists is not None
