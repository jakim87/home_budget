# Skill: Przegląd kodu i architektury

## Opis
Przeprowadza kompleksowy przegląd kodu i architektury projektu. Sprawdza zgodność z przyjętymi wzorcami, jakość kodu, bezpieczeństwo, testy i dług techniczny. Na końcu generuje raport z konkretnymi rekomendacjami.

## Kiedy używać
Wywołaj przez `/review`. Opcjonalnie ogranicz zakres: `/review arch`, `/review security`, `/review tests`, `/review frontend`, `/review all` (domyślnie: `all`).

---

## Instrukcja wykonania

### Krok 1 — Ustal zakres

Sprawdź argument podany przez użytkownika:
- `arch` → tylko przegląd architektury (warstwy, modele, serwisy, blueprinty)
- `security` → tylko bezpieczeństwo (auth, walidacja, SQL injection, XSS)
- `tests` → tylko pokrycie testami i jakość testów
- `frontend` → tylko warstwa JS/HTML (moduły `app/static/js/`, base.html, wzorce HTMX)
- `all` lub brak argumentu → pełny przegląd (wszystkie obszary)

---

### Krok 2 — Odczyt plików (równolegle)

Przed każdą analizą przeczytaj poniższe pliki **równolegle**:

**Zawsze:**
- `app/models.py`
- `app/__init__.py`
- `app/services/*.py` — wszystkie pliki serwisów
- `app/blueprints/*.py` — wszystkie blueprinty
- `CLAUDE.md`

**Dla zakresu `frontend` lub `all`:**
- `app/templates/base.html`
- `app/static/js/*.js` — wszystkie moduły (`01_state.js` … `99_bootstrap.js`), ładowane
  w kolejności prefiksów liczbowych; nie ma pliku `main.js`
- `app/static/style.css`

**Dla zakresu `tests` lub `all`:**
- `tests/conftest.py`
- `tests/test_*.py` — lista plików (Glob), a następnie odczytaj każdy

**Dla zakresu `arch` lub `all`:**
- `config.py`
- `app/schemas.py`
- `app/cli.py`
- Ostatnie 3 pliki migracji z `migrations/versions/` (wg daty modyfikacji)

---

### Krok 3 — Analiza (wykonaj dla każdego aktywnego zakresu)

Dla każdego obszaru wypełnij sekcję w raporcie. Każde znalezisko musi zawierać:
- **Plik i numer linii** (`app/services/budget_service.py:142`)
- **Opis problemu** — co jest nie tak i dlaczego
- **Rekomendacja** — konkretna zmiana (nie "rozważ poprawę")
- **Priorytet**: 🔴 Krytyczny / 🟡 Ważny / 🟢 Drobny

---

#### Obszar A: Architektura (3-warstwowa)

Sprawdź naruszenia kontraktu **Models → Services → Blueprints**:

1. **Logika w blueprintach** — czy blueprint wykonuje operacje bazodanowe bezpośrednio (`db.session.query`, `db.session.commit`)? Logika powinna być w serwisach.
2. **Flask w serwisach** — czy serwis importuje `request`, `session`, `current_user` lub `jsonify`? Serwisy nie powinny znać warstwy HTTP.
3. **Brak rollback** — czy każda funkcja serwisowa, która modyfikuje DB, ma `db.session.rollback()` w bloku `except`?
4. **Prymitywy vs obiekty** — czy serwisy przyjmują prymitywne typy (`int`, `dict`, `Decimal`) zamiast obiektów ORM lub `request`?
5. **Modele** — czy wszystkie nowe pola używają składni SQLAlchemy 2.0 (`Mapped`, `mapped_column`)? Czy brakuje `nullable=False` gdzie powinno być?
6. **Miękkie usuwanie** — czy wszystkie zapytania do `Category` i `Contractor` filtrują `is_active=True`?
7. **Precyzja finansowa** — czy wszędzie używany jest `Decimal(str(value))` zamiast `float`?

#### Obszar B: Bezpieczeństwo

1. **Autoryzacja** — czy każdy endpoint zwracający dane użytkownika ma `@login_required`? Czy dane są filtrowane po `user_token = current_user.token`?
2. **Walidacja wejścia** — czy dane z `request.json` / `request.form` są walidowane przed użyciem? Szczególnie: kwoty, daty, ID.
3. **SQL Injection** — czy używane są parametryzowane zapytania (`db.session.get()`, `.filter_by()`, `.filter()`)? Czy nie ma surowych `text()` z interpolacją zmiennych?
4. **XSS** — czy wartości użytkownika wyświetlane w JS (np. w `innerHTML`) są bezpiecznie obsługiwane (`textContent` zamiast `innerHTML`, lub escaping)?
5. **CSRF** — czy formularze POST używają ochrony CSRF (Flask-WTF lub ręczny token)?
6. **Hasła** — czy `generate_password_hash` / `check_password_hash` są poprawnie używane w `auth_service.py`?

#### Obszar C: Frontend (moduły `app/static/js/` + base.html)

1. **Globalne zmienne** — wylistuj wszystkie zmienne globalne (deklarowane w `01_state.js`). Czy nie ma nadmiarowych lub nieużywanych? Czy któryś moduł nie używa funkcji zdefiniowanej w module ładowanym PÓŹNIEJ (kolejność wynika z prefiksów liczbowych)?
2. **Źródło prawdy** — czy operacje na danych modyfikują globalne tablice (`transactions`, `categories`, itp.) spójnie, czy są niespójności (np. lokalna kopia vs. globalna)?
3. **Wycieki pamięci** — czy instancje Chart.js są niszczone przed ponownym renderowaniem (`chart.destroy()`)?
4. **Obsługa błędów fetch** — czy wywołania `fetch()` mają obsługę błędów HTTP (sprawdzenie `response.ok`) i sieci (`catch`)?
5. **Dostępność** — czy elementy interaktywne bez `href` (np. `<div onclick>`) mają `role` i `tabindex`?
6. **Redundancja** — czy są zduplikowane fragmenty kodu, które można by zamknąć w funkcji pomocniczej?

#### Obszar D: Testy

1. **Pokrycie serwisów** — czy każdy plik w `app/services/` ma odpowiadający plik `tests/test_*`? Wylistuj braki.
2. **Pokrycie ścieżek błędów** — czy testy sprawdzają nie tylko "happy path", ale też przypadki brzegowe (brak danych, nieprawidłowe ID, kwoty ujemne)?
3. **Izolacja** — czy testy nie zależą od kolejności wykonania (brak globalnego stanu między testami)?
4. **SQLite vs PostgreSQL** — czy są testy, które mogą przejść na SQLite ale nie na PostgreSQL (np. JSON, `ILIKE`, `RETURNING`)?
5. **Brakujące testy** — wskaż konkretne funkcje serwisowe nieprzetestowane lub słabo przetestowane.

#### Obszar E: Dług techniczny

1. **TODO / FIXME / HACK** — wyszukaj i wylistuj wszystkie takie komentarze z plikiem i linią.
2. **Nieużywany kod** — zaimportowane moduły lub funkcje nieużywane w plikach (`import X` bez użycia `X`).
3. **N+1 queries** — czy w pętlach wykonywane są zapytania do bazy? Sprawdź czy `joinedload` / `selectinload` jest używane tam, gdzie potrzeba.
4. **Przestarzałe wzorce** — czy są fragmenty kodu niezgodne z CLAUDE.md (np. stara składnia SQLAlchemy bez `Mapped`)?
5. **README vs. rzeczywistość** — czy `README.MD` opisuje aktualny stan projektu (stack, komendy, struktura)?

---

### Krok 4 — Wygeneruj raport

Raport po polsku, nagłówek: data, zakres, liczba przejrzanych plików. Potem
2-4 zdania podsumowania i sekcja na każdy aktywny obszar (A-E) — jeśli nic nie
znalazłeś, napisz "✅ Brak uwag". Na końcu lista rekomendowanych działań
posortowana po priorytecie. Format znaleziska jak w Kroku 3: `plik:linia`,
opis problemu, konkretna rekomendacja, priorytet.

---

### Krok 5 — Pytanie końcowe

Po wyświetleniu raportu zapytaj użytkownika:

> "Czy chcesz, żebym od razu naprawił któreś ze znalezisk? Jeśli tak, podaj numer z listy rekomendacji."

Jeśli użytkownik wskaże konkretne punkty — przystąp do ich implementacji w tej samej sesji.

---

## Zasady jakości raportu

- **Konkrety ponad ogólniki**: zamiast "brak obsługi błędów" → "`budget_service.py:87`: brak `rollback` w bloku `except`, zapis może pozostać w niespójnym stanie po błędzie walidacji"
- **Nie zgłaszaj fałszywych alarmów**: jeśli coś wygląda podejrzanie, ale jest celowe (widoczne z kodu lub CLAUDE.md) — pomiń lub oznacz jako "świadoma decyzja projektowa"
- **Jeden problem = jedno znalezisko**: nie łącz kilku problemów w jedno
- **Polska terminologia** — cały raport po polsku, identyfikatory kodu bez tłumaczenia
- Jeśli plik jest za długi do pełnej analizy — przeczytaj w częściach; nie pisz "nie mogłem przeanalizować"
