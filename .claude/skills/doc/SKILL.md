# Skill: Generowanie dokumentacji technicznej i biznesowej

## Opis
Generuje lub aktualizuje plik `docs/DOCUMENTATION.md` na podstawie analizy kodu projektu oraz odpowiedzi użytkownika na pytania uzupełniające dotyczące kontekstu biznesowego.

## Kiedy używać
Wywołaj przez `/doc`. Opcjonalnie podaj zakres: `/doc technical`, `/doc business`, `/doc all` (domyślnie: `all`).

---

## Instrukcja wykonania

### Krok 1 — Ustal zakres

Sprawdź argument podany przez użytkownika:
- `technical` → generuj tylko sekcje techniczne (architektura, API, modele)
- `business` → generuj tylko sekcje biznesowe (wymagania, procesy, user stories)
- `all` lub brak argumentu → generuj pełną dokumentację

### Krok 2 — Analiza kodu (zawsze wykonaj przed pytaniami)

Przeczytaj poniższe pliki **równolegle**, aby zebrać materiał do dokumentacji:

**Obowiązkowe:**
- `app/models.py` — wszystkie modele ORM (pola, relacje, enumy)
- `app/__init__.py` — rejestracja blueprintów i konfiguracja app factory
- `app/blueprints/*.py` — wszystkie routes (metody HTTP, ścieżki URL, parametry)
- `app/services/*.py` — logika biznesowa, kontrakty serwisów
- `config.py` — klasy konfiguracji
- `CLAUDE.md` — kontekst projektu już udokumentowany

**Jeśli istnieją:**
- `app/schemas.py` — schematy Marshmallow (walidacja, serializacja)
- `app/cli.py` — komendy CLI
- `migrations/versions/` — ostatnie 3 migracje (żeby wywnioskować zmiany schematu)

Podczas czytania zbieraj:
- Nazwy i pola każdego modelu (w tym nullable, default, typ)
- Wszystkie endpointy: metoda + ścieżka + co przyjmuje + co zwraca
- Zależności między serwisami
- Kluczowe przepływy (np. import CSV, przelewu wewnętrzne)

### Krok 3 — Pytania uzupełniające (tylko gdy brakuje kontekstu biznesowego)

**Zadaj pytania TYLKO o to, czego nie da się wywnioskować z kodu.** Nie pytaj o rzeczy widoczne w modelu lub serwisach.

Przykłady pytań, które warto zadać (wybierz odpowiednie dla zakresu):

**Biznesowe:**
- Kto jest docelowym użytkownikiem aplikacji? (np. jeden użytkownik domowy, rodzina, wiele osób)
- Czy są jakieś planowane funkcje lub znane ograniczenia, o których warto wspomnieć?
- Jakie banki/formaty CSV są obsługiwane poza ING Bank Śląski?
- Czy aplikacja ma być kiedyś publiczna / wieloużytkownikowa?

**Techniczne:**
- Czy są jakieś znane problemy z wydajnością lub techniczny dług, który warto udokumentować?
- Jaka jest strategia backupu bazy danych?
- Czy jest lub planowane jest CI/CD?

Pytaj zwięźle — maksymalnie 3–4 pytania, które realnie wzbogacą dokumentację.

### Krok 4 — Generowanie dokumentacji

Utwórz lub nadpisz plik `docs/DOCUMENTATION.md`.

Jeśli plik już istnieje — przeczytaj go najpierw, aby zachować sekcje, których nie aktualizujesz (zgodnie z wybranym zakresem).

Użyj poniższego szablonu jako szkieletu. Wypełnij go konkretną treścią z analizy kodu i odpowiedzi użytkownika — **nie zostawiaj placeholderów ani pustych sekcji**.

---

```markdown
# Dokumentacja projektu: [Nazwa aplikacji]

> Ostatnia aktualizacja: [data]  
> Wersja: [jeśli jest tag/wersja w repo, wstaw; inaczej pomiń]

## Spis treści
1. [Cel i zakres aplikacji](#1-cel-i-zakres-aplikacji)
2. [Architektura systemu](#2-architektura-systemu)
3. [Modele danych](#3-modele-danych)
4. [API — endpointy](#4-api--endpointy)
5. [Warstwa serwisów](#5-warstwa-serwisów)
6. [Procesy biznesowe](#6-procesy-biznesowe)
7. [Konfiguracja i uruchomienie](#7-konfiguracja-i-uruchomienie)
8. [Znane ograniczenia i dług techniczny](#8-znane-ograniczenia-i-dług-techniczny)

---

## 1. Cel i zakres aplikacji

[Opis celu: co robi aplikacja, dla kogo, jakie problemy rozwiązuje.
Wymień kluczowe funkcje w punktach.]

---

## 2. Architektura systemu

### Stos technologiczny
| Warstwa | Technologia |
|---------|-------------|
| Backend | ... |
| Baza danych | ... |
| Frontend | ... |
| Autentykacja | ... |
| Migracje | ... |

### Struktura warstw

[Opisz trójwarstwową architekturę: Models → Services → Blueprints.
Wyjaśnij kontrakt każdej warstwy.]

### Struktura katalogów (kluczowe pliki)

[Tabela lub lista — ścieżka | rola]

---

## 3. Modele danych

[Dla każdego modelu: nazwa, opis roli, lista pól z typami i ograniczeniami, relacje do innych modeli.
Format: nagłówek H3 per model, tabela pól.]

### Przykład formatu:

#### `Transaction`
Główna tabela transakcji finansowych.

| Pole | Typ | Ograniczenia | Opis |
|------|-----|--------------|------|
| `id` | Integer | PK | ... |
| `amount` | Numeric(10,2) | NOT NULL | Kwota (ujemna = wydatek) |
| ... | | | |

**Relacje:** należy do `Account`, `Category`, `Contractor`

---

## 4. API — endpointy

[Dla każdego blueprintu: nagłówek H3, tabela endpointów.]

### Blueprint: `[nazwa]`

| Metoda | Ścieżka | Opis | Parametry / Body | Odpowiedź |
|--------|---------|------|-----------------|-----------|
| GET | `/api/...` | ... | — | JSON: `{...}` |
| POST | `/api/...` | ... | JSON body: `{...}` | 200 / 4xx |

---

## 5. Warstwa serwisów

[Dla każdego serwisu: co robi, kluczowe funkcje publiczne z sygnaturą i opisem, jakie wyjątki rzuca.]

---

## 6. Procesy biznesowe

[Opisz kluczowe przepływy end-to-end jako numerowane kroki lub diagramy tekstowe.
Minimum: import CSV, zatwierdzanie stagingu, przelewu wewnętrzne, transakcje cykliczne.]

### Import CSV (2-etapowy)
1. ...
2. ...

### Przelew wewnętrzny
...

### Transakcje cykliczne / planowane
...

---

## 7. Konfiguracja i uruchomienie

### Wymagania
- Python 3.12+
- PostgreSQL

### Instalacja
```bash
# kroki z CLAUDE.md, skrócone i aktualne
```

### Zmienne środowiskowe
| Zmienna | Opis | Przykład |
|---------|------|---------|
| `DATABASE_URL` | Connection string PostgreSQL | `postgresql://...` |
| `SECRET_KEY` | Klucz sesji Flask | losowy string |

### Komendy deweloperskie
[Tabela: komenda | opis]

---

## 8. Znane ograniczenia i dług techniczny

[Lista konkretnych ograniczeń wyniesionych z analizy kodu i odpowiedzi użytkownika.
Jeśli nie ma żadnych — napisz "Brak zidentyfikowanych ograniczeń."]
```

---

### Krok 5 — Weryfikacja i raport

Po zapisaniu pliku:
1. Potwierdź ścieżkę zapisanego pliku.
2. Wypisz w 3–5 punktach co zostało uwzględnione, a czego ewentualnie brakuje (np. brak CI/CD — nie udokumentowano).
3. Zaproponuj kolejne kroki jeśli dokumentacja jest niekompletna.

---

## Zasady jakości

- **Konkret ponad ogólnik**: zamiast „aplikacja obsługuje transakcje" → „transakcje zapisywane są w tabeli `transactions` z automatyczną aktualizacją salda konta (`Account.balance`) w `create_transaction()`"
- **Nie kopiuj komentarzy z kodu** — parafrazuj i wyjaśniaj
- **Polska terminologia** — cały dokument po polsku, nazwy techniczne (klasy, pola, endpointy) bez tłumaczenia
- **Daty w formacie ISO**: `2026-06-12`
- Jeśli sekcja nie dotyczy projektu (np. brak CLI), **pomiń ją** zamiast pisać „N/A"
- Nie dodawaj sekcji, których nie potrafisz sensownie wypełnić na podstawie kodu
