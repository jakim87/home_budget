# Dokumentacja projektu: Home Budget App

> Ostatnia aktualizacja: 2026-06-12
> Zakres: dokumentacja biznesowa (procesy, wymagania, przepływy)

---

## Spis treści

1. [Cel i zakres aplikacji](#1-cel-i-zakres-aplikacji)
2. [Słownik pojęć](#2-słownik-pojęć)
3. [Role i użytkownicy](#3-role-i-użytkownicy)
4. [Procesy biznesowe](#4-procesy-biznesowe)
   - 4.1 [Import wyciągu bankowego (CSV)](#41-import-wyciągu-bankowego-csv)
   - 4.2 [Zatwierdzanie transakcji ze stagingu](#42-zatwierdzanie-transakcji-ze-stagingu)
   - 4.3 [Ręczne dodawanie transakcji](#43-ręczne-dodawanie-transakcji)
   - 4.4 [Przelew wewnętrzny](#44-przelew-wewnętrzny)
   - 4.5 [Transakcje cykliczne](#45-transakcje-cykliczne)
   - 4.6 [Transakcje zaplanowane](#46-transakcje-zaplanowane)
   - 4.7 [Uzgadnianie salda konta](#47-uzgadnianie-salda-konta)
   - 4.8 [Zarządzanie kontrahentami i mapowanie](#48-zarządzanie-kontrahentami-i-mapowanie)
   - 4.9 [Usuwanie transakcji](#49-usuwanie-transakcji)
5. [Reguły biznesowe](#5-reguły-biznesowe)
6. [Planowany rozwój](#6-planowany-rozwój)
7. [Znane ograniczenia](#7-znane-ograniczenia)

---

## 1. Cel i zakres aplikacji

**Home Budget App** to webowa aplikacja do osobistego zarządzania finansami, docelowo przeznaczona dla dowolnego użytkownika jako rozwiązanie self-hosted lub SaaS.

### Główne funkcje

- **Śledzenie kont bankowych i portfeli** — wiele kont na użytkownika (konto bankowe, portfel gotówkowy, konto oszczędnościowe), każde z osobnym saldem aktualizowanym automatycznie przy każdej transakcji
- **Import wyciągów CSV z ING Bank Śląski** — dwuetapowy przepływ: parsowanie → staging → zatwierdzenie przez użytkownika
- **Automatyczne rozpoznawanie kontrahentów** — trójstopniowy algorytm dopasowania: numer rachunku kontrahenta → reguły mapowania → dopasowanie rozmyte (fuzzy match)
- **Kategoryzacja transakcji** — własne kategorie wydatków, przychodów i transferów; obsługa podziałów transakcji (split) na wiele kategorii
- **Transakcje cykliczne** — definicje automatycznie wykonywanych transakcji wg harmonogramu (dziennie, tygodniowo, miesięcznie, rocznie)
- **Transakcje zaplanowane** — jednorazowe transakcje z określoną datą wykonania w przyszłości
- **Przelewu wewnętrzne** — automatyczne tworzenie lustrzanej transakcji na koncie docelowym przy przelewie między własnymi kontami
- **Dashboard** — przegląd Net Worth, wykresy miesięczne i roczne wydatków/przychodów, bilans kont
- **Budżetowanie** — limity miesięczne per kategoria
- **Archiwum** — usuwane transakcje trafiają do archiwum (soft delete) z datą usunięcia

---

## 2. Słownik pojęć

| Pojęcie | Definicja |
|---------|-----------|
| **Transakcja** | Operacja finansowa (wpływ lub wypływ) przypisana do konta, kategorii i kontrahenta |
| **Konto** | Rachunek bankowy, konto oszczędnościowe lub portfel gotówkowy użytkownika |
| **Kategoria** | Klasyfikacja transakcji: `expense` (wydatek), `income` (przychód), `transfer` (przelew wewnętrzny) |
| **Kontrahent** | Słownikowy wpis reprezentujący sklep, osobę lub instytucję; zawiera reguły automatycznego mapowania |
| **Staging** | Strefa buforowa dla transakcji zaimportowanych z CSV, oczekujących na weryfikację użytkownika |
| **Split** | Podział jednej transakcji na kilka pozycji z różnymi kategoriami i kwotami |
| **Przelew wewnętrzny** | Transfer między własnymi kontami — generuje dwie sprzężone transakcje (rozchód + przychód) |
| **Transakcja cykliczna** | Definicja automatycznie powtarzającej się transakcji (np. czynsz co miesiąc) |
| **Transakcja zaplanowana** | Jednorazowa transakcja zaplanowana na konkretną datę w przyszłości |
| **Uzgadnianie salda** | Korekta salda konta przez transakcję systemową, gdy saldo w aplikacji rozmija się z rzeczywistym |
| **Reguły mapowania** | Lista słów kluczowych przypisanych do kontrahenta, używana przy auto-kategoryzacji importu |
| **Fuzzy match** | Dopasowanie rozmyte nazwy kontrahenta z banku do słownika z progiem podobieństwa 72% |

---

## 3. Role i użytkownicy

Aplikacja obsługuje wielu użytkowników w izolacji — każdy użytkownik widzi wyłącznie swoje konta, transakcje, kontrahentów i kategorie (za wyjątkiem kategorii systemowych, które są współdzielone).

| Rola | Opis |
|------|------|
| **Użytkownik zarejestrowany** | Pełny dostęp do własnych danych: konta, transakcje, import CSV, kontrahenci, kategorie, budżety |
| **System** | Automatyczne wykonywanie transakcji cyklicznych i zaplanowanych przez `flask process-scheduled` |

Architektura nie przewiduje ról administracyjnych w UI — zarządzanie użytkownikami odbywa się bezpośrednio w bazie danych.

---

## 4. Procesy biznesowe

### 4.1 Import wyciągu bankowego (CSV)

**Cel:** Zaimportowanie historii transakcji z pliku eksportu banku bez ręcznego przepisywania.

**Obsługiwany format:** ING Bank Śląski — CSV z separatorem `;`, kodowanie UTF-8-sig lub windows-1250. Nagłówek transakcji zaczyna się od wiersza `Data transakcji`.

**Przepływ:**

```
Użytkownik wybiera plik CSV + konto
         │
         ▼
  Parsowanie pliku (parse_ing_csv)
  - Wykrycie nagłówka tabeli transakcji
  - Mapowanie kolumn: data, kontrahent, tytuł, nr rachunku kontrahenta, kwota
  - Obsługa dwóch wariantów nazwy kolumny kwoty
         │
         ▼
  Analiza każdej transakcji (analyze_transaction_data)
  ┌─────────────────────────────────────────────────────┐
  │ 1. Czy nr rachunku kontrahenta pasuje do konta      │
  │    użytkownika?  →  TAK: kategoria "Przelew         │
  │    wewnętrzny" + kontrahent "Moje konto: <nazwa>"   │
  │                                                     │
  │ 2. Czy nazwa lub reguły mapowania kontrahenta       │
  │    zawierają się w tytule/kontrahencie z banku?     │
  │    → TAK: przypisz kontrahenta + jego domyślną kat. │
  │                                                     │
  │ 3. Fuzzy match znormalizowanej nazwy (próg 72%)     │
  │    → TAK: przypisz pasującego kontrahenta           │
  │                                                     │
  │ 4. Brak dopasowania → zasugeruj znormalizowaną      │
  │    nazwę do zatwierdzenia przez użytkownika          │
  └─────────────────────────────────────────────────────┘
         │
         ▼
  Zapis do tabeli staging (transaction_staging)
  Status: pending
  Pola: proposed_category_id, proposed_contractor_id,
        suggested_contractor_name
         │
         ▼
  Powiadomienie: "Zaimportowano N transakcji do weryfikacji"
```

**Stany transakcji w stagingu:**

| Stan w UI | Warunek | Znaczenie |
|-----------|---------|-----------|
| `Przelew` | proposed_category.type = 'transfer' | Przelew wewnętrzny — auto-wykryty |
| `Zmapowano` | proposed_category + proposed_contractor_id | Pełne dopasowanie do kontrahenta |
| `Auto-sugestia` | suggested_contractor_name bez proposed_contractor_id | Algorytm zasugerował nazwę, wymaga akceptacji |
| `Częściowo` | tylko jedna z: kategoria lub kontrahent | Dopasowanie niepełne |
| *(brak badge)* | brak proposed_category i proposed_contractor_id | Brak dopasowania — wymaga ręcznego uzupełnienia |

---

### 4.2 Zatwierdzanie transakcji ze stagingu

**Cel:** Weryfikacja i akceptacja zaimportowanych transakcji przed zapisaniem ich do głównej historii.

**Przepływ (pojedyncza transakcja):**

```
Użytkownik wybiera kategorię i kontrahenta w dropdownie
         │
         ▼
  Walidacja (StagingApproveSchema):
  - kategoria: wymagana, musi istnieć i być aktywna
  - kontrahent: wymagany, musi należeć do użytkownika i być aktywny
         │
         ▼
  create_transaction() — zapis do tabeli transactions
  - automatyczna aktualizacja Account.balance
  - jeśli kategoria = 'transfer': tworzy lustrzaną transakcję
         │
         ▼
  Usunięcie rekordu ze staging
```

**Zatwierdzanie zbiorcze** — wszystkie transakcje z kompletem `proposed_category` i `proposed_contractor_id` można zatwierdzić jednym kliknięciem „Zatwierdź zmapowane".

**Odrzucanie** — przycisk „Odrzuć wszystkie" usuwa cały staging użytkownika bez tworzenia transakcji.

**Akceptacja sugestii kontrahenta** — jeśli algorytm zasugerował znormalizowaną nazwę (`suggested_contractor_name`), użytkownik może ją edytować i zaakceptować jednym kliknięciem; system tworzy nowego kontrahenta z regułą mapowania = nazwa (małe litery), co przyspiesza przyszłe importy.

---

### 4.3 Ręczne dodawanie transakcji

**Cel:** Dodanie transakcji nieobecnej w wyciągu bankowym (np. gotówka, korekta).

**Formularz przyjmuje:**
- Konto (wymagane)
- Kwota — ujemna = wydatek, dodatnia = przychód
- Tytuł
- Data
- Kategoria (wymagana)
- Kontrahent (opcjonalny, wybierany z comboboxa ze słownika lub wpisany ręcznie)
- Podział (split) na wiele kategorii z opisami

Po zapisaniu saldo konta jest natychmiast aktualizowane.

---

### 4.4 Przelew wewnętrzny

**Cel:** Odwzorowanie przesunięcia środków między własnymi kontami bez sztucznego zawyżania wydatków/przychodów.

**Warunek wyzwolenia:** kategoria transakcji ma typ `transfer` ORAZ kontrahent ma nazwę w formacie `Moje konto: <nazwa konta>`.

**Mechanizm:**

```
Transakcja źródłowa (np. -1000 PLN na Koncie A)
         │
         ▼
  System szuka konta o nazwie = <część po "Moje konto: ">
         │
         ├── Konto docelowe NIE istnieje → zapis tylko transakcji źródłowej
         │
         └── Konto docelowe ISTNIEJE (i różne od źródłowego):
              │
              ├── Sprawdza czy lustrzana transakcja już istnieje
              │   (deduplikacja przy imporcie CSV obustronnego wyciągu)
              │
              └── Tworzy transakcję lustrzaną (+1000 PLN na Koncie B)
                  - kontrahent: "Moje konto: <nazwa Konta A>"
                  - auto-usunięcie pasującego rekordu ze stagingu
```

**Korekta znaku:** jeśli użytkownik poda dodatnią kwotę dla transakcji wychodzącejnia — system automatycznie koryguje ją na ujemną (i odwrotnie dla konta docelowego).

---

### 4.5 Transakcje cykliczne

**Cel:** Automatyczne generowanie regularnych transakcji (czynsz, abonament, pensja) bez ręcznej ingerencji.

**Konfiguracja:**

| Parametr | Wartości |
|----------|---------|
| Częstotliwość | `daily`, `weekly`, `monthly`, `yearly` |
| Interwał | dowolna liczba całkowita (np. co 2 tygodnie: weekly + interval=2) |
| Dzień tygodnia | 0=Poniedziałek … 6=Niedziela (dla weekly) |
| Dzień miesiąca | 1–31 (dla monthly/yearly; jeśli miesiąc krótszy — ostatni dzień miesiąca) |
| Data początkowa | data od której obowiązuje harmonogram |
| Data końcowa | opcjonalna; po jej przekroczeniu transakcja cykliczna jest dezaktywowana |

**Przepływ wykonania (`flask process-scheduled`):**

```
Pobranie wszystkich aktywnych transakcji cyklicznych
gdzie next_run_date <= dziś
         │
         ▼
  Dla każdej:
  1. Sprawdź czy nie przekroczono end_date → dezaktywuj jeśli tak
  2. Utwórz standardową transakcję (z aktualizacją salda)
  3. Przelicz next_run_date na kolejny termin
```

**Obliczanie pierwszego terminu:** jeśli data początkowa jest w przeszłości, system wyznacza najbliższy przyszły termin zgodny z harmonogramem — nie wykonuje zaległych iteracji.

---

### 4.6 Transakcje zaplanowane

**Cel:** Jednorazowe transakcje z z góry ustaloną datą wykonania (np. planowana rata, spodziewana faktura).

**Różnica względem cyklicznych:** brak harmonogramu — transakcja wykonuje się dokładnie raz w podanym `execution_date`.

**Przepływ wykonania (`flask process-scheduled`):**

```
Pobranie zaplanowanych transakcji gdzie:
  execution_date <= dziś AND status = 'pending'
         │
         ▼
  Dla każdej:
  1. Utwórz standardową transakcję
  2. Ustaw status = 'processed'
```

Przetworzone transakcje zaplanowane pozostają w tabeli `planned_transactions` ze statusem `processed` (nie są usuwane).

---

### 4.7 Uzgadnianie salda konta

**Cel:** Wyrównanie salda w aplikacji do rzeczywistego salda na rachunku bankowym, gdy pojawiła się rozbieżność (np. zaokrąglenia, opłaty pominięte przy imporcie).

**Mechanizm:**
- Użytkownik wpisuje rzeczywiste saldo konta
- System oblicza różnicę: `nowe_saldo - bieżące_saldo`
- Jeśli różnica ≠ 0: tworzy transakcję korygującą z kategorią systemową `Uzgadnianie salda`
- Jeśli różnica = 0: żadna transakcja nie jest tworzona

Kategoria `Uzgadnianie salda` ma flagę `is_system_category = True` i typ `system_reconciliation` — jest wyróżniona jako systemowa, nie pojawia się w zwykłych listach kategorii.

---

### 4.8 Zarządzanie kontrahentami i mapowanie

**Cel:** Budowanie słownika kontrahentów przyspieszającego kategoryzację przy kolejnych importach.

**Struktura kontrahenta:**

| Pole | Znaczenie |
|------|-----------|
| `name` | Znormalizowana, czytelna nazwa (np. „Biedronka") |
| `mapping_rules` | Lista słów kluczowych oddzielona przecinkami (np. „biedronka, jeronimo martins") |
| `default_category_id` | Kategoria przypisywana automatycznie przy dopasowaniu |

**Normalizacja nazwy kontrahenta z banku:**

Algorytm `normalize_contractor_name` przetwarza surowy tekst z banku (np. `BIEDRONKA SP Z OO WARSZAWA 3`) przez kolejne etapy:
1. Usunięcie artefaktów płatności kartą / przelewem bankowym
2. Usunięcie sufixów prawnych (SP. Z O.O., S.A., LTD itd.)
3. Usunięcie kodów i cyfr końcowych
4. Skrócenie do 2 pierwszych słów jeśli jest ich więcej
5. Zamiana na Title Case → `Biedronka`

**Trójstopniowy algorytm dopasowania (kolejność ma znaczenie):**

1. **Numer rachunku** — niezawodne dopasowanie wewnętrzne, nie wymaga słownika
2. **Dokładne dopasowanie nazwy/reguł** — iteracja po aktywnych kontrahentach użytkownika; sprawdza czy nazwa kontrahenta (≥3 znaki) lub któraś reguła mapowania zawiera się w tekście transakcji
3. **Fuzzy match** — `SequenceMatcher` z progiem 0.72; normalizowana nazwa z banku porównywana z nazwami kontrahentów i ich regułami

---

### 4.9 Usuwanie transakcji

**Cel:** Usunięcie błędnej transakcji przy zachowaniu śladu audytowego.

**Mechanizm (soft delete z archiwizacją):**

```
Użytkownik usuwa transakcję
         │
         ▼
  Korekta salda konta:
  Account.balance -= Transaction.amount
         │
         ▼
  Kopia do tabeli transaction_archive:
  - original_id, title, amount, date, account_id,
    category_id, contractor_id, user_id, deleted_at
         │
         ▼
  Usunięcie rekordu z tabeli transactions
```

Archiwum jest czyszczone automatycznie przez `flask cleanup-archive` — usuwa wpisy starsze niż 60 dni.

---

## 5. Reguły biznesowe

| # | Reguła |
|---|--------|
| 1 | Saldo konta jest aktualizowane automatycznie przy każdej operacji (dodanie, usunięcie, zatwierdzenie stagingu) — nigdy ręcznie poza funkcją uzgadniania |
| 2 | Kwoty finansowe przechowywane jako `Decimal` (nigdy `float`) — precision 10, scale 2 |
| 3 | Transakcja wychodzącą (wydatek) ma kwotę ujemną; przychodząca — dodatnią |
| 4 | Przelew wewnętrzny wymaga koniecznie: kategorii `type=transfer` + kontrahenta w formacie `Moje konto: <nazwa>` |
| 5 | Lustrzana transakcja przelewu wewnętrznego nie jest tworzona, jeśli już istnieje transakcja na koncie docelowym o tej samej kwocie i dacie (deduplikacja CSV) |
| 6 | Kategorie i kontrahenci są miękko usuwani (`is_active=False`) — nigdy hard-delete; filtry zawsze stosują `is_active=True` |
| 7 | Kontrahent może mieć tylko jedną domyślną kategorię; zmiana kategorii kontrahenta dotyczy tylko przyszłych importów |
| 8 | Staging transakcji należy do konkretnego użytkownika i konta; rekord bez `account_id` (starszy import) nie może być zatwierdzony — należy go odrzucić i reimportować |
| 9 | Zatwierdzenie transakcji ze stagingu wymaga jednocześnie kategorii i kontrahenta — nie można zatwierdzić bez obu |
| 10 | Transakcja zaplanowana po wykonaniu ma status `processed` i pozostaje w tabeli jako zapis historyczny |

---

## 6. Planowany rozwój

| Funkcja | Opis |
|---------|------|
| **Obsługa kolejnych banków** | Rozszerzenie parsera CSV o formaty PKO BP, mBank, Revolut i innych — aktualnie obsługiwany wyłącznie ING Bank Śląski |
| **Tryb edycji zbiorczej transakcji** | Masowa zmiana kategorii/kontrahenta dla wielu zaznaczonych transakcji jednocześnie — funkcja zaznaczona jako TODO w repozytorium |

---

## 7. Znane ograniczenia

| Ograniczenie | Szczegóły |
|--------------|-----------|
| **Jeden format banku** | Import CSV obsługuje wyłącznie ING Bank Śląski; transakcje z innych banków należy wprowadzać ręcznie |
| **Brak wielodostępu współbieżnego** | Brak mechanizmu blokad optymistycznych — równoczesna edycja tej samej transakcji przez dwóch użytkowników może prowadzić do wyścigu |
| **Brak zarządzania rolami w UI** | Nie ma panelu administracyjnego; zakładanie kont i zarządzanie użytkownikami wymaga bezpośredniego dostępu do bazy |
| **Transakcje cykliczne bez obsługi zaległości** | Jeśli `flask process-scheduled` nie był uruchamiany przez dłuższy czas, zaległe iteracje nie są nadrabiane — wykonywana jest tylko bieżąca |
| **Waluta stała (PLN)** | Konta mogą mieć pole `currency`, ale logika sald i raportowania zakłada PLN; brak przeliczania kursów walut |
| **Brak eksportu danych** | Aplikacja nie oferuje eksportu transakcji do CSV/PDF/Excel |
