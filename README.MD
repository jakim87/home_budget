# Aplikacja Budżetu Domowego

Aplikacja webowa do zarządzania budżetem domowym: śledzenie sald kont bankowych, import transakcji z wyciągów CSV, kategoryzacja wydatków, transakcje cykliczne i zaplanowane, transfery wewnętrzne, raporty z wykresami oraz monitorowanie wartości netto (Net Worth).

Projekt jest budowany jako aplikacja edukacyjna, rozwijana krok po kroku z wykorzystaniem Pythona, Flaska i PostgreSQL.

## Cele projektu

- Import transakcji z plików eksportowanych przez banki
- Analiza wydatków i przychodów
- Kategoryzacja transakcji z automatycznym dopasowywaniem kontrahentów
- Planowanie budżetu miesięcznego
- Monitorowanie sald kont
- Obsługa wielu banków i walut
- Śledzenie wartości netto (Net Worth)
- Obsługa kredytów (traktowanych jako zobowiązania / wartość ujemna)
- Ręczne wprowadzanie salda gotówkowego
- Uwierzytelnianie użytkownika (logowanie)
- W przyszłości: skanowanie paragonów, aplikacja mobilna (iOS i Android)

## Obsługiwane źródła danych

Aktualnie obsługiwane:
- **ING Bank Śląski** (import z plików CSV w formacie UTF-8-sig / Windows-1250)

Docelowo planowana obsługa:
- Millennium
- mBank
- Pekao
- Revolut
- Ręczne wpisy gotówkowe

## Stack technologiczny

- **Backend:** Python 3.12+, Flask 3.1, SQLAlchemy 2.0 (składnia `Mapped`), Flask-Migrate (Alembic)
- **Baza danych:** PostgreSQL (produkcja), SQLite in-memory (testy)
- **Uwierzytelnianie:** Flask-Login
- **Serializacja:** Marshmallow + flask-marshmallow
- **Frontend:** Jinja2, Tailwind CSS (CDN), HTMX, Chart.js (CDN)
- **Testy:** pytest

## Wymagane narzędzia

Do uruchomienia i pracy z projektem potrzebne są:

- Python 3.12+
- Git
- PostgreSQL
- pgAdmin 4 (opcjonalnie)
- Visual Studio Code lub inny edytor

## Uruchamianie projektu

```bash
# Utwórz i aktywuj środowisko wirtualne
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# Zainstaluj zależności
pip install -r requirements.txt

# Skonfiguruj zmienne środowiskowe (.env)
# DATABASE_URL=postgresql://postgres:HASLO@localhost:5432/budget_db
# SECRET_KEY=twoj-tajny-klucz

# Zastosuj migracje bazy danych
flask db upgrade

# Załaduj dane testowe (opcjonalnie)
flask seed

# Uruchom serwer deweloperski
python run.py
```

Aplikacja dostępna pod adresem: `http://localhost:5000`

Domyślne dane logowania po `flask seed`: **default_user / password**

## Komendy CLI

```bash
# Migracje bazy danych
flask db migrate -m "opis zmian"   # Wygeneruj nową migrację po zmianie modeli
flask db upgrade                    # Zastosuj oczekujące migracje
flask db downgrade                  # Cofnij ostatnią migrację (tylko development)

# Zadania cykliczne
flask process-scheduled             # Wykonaj zaplanowane i cykliczne transakcje
flask cleanup-archive               # Usuń zarchiwizowane transakcje starsze niż 60 dni

# Testy
pytest                              # Uruchom wszystkie testy
pytest tests/test_plik.py           # Pojedynczy plik
pytest tests/test_plik.py::test_nazwa -vv --tb=long   # Pojedynczy test, tryb szczegółowy

# Diagnostyka
python test_db.py                   # Sprawdź połączenie z bazą danych
```

## Architektura aplikacji

Trójwarstwowy projekt: **Modele → Serwisy → Blueprinty**

```
app/
├── models.py           # Modele ORM (SQLAlchemy): User, Account, Transaction,
│                       #   Category, Contractor, TransactionSplit,
│                       #   TransactionStaging, TransactionArchive,
│                       #   RecurringTransaction, PlannedTransaction, Budget
├── schemas.py          # Serializatory Marshmallow (walidacja żądań i odpowiedzi)
├── cli.py              # Komendy Flask CLI
├── services/           # Logika biznesowa — oddzielona od warstwy HTTP
│   ├── budget_service.py             # Główne CRUD, import CSV, uzgadnianie salda
│   ├── transaction_service.py        # Archiwizacja i czyszczenie transakcji
│   ├── recurring_service.py          # Wykonywanie transakcji cyklicznych
│   ├── planned_transaction_service.py
│   └── *.py                          # Serwisy kategorii, kontrahentów, kont, auth
├── blueprints/         # Warstwa HTTP — obsługuje żądania, wywołuje serwisy
│   ├── home_bp.py      # Strona główna + endpoint /api/init
│   ├── import_bp.py    # Import CSV → flow zatwierdzania ze stagingu
│   ├── transactions_bp.py
│   └── *.py            # auth, accounts, categories, contractors, recurring, planned
└── templates/
    └── base.html       # Główny szablon Jinja2 (SPA z zakładkami)
```

### Kontrakt warstwy serwisów

- Przyjmują proste typy danych (`int`, `dict`, `Decimal`); zwracają obiekty modeli lub rzucają `ValueError`
- Zarządzają własną transakcją bazodanową: `db.session.commit()` przy sukcesie, `db.session.rollback()` przy błędzie
- Blueprinty przechwytują `ValueError` i zwracają odpowiednie kody HTTP

## Architektura importu danych

Import transakcji z plików bankowych odbywa się w bezpieczny, dwuetapowy sposób:

1. **Staging (poczekalnia):** Zaimportowane transakcje trafiają najpierw do tabeli tymczasowej `transaction_staging`.
2. **Analiza i propozycja:** Algorytm dopasowuje kontrahenta i kategorię na podstawie słów kluczowych i numerów kont. Wykrywa również transfery wewnętrzne.
3. **Weryfikacja przez użytkownika:** Zakładka "Do weryfikacji" umożliwia akceptację propozycji systemu, ręczną korektę lub odrzucenie błędnych wpisów.
4. **Zatwierdzenie:** Po zatwierdzeniu transakcja trafia do głównej tabeli `transactions`, a saldo powiązanego konta jest aktualizowane.

## Architektura edycji danych (Audit Trail)

Aplikacja celowo nie przechowuje pełnej historii zmian (Audit Trail) w osobnych tabelach historycznych — dla budżetu domowego byłoby to nadmierną inżynierią. Modyfikacje nadpisują istniejące dane, aktualizując jedynie znacznik czasu (`updated_at`).

Wyjątkiem jest **usuwanie transakcji** — usunięte wpisy trafiają najpierw do tabeli `TransactionArchive` (Shadow Table), co zabezpiecza przed przypadkową utratą danych.

## Struktura projektu

```
budget/
├── app/
│   ├── blueprints/
│   │   └── README.md             # Instrukcje tworzenia nowych blueprintów
│   ├── services/
│   │   └── README.md             # Instrukcje warstwy serwisów
│   ├── static/
│   │   ├── main.js               # Cała logika frontend (SPA)
│   │   └── style.css             # Style uzupełniające Tailwind
│   ├── templates/
│   │   └── base.html             # Główny szablon HTML
│   ├── __init__.py               # Fabryka aplikacji Flask
│   ├── models.py                 # Modele tabel bazy danych
│   ├── schemas.py                # Schematy Marshmallow
│   └── cli.py                    # Komendy CLI
├── local_data/                   # Ignorowany przez git (pliki CSV z banku)
├── migrations/
│   ├── README.md                 # Instrukcje migracji
│   └── versions/                 # Skrypty migracyjne Alembic
├── tests/
│   ├── README.md                 # Dokumentacja i zasady testowania
│   ├── conftest.py               # Fixture pytest (SQLite in-memory)
│   └── test_*.py                 # Pliki z testami
├── docs/
│   └── DOCUMENTATION.md          # Dokumentacja biznesowa i procesowa aplikacji
├── .env                          # Zmienne środowiskowe (ignorowany przez git)
├── .flaskenv                     # Konfiguracja Flask (FLASK_DEBUG=1)
├── .gitignore
├── config.py                     # Klasy Config i TestConfig
├── requirements.txt
├── run.py                        # Punkt wejścia aplikacji
├── test_db.py                    # Skrypt weryfikujący połączenie z bazą
└── README.MD
```
