from decimal import Decimal
from app.models import User, Account, Transaction, Category
from app.services.budget_service import reconcile_account_balance
from app import db

def test_reconcile_balance_with_positive_difference(app):
    """
    Testuje, czy uzgadnianie salda poprawnie tworzy transakcję dodatnią,
    gdy nowe saldo jest wyższe od bieżącego.
    """
    with app.app_context():
        # 1. Przygotowanie danych (Arrange)
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("1000.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        # 2. Wywołanie funkcji (Act)
        new_balance = Decimal("1150.50")
        reconciliation_tx = reconcile_account_balance(user.id, account.id, new_balance)

        # 3. Sprawdzenie wyników (Assert)
        assert reconciliation_tx is not None
        assert reconciliation_tx.amount == Decimal("150.50")
        assert reconciliation_tx.title == "Uzgadnianie salda"
        
        # Sprawdź, czy saldo konta zostało poprawnie zaktualizowane
        updated_account = db.session.get(Account, account.id)
        assert updated_account.balance == new_balance

        # Sprawdź, czy kategoria systemowa została użyta
        category = db.session.get(Category, reconciliation_tx.category_id)
        assert category.name == "Uzgadnianie salda"
        assert category.is_system_category is True

def test_reconcile_balance_with_negative_difference(app):
    """
    Testuje, czy uzgadnianie salda poprawnie tworzy transakcję ujemną,
    gdy nowe saldo jest niższe od bieżącego.
    """
    with app.app_context():
        # 1. Arrange
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("1000.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        # 2. Act
        new_balance = Decimal("950.25")
        reconciliation_tx = reconcile_account_balance(user.id, account.id, new_balance)

        # 3. Assert
        assert reconciliation_tx is not None
        assert reconciliation_tx.amount == Decimal("-49.75")
        
        updated_account = db.session.get(Account, account.id)
        assert updated_account.balance == new_balance

def test_reconcile_balance_with_no_difference(app):
    """
    Testuje, czy funkcja nie tworzy transakcji, gdy saldo jest zgodne.
    """
    with app.app_context():
        # 1. Arrange
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("1000.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        # 2. Act
        new_balance = Decimal("1000.00")
        reconciliation_tx = reconcile_account_balance(user.id, account.id, new_balance)

        # 3. Assert
        assert reconciliation_tx is None
        
        updated_account = db.session.get(Account, account.id)
        assert updated_account.balance == Decimal("1000.00")

def test_reconcile_creates_system_category_if_not_exists(app):
    """
    Testuje, czy kategoria systemowa jest tworzona, jeśli nie istnieje w bazie.
    """
    with app.app_context():
        user = User(username="testuser", email="test@test.com", password_hash="hash")
        account = Account(name="Test Account", bank_name="Test Bank", balance=Decimal("100.00"), user=user)
        db.session.add_all([user, account])
        db.session.commit()

        reconcile_account_balance(user.id, account.id, Decimal("120.00"))
        
        category = db.session.query(Category).filter_by(name="Uzgadnianie salda").one()
        assert category is not None
        assert category.is_system_category is True