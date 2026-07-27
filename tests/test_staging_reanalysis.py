"""Naprawa: "Odśwież mapowanie" (reanalyze_all_staging) kasowało rozpoznanie
przelewów wewnętrznych. Przyczyna: TransactionStaging nie przechowywało numeru
konta kontrahenta (counterparty_account) z wyciągu, więc ponowna analiza nie
mogła wykonać kroku 1 (dopasowanie po IBAN) z analyze_transaction_data —
jedynie pierwszy import (save_transactions_to_staging) miał do niego dostęp."""
from datetime import date
from decimal import Decimal

from app import db
from app.models import User, Account, Category, Contractor
from app.services.budget_service import save_transactions_to_staging, reanalyze_all_staging


def _users_with_accounts(app):
    user = User(username="stg_reanalysis_user", email="sru@test.com", password_hash="hash")
    db.session.add(user)
    db.session.commit()
    acc_a = Account(name="Konto A", bank_name="ING", user_token=user.token,
                    account_number="45 1050 1025 1000 0091 0293 0329")
    acc_b = Account(name="Konto B", bank_name="ING", user_token=user.token,
                    account_number="72 1050 1025 1000 0091 1144 0914")
    db.session.add_all([acc_a, acc_b])
    db.session.commit()
    return user, acc_a, acc_b


def test_save_transactions_to_staging_persists_counterparty_account(app):
    """Round-trip: numer konta kontrahenta z wiersza parsera trafia do kolumny
    TransactionStaging.counterparty_account (a nie tylko do jednorazowej analizy)."""
    user, acc_a, acc_b = _users_with_accounts(app)
    parsed = [{
        'date': date(2024, 6, 1), 'title': 'Przelew środków',
        'amount': Decimal("-300.00"), 'contractor': 'Jan Kowalski',
        'account_id': acc_a.id, 'counterparty_account': acc_b.account_number.replace(' ', ''),
    }]

    saved = save_transactions_to_staging(parsed, user_token=user.token)

    assert saved[0].counterparty_account == acc_b.account_number.replace(' ', '')


def test_reanalyze_all_staging_preserves_internal_transfer_recognition(app):
    """RED przed naprawą: 'Odśwież mapowanie' musi wykryć przelew wewnętrzny
    identycznie jak pierwszy import — nie może zgubić dopasowania po IBAN."""
    user, acc_a, acc_b = _users_with_accounts(app)
    parsed = [{
        'date': date(2024, 6, 1), 'title': 'Przelew środków',
        'amount': Decimal("-300.00"), 'contractor': 'Jan Kowalski',
        'account_id': acc_a.id, 'counterparty_account': acc_b.account_number.replace(' ', ''),
    }]
    saved = save_transactions_to_staging(parsed, user_token=user.token)
    stg = saved[0]

    transfer_cat = db.session.query(Category).filter_by(name="Przelew wewnętrzny", type="transfer").first()
    transfer_cont = db.session.query(Contractor).filter_by(linked_account_id=acc_b.id).first()
    assert stg.proposed_category_id == transfer_cat.id  # zaufanie do istniejącej logiki importu
    assert stg.proposed_contractor_id == transfer_cont.id

    reanalyze_all_staging(user.token)
    db.session.refresh(stg)

    assert stg.proposed_category_id == transfer_cat.id, \
        "Odśwież mapowanie zgubiło kategorię 'Przelew wewnętrzny' — brak counterparty_account przy reanalizie."
    assert stg.proposed_contractor_id == transfer_cont.id, \
        "Odśwież mapowanie zgubiło kontrahenta 'Moje konto: X' — brak counterparty_account przy reanalizie."
