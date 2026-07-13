# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Home Budget App** — Flask + PostgreSQL web app for personal finance management. Features: bank account tracking, CSV import from ING Bank Śląski, transaction categorization, recurring/planned transactions, internal transfers, dashboard z Net Worth i wykresami Chart.js. Codebase and UI are in **Polish**.

## Commands

```bash
# Run
python run.py                    # Dev server on http://localhost:5000

# Database
flask db migrate -m "message"   # Generate migration after model changes
flask db upgrade                 # Apply pending migrations
flask db downgrade               # Rollback last migration (dev only)
flask seed                       # Populate DB with default_user + test data

# CLI tasks
flask process-scheduled          # Execute due recurring & planned transactions
flask cleanup-archive            # Remove archived transactions older than 60 days

# Tests
pytest                           # Run all tests
pytest tests/test_file.py        # Single file
pytest tests/test_file.py::test_name -vv --tb=long  # Single test, verbose

# DB connectivity check
python test_db.py
```

## Setup

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
# Edit .env: DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/budget_db
flask db upgrade
flask seed
```

Default dev credentials after `flask seed`: **default_user / password**

> **Uwaga**: Jeśli `flask seed` nie uruchomiono ponownie, hasło w bazie może być zapisane jako niezahaszowany plaintext `"secret"`. W takim przypadku należy zaktualizować hash ręcznie:
> ```bash
> python -c "from app import create_app, db; from app.models import User; from werkzeug.security import generate_password_hash; app = create_app(); ctx = app.app_context(); ctx.push(); u = db.session.query(User).filter_by(username='default_user').first(); u.password_hash = generate_password_hash('password'); db.session.commit()"
> ```

## Tech Stack

- **Backend**: Python 3.12+, Flask 3.1.3, SQLAlchemy 2.0 (`Mapped` type hints), Flask-Migrate
- **Database**: PostgreSQL (prod), in-memory SQLite (tests via `tests/conftest.py`)
- **Auth**: Flask-Login
- **Serialization**: Marshmallow + flask-marshmallow
- **Frontend**: Jinja2 + Tailwind CSS + HTMX + Chart.js (CDN, dashboard only)

## Architecture

Three-layer design: **Models → Services → Blueprints**

```
app/
├── models.py          # SQLAlchemy ORM: User, Account, Transaction, Category, Contractor,
│                      #   TransactionSplit, TransactionStaging, TransactionArchive,
│                      #   RecurringTransaction, PlannedTransaction
├── schemas.py         # Marshmallow serializers (request/response validation)
├── cli.py             # Flask CLI commands
├── services/          # Business logic — decoupled from HTTP/Flask
│   ├── budget_service.py           # Core CRUD, CSV import, balance reconciliation
│   ├── transaction_service.py      # Transaction archive & cleanup
│   ├── recurring_service.py        # Recurring transaction execution
│   ├── planned_transaction_service.py
│   └── *.py                        # Category, Contractor, Account, Auth services
├── blueprints/        # HTTP layer — route handlers call services, translate exceptions to HTTP
│   ├── import_bp.py   # CSV upload → staging approval flow
│   ├── transactions_bp.py
│   └── *.py           # auth, accounts, categories, contractors, recurring, planned, home
└── templates/         # Jinja2 HTML
```

### Services Layer Contract

- Accept primitive types (int, dict, Decimal); return model objects or raise `ValueError`
- Own their DB transaction: `db.session.commit()` on success, `db.session.rollback()` in except
- Blueprints catch `ValueError` and return appropriate HTTP status codes

### Key Patterns

**CSV Import Flow** (2-stage):

1. Parse → save to `TransactionStaging` with auto-categorization (contractor matching, internal transfer detection)
2. User reviews pending staging rows → approves → moves to `Transaction`, updates account balance

**Internal Transfers**: Category type `"transfer"` + contractor name matching `"Moje konto: {account_name}"` automatically creates a mirror transaction on the destination account.

**Soft Deletes**: Categories and contractors use `is_active=False`. Always filter `is_active=True` in queries.

**Deleted Transactions**: Moved to `TransactionArchive` (not hard-deleted) for audit trail.

**Financial Precision**: Always use `Decimal(str(value))` — never float — for monetary amounts.

**Recurring/Planned**: `RecurringTransaction` (schedule-based) and `PlannedTransaction` (one-off with `execution_date`) are processed by `flask process-scheduled`.

**Dashboard**: Zakładka otwierana domyślnie. Dane obliczane po stronie klienta z już załadowanego `transactions` + `accounts` (brak dodatkowego endpointa). Funkcje: `renderDashboard()`, `renderDashboardChart()`, `setDashboardView('monthly'|'yearly')` w `main.js`. Wykresy Chart.js ładowane z CDN.

**Contractor Combobox**: Pole kontrahenta w formularzu transakcji to combobox (nie `<select>`): `#tx-contractor-input` (text, widoczny) + `#tx-contractor` (hidden, przechowuje ID). Inicjalizacja: `initContractorCombobox()`. Pozostałe miejsca (inline edit w tabeli, staging, formularze cykliczne) nadal używają `<select>`.

### Testing

Tests use in-memory SQLite by default, defined in `tests/conftest.py` (fixtures: `app`, `client`, `test_user`, `test_user_id`, `test_user_token`, `other_user`, `logged_in_client`, helper `login_as`). Setting env var `TEST_DATABASE_URL` runs the **same suite on PostgreSQL** (CI does this via `.github/workflows/tests.yml` — jobs: SQLite + coverage, PostgreSQL). SQLite behavior differs from PostgreSQL — notably no JSON column support and relaxed constraints.

Test conventions: amounts as `Decimal("...")` (never float; exception: assertions on JSON API responses), API-mutating tests assert both HTTP status **and** DB state, every endpoint with an ID gets an IDOR test in `tests/test_authorization.py`.

TDD workflow: RED (write failing test) → GREEN (minimal implementation) → REFACTOR.

### Adding New Features

1. **Model**: Define in `app/models.py` with SQLAlchemy 2.0 syntax → `flask db migrate` → `flask db upgrade`
2. **Service**: Add to `app/services/your_service.py` following the services contract above
3. **Blueprint**: Add route to existing or new `app/blueprints/` file → register in `app/__init__.py`
4. **Test**: Add `tests/test_feature.py` using conftest fixtures

## Important Files

| File                     | Purpose                                                           |
| ------------------------ | ----------------------------------------------------------------- |
| `app/__init__.py`      | App factory, blueprint + CLI registration                         |
| `config.py`            | `Config` (prod) and `TestConfig` classes                      |
| `run.py`               | Entry point                                                       |
| `.env`                 | Secrets — gitignored; contains `DATABASE_URL`, `SECRET_KEY/` |
| `.flaskenv`            | Public Flask env (`FLASK_DEBUG=1`)                              |
| `migrations/versions/` | Alembic migration scripts — always review before committing      |

## CSV Encoding

ING Bank Śląski exports use UTF-8-sig or windows-1250 encoding — both handled in `parse_ing_csv()` in `budget_service.py`.
