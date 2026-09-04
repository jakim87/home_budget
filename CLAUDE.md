# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Home Budget App** — Flask + PostgreSQL web app for personal finance management. Features: bank account tracking, import wyciągów z ING i mBanku (CSV/PDF/HTML, z automatyczną detekcją banku i formatu), transaction categorization, recurring/planned transactions, internal transfers, dashboard z Net Worth i zakładka Raporty (oba na Chart.js), publiczna rejestracja użytkowników. Codebase and UI are in **Polish**.

## Zasady pracy nad tym repo

Wytyczne behawioralne ograniczające typowe błędy przy zmianach w kodzie. Nastawione na ostrożność kosztem szybkości — dla trywialnych zadań (literówka, jednolinijkowa zmiana) użyj zdrowego rozsądku, nie trzeba całej ceremonii.

### Myśl, zanim zaczniesz kodować

- Nazwij założenia wprost. Jeśli istnieje kilka interpretacji — przedstaw je, nie wybieraj po cichu.
- Jeśli istnieje prostsze rozwiązanie — powiedz to. Kontruj, gdy jest ku temu powód.
- Jeśli coś jest niejasne — zatrzymaj się i zapytaj, zamiast zgadywać. Dotyczy to zwłaszcza kwot, przypisania kont i przelewów wewnętrznych — złe założenie tutaj oznacza błędne dane finansowe, nie tylko brzydki kod.

### Zmiany chirurgiczne

- Dotykaj tylko tego, co konieczne. Każda zmieniona linia powinna wynikać wprost z zadania.
- Nie „poprawiaj” sąsiedniego kodu, komentarzy ani formatowania przy okazji. Trzymaj się istniejącego stylu i granic warstw (Models → Services → Blueprints, patrz Services Layer Contract).
- Zauważony niepowiązany martwy kod — zgłoś, nie usuwaj. Wyjątek: importy/zmienne/funkcje osierocone przez Twoje własne zmiany usuń.

### Cel z kryterium weryfikacji

Przed wieloetapowym zadaniem podaj krótki plan z jawnym sprawdzeniem każdego kroku:

```
1. [krok] → weryfikacja: [jak sprawdzę, że działa]
2. [krok] → weryfikacja: [jak sprawdzę, że działa]
```

Przekładaj polecenia na weryfikowalne cele: „napraw bug” → „napisz test odtwarzający błąd, potem spraw, by przechodził”. Jest to spójne z workflow TDD (RED → GREEN → REFACTOR) opisanym w sekcji Testing.

### Test prostoty

Zanim uznasz zmianę za gotową, zadaj sobie pytanie: „Czy senior powiedziałby, że to przekombinowane?”. Jeśli tak — uprość. Bez spekulacyjnych abstrakcji, konfigurowalności, której nikt nie zamawiał, ani obsługi scenariuszy, które nie mogą wystąpić.

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
flask reset-password             # Ustawia nowe hasło użytkownika (jedyna droga odzyskania
                                 #   konta — aplikacja nie wysyła maili)
flask import-excel-balance-history  # Jednorazowa migracja historii sald z XLSX (domyślnie dry-run)
flask seed-demo                  # Odtwarza konto demo od zera (idempotentne — pod nocny timer)
flask feedback-list              # Wypisuje uwagi użytkowników (jedyna droga odczytu)
flask feedback-delete --id N     # Kasuje zgłoszenie na stałe

# Tests
pytest                           # Run all tests (~250 testów w 28 plikach; kilkanaście minut — nie mylić z zawieszeniem)
npm test                         # Testy JS (vitest): liczenie na Dashboardzie i w Raportach
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
#            SECRET_KEY=...           (opcjonalny; fallback 'dev-key-123' w config.py)
#            LOG_LEVEL=DEBUG|INFO|... (opcjonalny; domyślnie INFO — patrz Logging & Diagnostyka)
#            ENABLE_DEV_RESET=1       (opcjonalny; włącza destrukcyjny endpoint /api/dev/reset poza debug/test)
#            TRUST_PROXY=1            (opcjonalny; TYLKO za reverse proxy — patrz niżej)
#            APP_ADMIN_NAME=...       (opcjonalny; administrator danych na stronach Regulamin/RODO)
#            APP_CONTACT_EMAIL=...    (opcjonalny; adres kontaktowy na tych stronach)
#            DEMO_ENABLED=1           (opcjonalny; pokazuje przycisk „Zobacz demo" — patrz Konto demo)
#            DEMO_USERNAME=/DEMO_PASSWORD=  (opcjonalne; domyślnie demo / demo-do-ogladania)
flask db upgrade
flask seed
```

Default dev credentials after `flask seed`: **default_user / password**. Hasło zapomniane → `flask reset-password`.

## Tech Stack

- **Backend**: Python 3.12+, Flask 3.1.3, SQLAlchemy 2.0 (`Mapped` type hints), Flask-Migrate
- **Database**: PostgreSQL (prod), in-memory SQLite (tests via `tests/conftest.py`)
- **Auth**: Flask-Login + Flask-Limiter (limity per-IP na `/api/login` i `/api/register`)
- **Serialization**: Marshmallow + flask-marshmallow
- **Parsowanie wyciągów**: PyMuPDF (PDF), BeautifulSoup4 (HTML mBanku), `csv` ze stdlib
- **Frontend**: Jinja2 (jeden szablon `base.html` = SPA z zakładkami) + Tailwind CSS + Chart.js (dashboard i Raporty) + driver.js (samouczek) — wszystko z CDN

## Architecture

Three-layer design: **Models → Services → Blueprints**

```
app/
├── models.py          # SQLAlchemy ORM: User, Account, Transaction, Category, Contractor,
│                      #   TransactionSplit, TransactionStaging, TransactionArchive,
│                      #   RecurringTransaction, PlannedTransaction, Budget, StatementImport
├── schemas.py         # Marshmallow serializers (request/response validation)
├── cli.py             # Flask CLI commands
├── services/          # Business logic — decoupled from HTTP/Flask
│   ├── budget_service.py           # Core CRUD, parsery CSV (ING/mBank), uzgadnianie salda
│   ├── budget_plan_service.py      # Plan miesieczny vs wykonanie (zakladka Budzet)
│   ├── statement_parsers.py        # detect_bank_and_format + parsery PDF/HTML
│   ├── import_history_service.py   # Historia importów (model StatementImport)
│   ├── excel_history_import_service.py  # Jednorazowa migracja historii sald z XLSX
│   ├── init_service.py             # Payload dla GET /api/init (cały stan frontu)
│   ├── transaction_service.py      # Transaction archive & cleanup
│   ├── recurring_service.py        # Recurring transaction execution
│   ├── planned_transaction_service.py
│   └── *.py                        # Category, Contractor, Account, Auth services
├── blueprints/        # HTTP layer — route handlers call services, translate exceptions to HTTP
│   ├── import_bp.py   # Upload wyciągu → staging approval flow; mapa STATEMENT_PARSERS
│   ├── transactions_bp.py
│   ├── budget_bp.py   # Plan budzetu: GET/PUT/DELETE /api/budgets/<rok>/<miesiac>
│   └── *.py           # auth, accounts, categories, contractors, recurring, planned, home
└── templates/         # base.html (cała aplikacja) + reconcile_modal.html
```

### Services Layer Contract

- Accept primitive types (int, dict, Decimal); return model objects or raise `ValueError`
- Właścicielem danych jest `user_token: str` (nie `user_id`) — bierz go pierwszym argumentem i filtruj nim **każde** zapytanie o cudzy obiekt po ID. To jedyna bariera przed IDOR; blueprint jej nie doda
- Own their DB transaction: `db.session.commit()` on success, `db.session.rollback()` in except
- Blueprints catch `ValueError` and return appropriate HTTP status codes

### Key Patterns

**Import wyciągów** (2-stage):

1. Parse → save to `TransactionStaging` with auto-categorization (contractor matching, internal transfer detection)
2. User reviews pending staging rows → approves → moves to `Transaction`, updates account balance

Bank i format rozpoznaje `detect_bank_and_format()` (`statement_parsers.py`) **po zawartości pliku, nie po rozszerzeniu**. Mapa `STATEMENT_PARSERS` w `import_bp.py:24` wiąże parę `(bank, format)` z parserem i trybem wejścia (`'text'` po zdekodowaniu / `'bytes'` surowo):

| Bank | CSV | PDF | HTML |
| ---- | --- | --- | ---- |
| ING Bank Śląski | ✅ | ✅ | — |
| mBank | ✅ | ✅ | ✅ |

Nowy format = parser w `statement_parsers.py` + jeden wpis w tej mapie. Każdy import zapisuje ślad w `StatementImport` (historia importów).

**Internal Transfers**: Category type `"transfer"` + contractor name matching `"Moje konto: {account_name}"` automatically creates a mirror transaction on the destination account.

**Soft Deletes**: Categories and contractors use `is_active=False`. Always filter `is_active=True` in queries.

**Kategorie per użytkownik**: `Category.user_token` wskazuje właściciela; `NULL` = kategoria globalna (systemowa, widoczna dla wszystkich, nieusuwalna przez użytkownika). Nie pisz własnych zapytań o kategorię po nazwie — użyj `category_service.find_by_name(user_token, name)` / `list_active(user_token)`, które definiują zakres widoczności (własne + globalne) w jednym miejscu.

**Deleted Transactions**: Moved to `TransactionArchive` (not hard-deleted) for audit trail.

**Financial Precision**: Always use `Decimal(str(value))` — never float — for monetary amounts.

**Recurring/Planned**: `RecurringTransaction` (schedule-based) and `PlannedTransaction` (one-off with `execution_date`) are processed by `flask process-scheduled`.

**Dashboard**: Zakładka otwierana domyślnie. Dane obliczane po stronie klienta z już załadowanego `transactions` + `accounts` (brak dodatkowego endpointa). Funkcje: `renderDashboard()`, `renderDashboardChart()`, `setDashboardView('monthly'|'yearly')` w `13_dashboard.js`. Wykresy Chart.js ładowane z CDN.

**Raporty**: osobna zakładka (`16_reports.js`, `renderReports()`), również licząca po stronie klienta z globalnego stanu. Ma własne wykresy Chart.js (`rptBarChart`, `rptLineChart`), presety zakresu dat, sortowanie tabeli i domyślnie **wyklucza przelewy wewnętrzne** (checkbox `#rpt-exclude-transfers`) — bez tego transfery podwajałyby obroty. Tabela ograniczona do `RPT_TABLE_MAX` wierszy.

**Budżet** (`20_budget.js`, `budget_plan_service.py`, `budget_bp.py`): plan kwoty per kategoria na miesiąc, zestawiony z wykonaniem. Jedyna zakładka, która **nie liczy niczego w przeglądarce** — front tylko renderuje to, co przyszło z `GET /api/budgets/<rok>/<miesiac>`. Powód: budżet jest świadomy podziałów transakcji i rezerwacji z harmonogramu, a globalny stan frontu nie zawiera ani jednego, ani drugiego.

Trzy rzeczy, które odróżniają go od Raportów i o które łatwo się potknąć:

1. **Podziały.** Raporty liczą po kategorii rodzica; Budżet po kategoriach podziałów. W bazie kwoty podziałów są **dodatnie**, a transakcja ma znak — podział dziedziczy znak rodzica, inaczej wydatek policzyłby się jako przychód. Reszta nieopisana podziałami (`abs(rodzic) − suma podziałów`) zostaje na kategorii rodzica; niezmiennik „suma po kategoriach == suma transakcji" ma własny test, bo bez niego kwoty giną po cichu przy podziale niepełnym. **Rozjazd z Raportami jest świadomy** — dla transakcji rozbitych oba widoki pokażą różne liczby per kategoria.
2. **Wykonane ≠ zarezerwowane.** Cykliczne i zaplanowane z datą w przyszłości zajmują budżet, zanim się wykonają. Liczymy **wyłącznie wystąpienia od dziś w przód**: wystąpienie z przeszłości albo ma już swoją transakcję (i policzyłoby się drugi raz), albo jest zaległością `flask process-scheduled`.
3. **Kategorie `transfer` nie podlegają planowaniu** — przelew między własnymi kontami nie jest ani przychodem, ani wydatkiem. `ustaw_plan` odrzuca je razem z kategoriami technicznymi.

Plan wydatków wolno ustawić ponad plan przychodów — aplikacja pokazuje ujemny bilans banerem, ale nie blokuje zapisu. Sugestia kwoty opiera się na **medianie** miesięcznych sum (wydatki domowe są skośne — jedna naprawa auta zawyża średnią do kwoty, której nikt nie ustawi) i **milczy poniżej 3 miesięcy historii danej kategorii**; od 12 miesięcy dokłada osobno „rok temu w tym miesiącu". Sugestie jadą w odpowiedzi `GET /api/budgets` — liczą się jednym przebiegiem po historii, więc osobna trasa nic by nie dała.

**Edycja zbiorcza** (`19_bulk_edit.js`, trasy `POST /api/transactions/bulk/category` i `/bulk/delete`): checkboxy w tabeli operacji + pasek akcji. Zaznaczenie żyje w `selectedTxIds` i jest **kasowane przy każdym `renderTransactions()`** — operacja ma dotyczyć tego, co widać, a nie wierszy z innego miesiąca. Obie trasy przyjmują listę ID (limit 500, `BulkTransactionSchema`) i domykają się jednym commitem: obcy albo nieistniejący ID unieważnia **całe** żądanie, nie tylko siebie (`_wlasne_transakcje()` w `transaction_service.py`) — inaczej liczba przetworzonych wierszy zdradzałaby, które ID istnieją u kogoś innego.

Dwie zasady wynikające z przelewów wewnętrznych: usunięcie zabiera **obie nogi** (jak przy usuwaniu pojedynczym — inaczej Net Worth się rozjeżdża; front ostrzega o nogach spoza zaznaczenia PRZED operacją), a masowa zmiana kategorii przelewy **pomija** i zgłasza ich liczbę — zmiana typu kategorii na inny niż `transfer` zostawiłaby parę powiązaną przez `linked_transaction_id`, która przelewem już nie jest. Pojedyncza edycja nadal na to pozwala; masowa nie, bo tam nikt nie patrzy na konkretny wiersz.

**Contractor Combobox**: Pole kontrahenta w formularzu transakcji to combobox (nie `<select>`): `#tx-contractor-input` (text, widoczny) + `#tx-contractor` (hidden, przechowuje ID). Inicjalizacja: `initContractorCombobox()`. Pozostałe miejsca (inline edit w tabeli, staging, formularze cykliczne) nadal używają `<select>`.

**Frontend = globalny stan z `/api/init`**: `home_bp.py` jednym zapytaniem ładuje `transactions`, `categories`, `contractors`, `accounts` do zmiennych globalnych zadeklarowanych w `01_state.js`; cały rendering i przeliczenia dzieją się po stronie klienta (brak osobnych endpointów read). Po mutacji (POST/PUT/DELETE) front woła `fetchInitialData()`, by odświeżyć globalny stan.

Logowanie i rejestracja to modal w `base.html` (`#login-modal`, widoki `#auth-view-login` / `#auth-view-register`) obsługiwany przez `15_init.js` — nie ma osobnych szablonów ani tras GET; cała aplikacja to jedno `base.html`.

Frontend to **21 modułów w `app/static/js/`**, ładowanych w kolejności prefiksów liczbowych (`01_state.js` … `20_budget.js`, `99_bootstrap.js`) — nie ma pliku `main.js`. Kolejność ma znaczenie: `01_state.js` deklaruje stan globalny, `99_bootstrap.js` startuje aplikację. Funkcje pomocnicze ogólnego przeznaczenia (np. `escapeHtml`) należą do `04_helpers.js`, żeby były dostępne dla modułów ładowanych później. Szukaj funkcji `render*()` / `update*()` w module odpowiadającym zakładce.

**Wygląd „Classical"**: `app/static/classical.css` to warstwa **nadpisująca**, ładowana w `base.html` po `style.css` — zmienia typografię, kolory i promienie we wszystkich zakładkach naraz. Nie edytuj jej razem ze `style.css`: przy zmianach wyglądu ustal najpierw, która warstwa wygrywa. Wycofanie = usunięcie dwóch `<link>` z `<head>`.

**XSS**: dane użytkownika wstawiane do `innerHTML` MUSZĄ przechodzić przez `escapeHtml()` — tytuł przelewu przychodzącego ustala nadawca, więc to nie jest tylko self-XSS.

**Samouczek** (`17_tour.js`, treść przez `/samouczek`): `TOURS` trzyma kroki pod kluczem zakładki; jedyny klucz bez zakładki to `import` — dotyczy okna importu, wybierany przez `TOUR_MODAL_KEYS`, gdy modal jest otwarty. `startTour()` **odsiewa kroki wskazujące na elementy niewidoczne w danym momencie** (`krokWidoczny`, po `getClientRects()` — nie `offsetParent`, bo ten jest `null` dla wszystkiego w modalach). Dzięki temu krok może bezpiecznie celować w element warunkowy: listę poczekalni przed pierwszym importem, zwinięty panel filtrów, kafelek widoczny tylko przy `DEMO_ENABLED`. Zero widocznych kroków = komunikat zamiast pustego samouczka. Instancja driver.js trzymana jest w `aktywnyDriver` i zamykana przed startem nowej — bez tego nieukończony samouczek zostawia własną nakładkę pod dymkiem następnego.

**Zgłoszenia użytkowników**: `feedback_bp.py` + `feedback_service.py` + model `Feedback`. Aplikacja webowa **wyłącznie zapisuje** — jedyna trasa to `POST /api/feedback` (każdy zalogowany, limit 10/godz., **konto demo dostaje 403**, bo demo jest publiczne i inaczej byłby to anonimowy endpoint zapisu). **Nie ma trasy czytającej zgłoszenia**, więc aplikacja nie potrzebuje pojęcia administratora ani ról — odczyt i kasowanie idą przez `flask feedback-list` / `flask feedback-delete`, czyli spod konta z dostępem do serwera. Nie dokładaj podglądu przez HTTP bez przemyślenia tego od nowa: lista pokazuje treści WSZYSTKICH użytkowników (pilnuje tego `test_aplikacja_nie_udostepnia_zgloszen_przez_http`).

Zgłoszenia **nie opuszczają serwera** i formularz **nie przyjmuje plików ani zrzutów** — świadomie, bo opis problemu z aplikacji budżetowej potrafi zawierać cudze dane finansowe, a zrzut ekranu zawiera je zawsze. Front dokleja automatycznie kontekst (otwarta zakładka + wersja aplikacji) i `User-Agent`; zgłoszenie jest powiązane z kontem autora. Zmiana zakresu zbieranych danych wymaga aktualizacji `polityka_prywatnosci.html` i `DOCS_LAST_UPDATED` w `legal_bp.py`.

Treść pisze obca osoba i trafia wprost na terminal, więc obie komendy przepuszczają ją przez `bezpieczny_tekst()` (`cli.py`): wycina znaki sterujące (sekwencje ANSI mogłyby ukryć fragment wyniku) i zastępuje znaki spoza strony kodowej konsoli — bez tego jedno emoji wywala całą komendę na Windowsie.

**Strony informacyjne**: `legal_bp.py` serwuje `/regulamin`, `/polityka-prywatnosci` i `/o-aplikacji` — statyczne szablony dziedziczące po `legal_base.html`, BEZ `@login_required` (linkujemy je z modalu rejestracji). Nazwa administratora i adres kontaktowy pochodzą z `config.APP_ADMIN_NAME` / `APP_CONTACT_EMAIL` (nadpisywalne z `.env`), autor z `APP_AUTHOR` — nie wpisuj tych danych na sztywno w szablonach. Linki żyją w dwóch partialach: `_footer.html` (stopka SPA i stron informacyjnych) oraz `_auth_legal_links.html` (modal logowania/rejestracji).

**Konto demo**: `app/services/demo_service.py` + `flask seed-demo`. Zwykłe konto użytkownika (`demo`) z wygenerowaną historią 6 miesięcy — cztery konta, przelewy wewnętrzne, harmonogram. Zwiedzający ma **pełne prawa zapisu**; porządek robi dopiero ponowne uruchomienie `seed-demo`, które kasuje stan i buduje go od nowa (idempotentne, pod nocny timer). Dane są deterministyczne (`SEED`), ruchome są tylko daty — liczone wstecz od dnia uruchomienia. Przycisk „Zobacz demo" na ekranie logowania pojawia się wyłącznie przy `DEMO_ENABLED=1`; hasło jest jawne z założenia (trafia do HTML). Do wypróbowania importu służy `GET /api/demo/przykladowy-wyciag.csv` (`import_bp`, też tylko przy `DEMO_ENABLED`) — wyciąg ING generowany w locie z datami względem dziś, żeby nie starzał się razem z resztą; część pozycji pasuje do reguł kontrahentów, DECATHLON celowo nie. `wipe_user_data()` z tego samego modułu obsługuje też `/api/dev/reset` — jedno miejsce kasowania danych użytkownika dla obu ścieżek.

**Dev Reset** (tylko dev/test): `app/blueprints/dev_bp.py` → `POST /api/dev/reset` (przycisk „Wyczyść wszystkie dane testowe") kasuje dane WYŁĄCZNIE bieżącego użytkownika i zeruje salda kont; kategorie są globalne, więc ich nie usuwa. Blueprint rejestrowany tylko gdy `app.debug`/`app.testing` lub `ENABLE_DEV_RESET=1`. Operacja destrukcyjna — nie wołać w trakcie zwykłej pracy.

### Testing

Tests use in-memory SQLite by default, defined in `tests/conftest.py` (fixtures: `app`, `client`, `test_user`, `test_user_id`, `test_user_token`, `other_user`, `logged_in_client`, helper `login_as`). Setting env var `TEST_DATABASE_URL` runs the **same suite on PostgreSQL** (CI does this via `.github/workflows/tests.yml` — jobs: SQLite + coverage, PostgreSQL). SQLite behavior differs from PostgreSQL — notably no JSON column support and relaxed constraints.

Drugi workflow, `.github/workflows/jakosc.yml`, dokłada dwie bramki: **ruff** (konfiguracja w `ruff.toml` — świadomie wąski zestaw `E9` + `F`, nie sprzątanie stylu) i **drift migracji** (`flask db check` na PostgreSQL — czerwony, gdy model zmieniono bez wygenerowania migracji). Narzędzia deweloperskie siedzą w `requirements-dev.txt`, nie w `requirements.txt`.

**Testy frontu** (`tests/js/`, vitest + jsdom, `npm test`): Dashboard i Raporty liczą sumy w przeglądarce z globalnego stanu, więc pytest nie dotyka tej ścieżki wcale — te liczby pokrywa wyłącznie vitest. Moduły z `app/static/js` nie są modułami ES (zwykłe skrypty, wspólny zasięg globalny), więc test ich nie importuje: `zaladujModuly()` z `tests/js/helpers.js` czyta plik i wykonuje go w zasięgu globalnym testu, zamieniając przy tym deklaracje z kolumny 0 na przypisania — bez tego `let transactions` z `01_state.js` byłoby niewidoczne dla kodu testu. Testy Raportów budują atrapę DOM; osobny test pilnuje, żeby użyte w niej `id` istniały w `base.html` (inaczej zmiana szablonu przechodziłaby przez zielone testy, psując aplikację).

Test conventions: amounts as `Decimal("...")` (never float; exception: assertions on JSON API responses), API-mutating tests assert both HTTP status **and** DB state, every endpoint with an ID gets an IDOR test in `tests/test_authorization.py`.

TDD workflow: RED (write failing test) → GREEN (minimal implementation) → REFACTOR.

### Adding New Features

1. **Model**: Define in `app/models.py` with SQLAlchemy 2.0 syntax → `flask db migrate` → `flask db upgrade`
2. **Service**: Add to `app/services/your_service.py` following the services contract above
3. **Blueprint**: Add route to existing or new `app/blueprints/` file → register in `app/__init__.py`
4. **Test**: Add `tests/test_feature.py` using conftest fixtures

## Za reverse proxy (produkcja)

`TRUST_PROXY=1` opakowuje aplikację w `ProxyFix` (`x_for=1`, `x_proto=1`). Bez tego za nginx-em `request.remote_addr` to zawsze `127.0.0.1`, więc logi logowań i każdy limit per-IP są bezwartościowe. **Nie włączać przy bezpośrednim wystawieniu na świat** — pozwoliłoby podszyć się pod dowolne IP nagłówkiem `X-Forwarded-For`.

Nadużycia logowania i rejestracji ogranicza **kod aplikacji ORAZ fail2ban** — dwie niezależne warstwy:

1. **Flask-Limiter** (`app/__init__.py:30`, dekoratory w `auth_bp.py`): `/api/login` — `10 per minute; 50 per hour`, `/api/register` — `5 per hour`, klucz = adres IP. Odpowiedź przy przekroczeniu: `429`. Limity są **punktowe**, `default_limits` jest puste. Licznik trzymany jest w pamięci procesu (`storage_uri="memory://"`), więc przy gunicornie z N workerami realny limit to N-krotność ustawionego; przy większym ruchu `storage_uri` na Redisa. Działa sensownie tylko przy `TRUST_PROXY=1` — bez tego wszyscy dzielą jeden licznik dla `127.0.0.1`.
2. **fail2ban** (serwer i tak go używa dla SSH): pliki w `deploy/fail2ban/`, filtr dopasowuje wpisy `Nieudana próba logowania` z `logs/app.log`. Zmiana formatu tego logu w `auth_bp.py` psuje filtr — trzeba wtedy zaktualizować `deploy/fail2ban/budget-auth.conf`.

Rejestracja pod `POST /api/register` jest **publiczna** — bez zaproszeń i bez CAPTCHY, limit per-IP to jedyna bariera. Testy: `tests/test_rate_limiting.py`, `tests/test_onboarding.py`.

**CSRF nie jest włączony** (brak `CSRFProtect`). Zapisano tu świadomie, żeby nie sprawdzać tego za każdym razem od nowa.

`MAX_CONTENT_LENGTH` = 10 MB (drugą warstwą jest `client_max_body_size` w nginx).

## Kopie zapasowe

`deploy/backup/` — skrypty i jednostki systemd. Kopia powstaje codziennie o 02:00 UTC
(`budget-backup.timer`), jest szyfrowana AES-256 i **weryfikowana zaraz po utworzeniu**
(`pg_restore --list` na odszyfrowanym pliku) — bez tego uszkodzona kopia wychodzi na jaw
dopiero przy awarii. Rotacja zostawia `BACKUP_KEEP` najnowszych plików.

Odtworzenie: `budget-restore.sh <plik> <nowa_baza>`. Skrypt **odmawia nadpisania
istniejącej bazy** — literówka w nazwie nie skasuje produkcji. Pełna instrukcja wraz
z kwartalnym ćwiczeniem odtworzenia: `deploy/backup/README.md`.

Hasło szyfrowania (`BACKUP_PASSPHRASE_FILE`) musi istnieć także poza serwerem — bez niego
żadnej kopii nie da się odczytać.

## Logging & Diagnostyka

Konfiguracja w `app/logging_config.py` (`configure_logging()`, wołane raz w `create_app()`). **Główny kanał diagnostyki — sprawdzaj go zamiast zgadywać.**

- **Plik**: `logs/app.log` (gitignored). `RotatingFileHandler`: rotacja przy 2 MB, 5 kopii (`app.log.1` … `app.log.5`). Plik bywa duży — czytaj przez `tail`/`offset`, nie w całości.
- **Format**: `%(asctime)s %(levelname)s [%(name)s] %(message)s`. Nazwa loggera = ścieżka modułu (np. `app.services.budget_service`).
- **Poziom**: sterowany `LOG_LEVEL` z `.env` (domyślnie `INFO`; `DEBUG` dla szczegółów). Root logger zostaje na `WARNING`, żeby biblioteki (SQLAlchemy itp.) nie zaśmiecały pliku.
- **Logi HTTP**: hooki `before_request`/`after_request` w `app/__init__.py` logują każde żądanie jako `METHOD path -> status (czas ms) user=...`. Globalny `@app.errorhandler(Exception)` zapisuje pełny traceback i zwraca 500. `werkzeug` wyciszony do `WARNING` (bez zdublowanych, kolorowanych ANSI wpisów).
- **Konwencja w kodzie**: każdy moduł ma `logger = logging.getLogger(__name__)`; serwisy logują `logger.info(...)` na sukces i `logger.error(...)`/`logger.exception(...)` w `except`.

## Important Files

| File                     | Purpose                                                           |
| ------------------------ | ----------------------------------------------------------------- |
| `app/__init__.py`      | App factory, blueprint + CLI registration                         |
| `config.py`            | `Config` (prod) and `TestConfig` classes                      |
| `run.py`               | Entry point                                                       |
| `.env`                 | Secrets — gitignored; contains `DATABASE_URL`, `SECRET_KEY`, `LOG_LEVEL` |
| `.flaskenv`            | Public Flask env (`FLASK_DEBUG=1`)                              |
| `migrations/versions/` | Alembic migration scripts — always review before committing      |
| `ruff.toml`            | Konfiguracja lintera — celowo wąska, patrz Testing                |
| `requirements-dev.txt` | Narzędzia CI (ruff); nie instalowane na produkcji                 |
| `README.md`            | Opis dla ludzi — trzymaj zgodny z tym plikiem                     |
| `docs/`                | `DOCUMENTATION.md` (procesy biznesowe), `PRZEWODNIK_UZYTKOWNIKA.md` |

**Uruchamianie produkcji**: gunicorn dostaje fabrykę wprost (`"app:create_app()"`). **Nigdy przez `run.py`** — ten plik ustawia `FLASK_DEBUG=1` przy imporcie, a przy `app.debug` rejestruje się `dev_bp` z destrukcyjnym `/api/dev/reset`.

## Kodowanie plików wejściowych

Eksporty z ING i mBanku (CSV, HTML) bywają w UTF-8-sig albo windows-1250 — oba warianty obsługuje `decode_statement_bytes()` (`statement_parsers.py`), wołane w `import_bp.py` dla parserów w trybie `'text'`. Parsery PDF dostają surowe bajty i dekodują je same przez PyMuPDF.
