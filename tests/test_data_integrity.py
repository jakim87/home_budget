"""Testy poprawek integralności danych finansowych (branch fix/data-layer-critical-important)."""
from datetime import date
from decimal import Decimal

from app import db
from app.models import (
    User, Account, Category, Contractor, Transaction,
    RecurringTransaction, PlannedTransaction, Frequency,
)
from app.services.budget_service import create_transaction
from app.services.transaction_service import update_transaction
from app.services.recurring_service import process_recurring_transactions
from app.services.planned_transaction_service import process_planned_transactions


def _make_user():
    user = User(username="di_user", email="di@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()
    return user


def test_update_amount_corrects_account_balance(app):
    """Edycja kwoty transakcji musi skorygować saldo konta o różnicę."""
    with app.app_context():
        user = _make_user()
        account = Account(name="Konto", bank_name="Bank", balance=Decimal("100.00"), user_token=user.token)
        db.session.add(account)
        db.session.commit()

        tx = create_transaction(user.token, account.id, Decimal("-100.00"), "Zakup", date(2024, 1, 1))
        assert db.session.get(Account, account.id).balance == Decimal("0.00")

        update_transaction(user.token, tx.id, {"amount": "-150.00"})

        assert db.session.get(Account, account.id).balance == Decimal("-50.00")
        assert db.session.get(Transaction, tx.id).amount == Decimal("-150.00")


def test_recurring_processing_is_idempotent(app):
    """Ponowne uruchomienie przetwarzania nie tworzy drugiej transakcji dla tej samej daty."""
    with app.app_context():
        user = _make_user()
        account = Account(name="Konto", bank_name="Bank", balance=Decimal("0.00"), user_token=user.token)
        db.session.add(account)
        db.session.commit()

        rec = RecurringTransaction(
            user_token=user.token, account_id=account.id, title="Czynsz",
            amount=Decimal("-1000.00"), frequency=Frequency.MONTHLY, day_of_month=1,
            start_date=date(2024, 1, 1), next_run_date=date(2024, 1, 1),
        )
        db.session.add(rec)
        db.session.commit()
        due_date = rec.next_run_date

        created = process_recurring_transactions()
        assert created == 1
        assert db.session.query(Transaction).filter_by(source_recurring_id=rec.id).count() == 1

        # Symulacja awarii: cofamy next_run_date na datę, dla której transakcja już istnieje.
        rec = db.session.get(RecurringTransaction, rec.id)
        rec.next_run_date = due_date
        db.session.commit()

        created_again = process_recurring_transactions()
        assert created_again == 0  # strażnik idempotentności zablokował duplikat
        assert db.session.query(Transaction).filter_by(source_recurring_id=rec.id, date=due_date).count() == 1


def test_planned_processing_is_idempotent(app):
    """Zaplanowana transakcja już wykonana dla danej daty nie powstaje ponownie."""
    with app.app_context():
        user = _make_user()
        account = Account(name="Konto", bank_name="Bank", balance=Decimal("0.00"), user_token=user.token)
        db.session.add(account)
        db.session.commit()

        pt = PlannedTransaction(
            user_token=user.token, account_id=account.id, title="Ubezpieczenie",
            amount=Decimal("-300.00"), execution_date=date(2024, 1, 5), status="pending",
        )
        db.session.add(pt)
        db.session.commit()

        assert process_planned_transactions() == 1
        assert db.session.query(Transaction).filter_by(source_planned_id=pt.id).count() == 1

        # Ręczne cofnięcie statusu — mimo to duplikat nie powstaje (istnieje już transakcja z tej definicji).
        db.session.get(PlannedTransaction, pt.id).status = "pending"
        db.session.commit()
        assert process_planned_transactions() == 0
        assert db.session.query(Transaction).filter_by(source_planned_id=pt.id).count() == 1


def test_two_identical_transfers_create_two_mirrors(app):
    """Dwa identyczne przelewy tego samego dnia tworzą DWA odrębne lustra (brak fałszywej deduplikacji)."""
    with app.app_context():
        user = _make_user()
        acc_a = Account(name="Konto A", bank_name="Bank", balance=Decimal("2000.00"), user_token=user.token)
        acc_b = Account(name="Konto B", bank_name="Bank", balance=Decimal("0.00"), user_token=user.token)
        db.session.add_all([acc_a, acc_b])
        db.session.commit()

        transfer_cat = Category(name="Przelew wewnętrzny", type="transfer")
        db.session.add(transfer_cat)
        db.session.commit()

        cont_to_b = Contractor(
            name="Moje konto: Konto B", user_token=user.token,
            default_category_id=transfer_cat.id, linked_account_id=acc_b.id,
        )
        db.session.add(cont_to_b)
        db.session.commit()

        for _ in range(2):
            create_transaction(
                user.token, acc_a.id, Decimal("500.00"), "Przelew do B", date(2024, 2, 1),
                category_id=transfer_cat.id, contractor_id=cont_to_b.id,
            )

        # Dwa lustra po stronie B, saldo B = 1000, każde powiązane z inną stroną źródłową.
        mirrors = db.session.query(Transaction).filter_by(account_id=acc_b.id).all()
        assert len(mirrors) == 2
        assert db.session.get(Account, acc_b.id).balance == Decimal("1000.00")
        assert all(m.linked_transaction_id is not None for m in mirrors)

        # Strona źródłowa: dwa wypływy po -500, saldo A = 2000 - 1000 = 1000.
        sources = db.session.query(Transaction).filter_by(account_id=acc_a.id).all()
        assert len(sources) == 2
        assert all(s.amount == Decimal("-500.00") for s in sources)
        assert db.session.get(Account, acc_a.id).balance == Decimal("1000.00")


def test_transfer_resolves_by_linked_account_after_rename(app):
    """Zmiana nazwy konta docelowego nie psuje przelewu — powiązanie idzie po linked_account_id."""
    with app.app_context():
        user = _make_user()
        acc_a = Account(name="Konto A", bank_name="Bank", balance=Decimal("1000.00"), user_token=user.token)
        acc_b = Account(name="Stara Nazwa", bank_name="Bank", balance=Decimal("0.00"), user_token=user.token)
        db.session.add_all([acc_a, acc_b])
        db.session.commit()

        transfer_cat = Category(name="Przelew wewnętrzny", type="transfer")
        db.session.add(transfer_cat)
        db.session.commit()

        cont_to_b = Contractor(
            name="Moje konto: Stara Nazwa", user_token=user.token,
            default_category_id=transfer_cat.id, linked_account_id=acc_b.id,
        )
        db.session.add(cont_to_b)
        db.session.commit()

        # Konto docelowe zmienia nazwę — kontrahent zachowuje starą etykietę.
        db.session.get(Account, acc_b.id).name = "Nowa Nazwa"
        db.session.commit()

        create_transaction(
            user.token, acc_a.id, Decimal("200.00"), "Przelew", date(2024, 3, 1),
            category_id=transfer_cat.id, contractor_id=cont_to_b.id,
        )

        assert db.session.get(Account, acc_b.id).balance == Decimal("200.00")
