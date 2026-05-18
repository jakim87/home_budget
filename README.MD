# Home Budget App

A web application for managing a home budget, analyzing expenses, importing bank transactions, and monitoring net worth.

In the future, the application will also be available on mobile platforms (iOS and Android) and will feature receipt scanning.

This project is built as an educational application, developed step-by-step using Python, Flask, and PostgreSQL.

## Architektura edycji danych (Audit Trail)

W przypadku edycji istniejących wpisów aplikacja celowo nie przechowuje pełnej historii zmian (tzw. Audit Trail) w osobnych tabelach historycznych. Dla aplikacji domowego budżetu byłoby to zjawiskiem overengineeringu. Zamiast tego modyfikacje po prostu nadpisują istniejące dane w bazie, a zaktualizowany zostaje jedynie znacznik czasu (`updated_at`). 
Wyjątkiem jest usuwanie transakcji – aby zabezpieczyć użytkownika przed utratą danych, usunięte wpisy trafiają wpierw do tabeli `TransactionArchive` (tzw. Shadow Table).

## Architektura importu danych

Import transakcji z plików bankowych odbywa się w bezpieczny, dwuetapowy sposób:

1.  **Staging (Poczekalnia):** Wgrane transakcje nie trafiają od razu do głównego rejestru. Zamiast tego są zapisywane w tabeli tymczasowej (`transaction_staging`).
2.  **Analiza i propozycja:** W tle uruchamiany jest algorytm, który analizuje każdą transakcję (na podstawie słów kluczowych i numerów kont) i próbuje automatycznie dopasować kontrahenta oraz kategorię.
3.  **Weryfikacja przez użytkownika:** Użytkownik widzi zaimportowane transakcje w specjalnej zakładce "Do weryfikacji", gdzie może zaakceptować propozycje systemu, wprowadzić własne poprawki lub odrzucić błędne wpisy.
4.  **Zatwierdzenie:** Dopiero po zatwierdzeniu przez użytkownika transakcja jest przenoszona z poczekalni do głównej tabeli `transactions`, a saldo powiązanego konta jest aktualizowane.

Taki proces zapewnia pełną kontrolę nad danymi i zapobiega zaśmiecaniu budżetu niepoprawnymi lub zduplikowanymi wpisami.

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

Currently supported:
- **ING Bank Śląski** (import z plików CSV)

Ultimately, the application aims to support:

- Millennium
- mBank
- Pekao
- Revolut
- Manual cash entries

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
│   │   ├── README.md             # Instrukcje dla modułu usług
│   │   └── budget_service.py     # Logika biznesowa i operacje na bazie
│   ├── blueprints/               # Podział endpointów (Routing)
│   │   └── README.md             # Instrukcje tworzenia nowych blueprintów
│   ├── templates/
│   │   └── base.html             # Główny szablon (Tailwind + JS)
│   ├── __init__.py               # Inicjalizacja Flask i SQLAlchemy (App Factory)
│   └── models.py                 # Modele tabel bazy danych
├── local_data/                   # Ignored by git (keep your bank CSVs here!)
├── migrations/                   # Flask-Migrate (Alembic) versions
│   └── README.md             # Instrukcje dla migracji
├── tests/
│   ├── README.md             # Dokumentacja i zasady testowania
│   └── ...                   # Pliki z testami
├── .env
├── .gitignore
├── config.py
├── requirements.txt
├── run.py
├── test_db.py                    # Skrypt weryfikujący połączenie z DB
└── README.md