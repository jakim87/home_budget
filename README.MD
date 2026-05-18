# Home Budget App

A web application for managing a home budget, analyzing expenses, importing bank transactions, and monitoring net worth.

In the future, the application will also be available on mobile platforms (iOS and Android) and will feature receipt scanning.

This project is built as an educational application, developed step-by-step using Python, Flask, and PostgreSQL.

## Architektura edycji danych (Audit Trail)

W przypadku edycji istniejących wpisów aplikacja celowo nie przechowuje pełnej historii zmian (tzw. Audit Trail) w osobnych tabelach historycznych. Dla aplikacji domowego budżetu byłoby to zjawiskiem overengineeringu. Zamiast tego modyfikacje po prostu nadpisują istniejące dane w bazie, a zaktualizowany zostaje jedynie znacznik czasu (`updated_at`). 
Wyjątkiem jest usuwanie transakcji – aby zabezpieczyć użytkownika przed utratą danych, usunięte wpisy trafiają wpierw do tabeli `TransactionArchive` (tzw. Shadow Table).

## Main Project Goals

- Import transactions from bank export files
- Expense analysis
- Transaction categorization
- Monthly budget planning
- Account balance monitoring
- Multi-bank and multi-currency support
- Net worth tracking
- Mortgage handling (treated as a negative value/liability)
- Manual cash balance entry
- User authentication (login)
- Receipt scanning
- Future availability on iOS and Android

## Supported Data Sources

Ultimately, the application aims to support:

- ING Bank Śląski
- Millennium
- mBank
- Pekao
- Revolut
- Manual cash entries

Initial development will focus on importing files from ING.

## Tech Stack

Planned technologies:

- Python
- Flask
- PostgreSQL
- SQLAlchemy
- Flask-Migrate
- HTML
- Bootstrap
- HTMX
- Chart.js
- pytest (for testing imports and logic)

## Required Tools

To run and work on this project, you will need:

- Python 3.12+
- Git
- PostgreSQL
- pgAdmin 4
- Visual Studio Code

## Current Project Structure

```text
home-budget-app/
├── app/
│   ├── services/
│   │   ├── __init__.py
│   │   └── budget_service.py     # Logika biznesowa i operacje na bazie
│   ├── blueprints/               # Podział endpointów (Routing)
│   ├── templates/
│   │   └── base.html             # Frontend (Tailwind + JS)
│   ├── __init__.py               # Inicjalizacja Flask i SQLAlchemy (App Factory)
│   └── models.py                 # Modele tabel bazy danych
├── local_data/                   # Ignored by git (keep your bank CSVs here!)
├── migrations/                   # Flask-Migrate (Alembic) versions
├── tests/
│   ├── conftest.py               # Konfiguracja Pytest (baza SQLite w RAM)
│   ├── test_accounts.py          
│   └── test_transactions.py      # TDD testy dla transakcji
├── .env
├── .gitignore
├── config.py
├── requirements.txt
├── run.py
├── test_db.py                    # Skrypt weryfikujący połączenie z DB
└── README.md