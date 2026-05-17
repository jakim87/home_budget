from datetime import date
from app import db
# Zakładamy, że Account i User zostały zdefiniowane już wcześniej, jak wynika z test_accounts.py
from app.models import User, Account, Category, Transaction, TransactionStaging, Contractor
from app.services.budget_service import save_transactions_to_staging

def test_create_category(app):
    # Action
    category = Category(name="Jedzenie", type="expense")
    db.session.add(category)
    db.session.commit()

    # Assert
    assert category.id is not None
    assert category.name == "Jedzenie"
    assert category.type == "expense"

def test_create_transaction(app):
    # Setup - potrzebujemy konta i kategorii by utworzyć transakcję
    user = User(username="tx_user", email="tx@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()
    
    account = Account(name="Konto Bieżące", bank_name="ING", balance=1500.0, user_id=user.id)
    category = Category(name="Wypłata", type="income")
    db.session.add_all([account, category])
    db.session.commit()

    # Action
    tx = Transaction(
        date=date(2023, 10, 1),
        title="Premia",
        amount=500.0,
        category_id=category.id,
        account_id=account.id,
        user_id=user.id
    )
    db.session.add(tx)
    db.session.commit()

    # Assert
    assert tx.id is not None
    assert tx.amount == 500.0

def test_create_transaction_staging(app):
    """Testuje zapisywanie surowych danych do tabeli stagingowej."""
    # Action
    staging_tx = TransactionStaging(
        date=date(2023, 10, 25),
        title="Wypłata z testu",
        amount=12500.50,
        contractor="Firma X"
    )
    db.session.add(staging_tx)
    db.session.commit()

    # Assert
    assert staging_tx.id is not None
    assert staging_tx.status == 'pending'

def test_save_transactions_to_staging(app):
    """Testuje zapisywanie listy sparsowanych słowników do tabeli stagingowej."""
    # Setup - symulujemy wyjście z parsera parse_ing_csv
    user = User(username="stg_user", email="stg@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()

    cat = Category(name="Jedzenie", type="expense")
    db.session.add(cat)
    db.session.commit()

    contractor = Contractor(name="Biedronka", mapping_rules="biedronka, jeronimo", default_category_id=cat.id, user_id=user.id)
    db.session.add(contractor)
    db.session.commit()

    parsed_data = [
        {
            'date': date(2023, 10, 25),
            'title': 'Zakupy Biedronka Warszawa',
            'amount': 12500.50,
            'contractor': 'Jeronimo Martins'
        },
        {
            'date': date(2023, 10, 28),
            'title': 'Opłata',
            'amount': -7.00,
            'contractor': None
        }
    ]
    
    # Action
    saved = save_transactions_to_staging(parsed_data, user_id=user.id)
    
    # Assert - sprawdzamy, czy funkcja poprawnie zrzuciła dane do bazy
    assert len(saved) == 2
    assert saved[0].id is not None
    assert saved[0].status == 'pending'
    # Sprawdzamy czy pierwsza transakcja otrzymała propozycje
    assert saved[0].proposed_contractor_id == contractor.id
    assert saved[0].proposed_category_id == cat.id
    # Druga nie pasuje do reguł "Biedronka", więc propozycje są puste
    assert saved[1].proposed_contractor_id is None