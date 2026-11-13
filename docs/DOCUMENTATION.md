# Dokumentacja projektu: Ile mam kasy

> Ostatnia aktualizacja: 2026-11-09
> Zakres: dokumentacja biznesowa (procesy, wymagania, przepływy)

---

## Spis treści

1. [Cel i zakres aplikacji](#1-cel-i-zakres-aplikacji)
2. [Słownik pojęć](#2-słownik-pojęć)
3. [Role i użytkownicy](#3-role-i-użytkownicy)
4. [Procesy biznesowe](#4-procesy-biznesowe)
   - 4.1 [Import wyciągu bankowego](#41-import-wyciągu-bankowego)
   - 4.2 [Zatwierdzanie transakcji ze stagingu](#42-zatwierdzanie-transakcji-ze-stagingu)
   - 4.3 [Ręczne dodawanie transakcji](#43-ręczne-dodawanie-transakcji)
   - 4.4 [Przelew wewnętrzny](#44-przelew-wewnętrzny)
   - 4.5 [Transakcje cykliczne](#45-transakcje-cykliczne)
   - 4.6 [Transakcje zaplanowane](#46-transakcje-zaplanowane)
   - 4.7 [Uzgadnianie salda konta](#47-uzgadnianie-salda-konta)
   - 4.8 [Zarządzanie kontrahentami i mapowanie](#48-zarządzanie-kontrahentami-i-mapowanie)
   - 4.9 [Usuwanie transakcji](#49-usuwanie-transakcji)
   - 4.10 [Planowanie budżetu miesięcznego](#410-planowanie-budżetu-miesięcznego)
5. [Reguły biznesowe](#5-reguły-biznesowe)
6. [Planowany rozwój](#6-planowany-rozwój)
7. [Znane ograniczenia](#7-znane-ograniczenia)

---

## 1. Cel i zakres aplikacji

**Ile mam kasy** to webowa aplikacja do osobistego zarządzania finansami, docelowo przeznaczona dla dowolnego użytkownika jako rozwiązanie self-hosted lub SaaS.

### Główne funkcje

- **Śledzenie kont bankowych i portfeli** — wiele kont na użytkownika (konto bankowe, portfel gotówkowy, konto oszczędnościowe), każde z osobnym saldem aktualizowanym automatycznie przy każdej transakcji
- **Import wyciągów bankowych** — ING Bank Śląski, mBank i Pekao SA, w formatach CSV, PDF i HTML, z automatycznym rozpoznaniem banku i formatu po zawartości pliku; dwuetapowy przepływ: parsowanie → staging → zatwierdzenie przez użytkownika
- **Automatyczne rozpoznawanie kontrahentów** — trójstopniowy algorytm dopasowania: numer rachunku kontrahenta → reguły mapowania → dopasowanie rozmyte (fuzzy match)
- **Kategoryzacja transakcji** — własne kategorie wydatków, przychodów i transferów; obsługa podziałów transakcji (split) na wiele kategorii
- **Transakcje cykliczne** — definicje automatycznie wykonywanych transakcji wg harmonogramu (dziennie, tygodniowo, miesięcznie, rocznie)
- **Transakcje zaplanowane** — jednorazowe transakcje z określoną datą wykonania w przyszłości
- **Przelewy wewnętrzne** — przelew między własnymi kontami to dwie powiązane operacje (nogi); druga strona pochodzi z wyciągu drugiego konta albo, gdy to konto nie dostaje wyciągów, jest dopisywana automatycznie jako lustro (patrz 4.4)
- **Dashboard** — Net Worth z porównaniem do poprzedniego miesiąca i roku, majątek w czasie (razem albo wg typu kont), przychody i wydatki wg wybranych kategorii, udział majątku wg typu kont; klik w miesiąc prowadzi do jego transakcji albo widoku we Wnioskach
- **Wnioski** — automatyczne wnioski z wybranego pełnego miesiąca (trendy kategorii, jednorazowe zdarzenia, stałe opłaty, bilans) liczone regułami w przeglądarce względem typowego miesiąca (mediana z 6 poprzednich), a pod nimi widoki: filtry okresu, kont, kategorii i kontrahentów z wykresem i tabelą, rozbijaniem elementów (menu, ścieżka, karta kategorii) i saldami kont na koniec miesiąca; do 7 własnych widoków zapisanych na koncie i do 10 ulubionych kont jako filtr. Kwoty w PLN po kursie NBP z końca miesiąca, przelewy wewnętrzne zawsze poza sumami (poza widokiem sald)
- **Raporty** — osobna zakładka z filtrowaniem po zakresie dat, kategoriach i kontach; wykresy słupkowe i liniowe, domyślnie z wyłączeniem przelewów wewnętrznych (inaczej podwajałyby obroty)
- **Budżet miesięczny** — plan kwoty na kategorię w danym miesiącu, zestawiony z wykonaniem i z rezerwacjami z harmonogramu; planowane są obie strony (przychody i wydatki), więc widać, czy plan wydatków mieści się w planie przychodów

---

## 2. Słownik pojęć

| Pojęcie | Definicja |
|---------|-----------|
| **Transakcja** | Operacja finansowa (wpływ lub wypływ) przypisana do konta, kategorii i kontrahenta |
| **Konto** | Rachunek bankowy, konto oszczędnościowe lub portfel gotówkowy użytkownika; posiada pola `owner` i `co_owner` (dane właścicieli) oraz flagę `is_default` (konto wybierane automatycznie w formularzach) |
| **Kategoria** | Klasyfikacja transakcji: `expense` (wydatek), `income` (przychód), `transfer` (przelew wewnętrzny) |
| **Kontrahent** | Słownikowy wpis reprezentujący sklep, osobę lub instytucję; zawiera reguły automatycznego mapowania |
| **Staging** | Strefa buforowa dla transakcji zaimportowanych z wyciągu, oczekujących na weryfikację użytkownika |
| **Split** | Podział jednej transakcji na kilka pozycji z różnymi kategoriami i kwotami |
| **Przelew wewnętrzny** | Transfer między własnymi kontami — dwie powiązane transakcje (nogi): wypływ na koncie źródłowym i wpływ na docelowym. Nie jest przychodem ani wydatkiem |
| **Noga przelewu** | Jedna z dwóch transakcji przelewu wewnętrznego; nogi wiąże `linked_transaction_id` |
| **Lustro** | Noga dopisana przez aplikację (`origin = 'mirror'`) na koncie, które nie dostaje własnych wyciągów; zastępowana prawdziwą nogą, gdy ta przyjdzie z wyciągu |
| **Do zmapowania** | Znacznik nogi przelewu bez pary — czeka na drugą stronę z wyciągu drugiego konta |
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
| **Użytkownik zarejestrowany** | Pełny dostęp do własnych danych: konta, transakcje, import wyciągów, kontrahenci, kategorie, budżety |
| **System** | Automatyczne wykonywanie transakcji cyklicznych i zaplanowanych przez `flask process-scheduled` |

Konto zakłada się samodzielnie — rejestracja jest publiczna i kończy się kreatorem pierwszego konta oraz zestawem kategorii startowych. Liczba prób logowania i rejestracji jest ograniczana per adres IP.

Architektura nie przewiduje ról administracyjnych w UI. Aplikacja nie wysyła e-maili, więc **jedyną drogą odzyskania zapomnianego hasła jest komenda `flask reset-password` uruchomiona przez administratora serwera.**

---

## 4. Procesy biznesowe

### 4.1 Import wyciągu bankowego

**Cel:** Zaimportowanie historii transakcji z pliku eksportu banku bez ręcznego przepisywania.

**Obsługiwane formaty:**

| Bank | CSV | PDF | HTML |
|------|-----|-----|------|
| **ING Bank Śląski** | ✅ | ✅ | — |
| **mBank** | ✅ | ✅ | ✅ |
| **Pekao SA** | ✅ | — | — |

Bank i format rozpoznawane są **po zawartości pliku, nie po rozszerzeniu** — użytkownik nie musi ich wskazywać. Pliki tekstowe (CSV, HTML) dekodowane są z UTF-8-sig lub windows-1250; oba warianty pojawiają się w eksportach z banków. CSV z ING ma separator `;`, a nagłówek tabeli zaczyna się od wiersza `Data transakcji`.

Konto docelowe rozpoznawane jest po numerze rachunku z nagłówka wyciągu — chroni przed zaimportowaniem transakcji na niewłaściwe konto. Gdy numeru nie da się dopasować, użytkownik wskazuje konto ręcznie.

Każdy import zapisuje ślad w historii importów (nazwa pliku, bank, format, liczba wierszy), dzięki czemu widać, co i kiedy zostało wciągnięte.

**Przepływ:**

```
Użytkownik wybiera plik wyciągu
         │
         ▼
  Rozpoznanie banku i formatu (detect_bank_and_format)
  - Analiza zawartości pliku, nie rozszerzenia
  - Wybór parsera z mapy STATEMENT_PARSERS
         │
         ▼
  Parsowanie pliku (parser właściwy dla banku i formatu)
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

Wgrywanie i zatwierdzanie są w jednej zakładce **Import** (na telefonie ukrytej). Kilka plików naraz: konto każdego rozpoznaje się po numerze rachunku z wyciągu; plik bez numeru (Revolut CSV, wyciąg ING z jednym kontem) dostaje na liście wyników wybór konta i „Wgraj ponownie”.

**Stany transakcji w stagingu:**

| Stan w UI | Warunek | Znaczenie |
|-----------|---------|-----------|
| sekcja „Przelewy między Twoimi kontami” | proposed_category.type = 'transfer' | Przelew wewnętrzny — auto-wykryty; para z tego samego importu to jeden wiersz |
| `Gotowe` | proposed_category + proposed_contractor_id (przelew: konto po drugiej stronie) | Można zatwierdzić |
| `Uzupełnij …` | brak kategorii lub kontrahenta | Wymaga ręcznego uzupełnienia; sugestia nowego kontrahenta jako „Nowy: … · Dodaj” |
| `Możliwy duplikat` | na tym koncie jest transakcja o tej samej kwocie w oknie ±4 dni | „Porównaj z historią” pokazuje ją obok; hurtowe zatwierdzenie pomija taki wiersz |

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
  - jeśli kategoria = 'transfer': szuka drugiej nogi przelewu — paruje ją albo dopisuje lustro (patrz 4.4)
         │
         ▼
  Usunięcie rekordu ze staging
```

**Zatwierdzanie zbiorcze** — „Zatwierdź gotowe" zatwierdza wszystkie wiersze w stanie `Gotowe`; możliwe duplikaty i wiersze do uzupełnienia zostają w poczekalni.

**Odrzucanie** — przycisk „Odrzuć wszystkie" usuwa cały staging użytkownika bez tworzenia transakcji.

**Akceptacja sugestii kontrahenta** — jeśli algorytm zasugerował znormalizowaną nazwę (`suggested_contractor_name`), użytkownik może ją edytować i zaakceptować jednym kliknięciem; system tworzy nowego kontrahenta z regułą mapowania = nazwa (małe litery), co przyspiesza przyszłe importy.

---

### 4.3 Ręczne dodawanie transakcji

**Cel:** Dodanie transakcji nieobecnej w wyciągu bankowym (np. gotówka, korekta).

**Formularz przyjmuje:**
- Konto (wymagane)
- Kwota — zawsze wpisywana jako liczba dodatnia; znak wyznaczany automatycznie z typu wybranej kategorii: `expense`/`transfer` → ujemna, `income` → dodatnia
- Tytuł
- Data
- Kategoria (wymagana) — lista expense, income, transfer; wybór kategorii określa kierunek przepływu środków
- Kontrahent (opcjonalny, wybierany z comboboxa ze słownika lub wpisany ręcznie); dla kategorii `transfer` pole kontrahenta jest ukryte — zamiast niego pojawia się selektor konta docelowego
- Podział (split) na wiele kategorii z opisami

Po zapisaniu saldo konta jest natychmiast aktualizowane.

---

### 4.4 Przelew wewnętrzny

**Cel:** Odwzorowanie przesunięcia środków między własnymi kontami bez sztucznego zawyżania wydatków i przychodów.

**Wizualizacja:** [przelewy-miedzy-kontami.html](przelewy-miedzy-kontami.html) pokazuje tę samą logikę na diagramach, z próbnikiem scenariuszy („co zrobi aplikacja w mojej sytuacji”). To samodzielny plik, który otwiera się w przeglądarce. Reguły z niego (R1–R13) są wypisane na końcu tego rozdziału.

**Model:** przelew to dwie transakcje, zwane nogami: wypływ na koncie źródłowym i wpływ na koncie docelowym. Wiąże je `Transaction.linked_transaction_id`. Przelew nie jest przychodem ani wydatkiem: Raporty (domyślnie), Podsumowanie, Wnioski (poza widokiem sald), wykres kategorii na Dashboardzie i Budżet go pomijają, a majątek netto w jednej walucie się nie zmienia, bo nogi sumują się do zera.

**Warunek wyzwolenia (backend):** kategoria transakcji ma typ `transfer` ORAZ kontrahent jest aktywny i ma nazwę w formacie `Moje konto: <nazwa konta>`. Kontrahent wskazuje konto docelowe przez twarde powiązanie z kontem (`Contractor.linked_account_id`); dopiero gdy powiązania brak, konto jest dopasowywane po nazwie. Dzięki temu zmiana nazwy konta nie psuje przelewów.

**Skąd bierze się przelew:**

| Droga | Jak działa |
|-------|------------|
| Wpis ręczny | Wybór kategorii typu `transfer` ukrywa pole kontrahenta i pokazuje wybór konta docelowego; kwota jest zawsze wypływem. Szybki wpis rozumie znacznik `>konto` |
| Import wyciągu | Wiersz jest przelewem, gdy numer rachunku kontrahenta jest numerem jednego z kont użytkownika; w Revolucie przelewem jest wymiana walut między subkontami. Wyciąg obejmujący oba konta dostarcza obie nogi w jednym pliku. Wiersze trafiają do sekcji „Przelewy między Twoimi kontami” w poczekalni |
| Harmonogram | Transakcje cykliczne i zaplanowane zapisują się tą samą funkcją co wpis ręczny (`create_transaction`) |

**Formularz ręczny — przepływ UI:**

```
Użytkownik wybiera kategorię typu "transfer"
         │
         ▼
  Pole kontrahenta jest ukrywane.
  Pojawia się selektor "Wybierz konto docelowe..."
  (lista kont użytkownika bez konta źródłowego)
         │
         ▼
  Użytkownik wybiera konto docelowe
         │
         ▼
  Przy zapisaniu formularz sprawdza czy kontrahent
  "Moje konto: <nazwa konta docelowego>" istnieje.
  Jeśli nie — tworzy go automatycznie (POST /api/contractors).
  Następnie wysyła transakcję z contractor_id.
```

**Skąd bierze się druga strona (`handle_internal_transfer`):** po zapisie nogi na koncie A (kontrahent „Moje konto: B”) aplikacja sprawdza zasady po kolei; pierwsza spełniona rozstrzyga i dalsze nie są sprawdzane. Zasady działają symetrycznie, także gdy jako pierwsza zapisywana jest noga wpływu.

```
Zapisano nogę na koncie A, kontrahent „Moje konto: B”
         │
  1. Konto B nieznane albo to samo konto co A?
     └─ TAK → zostaje jedna noga (bez pary, bez lustra)
         │ NIE
  2. Na koncie B czeka niepowiązana noga tego przelewu:
     przeciwna kwota, kontrahent „Moje konto: A”, data w oknie ±4 dni?
     └─ TAK → PARA: nogi wiążą się ze sobą, nic nie powstaje
         │ NIE
  3. Konta mają różne waluty?
     └─ TAK → noga czeka na drugą stronę (lustra między walutami nie ma)
         │ NIE
  4. Drugą nogę trzyma lustro na koncie A (origin = 'mirror')?
     └─ TAK → prawdziwa noga ZASTĘPUJE lustro, saldo bez zmian
         │ NIE
  5. Konto B dostaje własne wyciągi (ma wpis w historii importów)?
     └─ TAK → noga czeka na wyciąg konta B, znacznik „Do zmapowania”
         │ NIE
  6. LUSTRO: aplikacja dopisuje wpływ na koncie B (origin = 'mirror')
     i zmienia jego saldo
```

Dlaczego lustro tylko dla kont bez wyciągów: lustro na koncie, które importuje własne wyciągi, liczyłoby ten sam wpływ dwa razy, z lustra i z wyciągu. Konto „dostaje wyciągi”, gdy ma w historii importów choć jeden wpis. Gdy lustro powstaje, a w poczekalni czeka już wiersz tego samego wpływu (ta sama kwota i data, kontrahent „Moje konto: A”), aplikacja usuwa ten wiersz, żeby wpływ nie został zaksięgowany drugi raz.

Między różnymi walutami para łączy się tylko przy tym samym dniu, przeciwnym znaku i identycznym tytule (tak jest przy wymianie w Revolucie, gdzie tytuł niesie znacznik czasu). Kwot się nie porównuje, bo dzieli je kurs i spread. Parowanie jest zawsze jeden do jednego.

**Poczekalnia — stan drugiej strony** (kolumna „Druga strona”; stan liczy serwer tą samą regułą, według której przelew zostanie zaksięgowany):

| Stan | Komunikat w aplikacji | Co zrobi zatwierdzenie |
|------|----------------------|------------------------|
| `staging` | „Obie operacje są w tym imporcie” (para to jeden wiersz z przyciskiem „Zatwierdź obie”) | Zatwierdza po kolei wypływ i wpływ; druga noga paruje się z pierwszą |
| `booked` | „Druga strona jest już zaksięgowana” | Wiąże nogę z zaksięgowaną drugą stroną albo zastępuje lustro, które ją reprezentuje |
| `mirror` | „Dopisze ją aplikacja” | Dopisuje lustro na koncie bez wyciągów |
| `missing` | „Brak — zaimportuj wyciąg z konta B” | Księguje tylko tę nogę (to ostrzeżenie, nie blokada); saldo drugiego konta nie zmienia się, dopóki nie przyjdzie jego noga |

Akcje na wierszu: „Zatwierdź obie”, „Rozdziel” (pokazuje nogi osobno), „Zmień konto” (wskazanie konta po drugiej stronie), „To nie przelew” (czyści kategorię i kontrahenta „Moje konto: …”; zmiana tylko w przeglądarce, do zatwierdzenia). „Zatwierdź gotowe” pomija możliwe duplikaty, a lustro na koncie nogi przelewu nie jest duplikatem, bo zatwierdzenie je zastąpi.

**Co dzieje się później:**

- **Druga strona dochodzi później.** Noga „Do zmapowania” paruje się, gdy zostanie zatwierdzona druga noga z wyciągu: znacznik znika, a saldo drugiego konta zmienia się dopiero wtedy. Lustro zostaje zastąpione prawdziwą nogą, gdy konto zacznie dostawać wyciągi. Dotyczy to tylko wpisów o pochodzeniu `mirror`; wpis o pochodzeniu `unknown` (dane sprzed wprowadzenia tej kolumny) nie jest kasowany automatycznie, a taki duplikat poprawia się ręcznie.
- **Edycja.** Zmiana kwoty jednej nogi zmienia obie nogi i obie salda (tylko w tej samej walucie; kierunek znaków zostaje). Data idzie za drugą nogą tylko wtedy, gdy któraś z nich jest lustrem. Zmiana kategorii lub kontrahenta liczy drugą stronę od nowa: lustro znika, a noga z wyciągu zostaje odpięta.
- **Usuwanie.** Usunięcie jednej nogi usuwa obie i koryguje oba salda; jest trwałe (patrz 4.9). Usuwanie zbiorcze ostrzega o nogach spoza zaznaczenia, a zbiorcza zmiana kategorii pomija przelewy i nie pozwala nadać kategorii typu `transfer`.
- **Majątek netto.** Gdy jedna noga czeka na drugą, majątek jest chwilowo niższy albo wyższy o kwotę przelewu, aż druga noga się zaksięguje.
- **Zmiana nazwy konta.** Przelewy działają dalej, ale nazwa kontrahenta „Moje konto: …” nie zmienia się razem z kontem (patrz 7).

**Reguły szczegółowe** (stałe numery; ta sama lista jest na stronie wizualizacji):

| # | Reguła |
|---|--------|
| R1 | Przelew wewnętrzny to dwie powiązane transakcje (nogi): wypływ na koncie źródłowym i wpływ na docelowym, wiązane przez `linked_transaction_id`. Nie jest ani przychodem, ani wydatkiem |
| R2 | Wpis jest przelewem, gdy kategoria ma typ `transfer`, a kontrahent jest aktywny i nazywa się „Moje konto: …”. Potrzebne są oba warunki naraz |
| R3 | Konto docelowe wskazuje kontrahent przez powiązanie z kontem (`linked_account_id`); dopiero gdy powiązania brak, aplikacja dopasowuje konto po nazwie. Kontrahent przelewu powinien być jeden na konto |
| R4 | Noga dodana ręcznie albo z harmonogramu jest zawsze wypływem. W imporcie znak kwoty pochodzi z banku i się nie zmienia |
| R5 | Po zapisie nogi aplikacja sprawdza po kolei: konto po drugiej stronie, istniejącą nogę do sparowania, różne waluty, lustro do zastąpienia i własne wyciągi konta docelowego. Ostatnim krokiem jest lustro. Pierwsza spełniona zasada rozstrzyga |
| R6 | Para wymaga nogi na koncie docelowym, która jest jeszcze niepowiązana, ma kontrahenta wskazującego konto zapisywanej nogi, przeciwną kwotę i datę w oknie ±4 dni. Parowanie jest jeden do jednego |
| R7 | Lustro powstaje tylko na koncie, które nie dostaje własnych wyciągów, i tylko w tej samej walucie. Konto dostaje wyciągi, gdy ma w historii importów choć jeden wpis |
| R8 | Noga bez pary jest widoczna jako „Do zmapowania”. Saldo konta po drugiej stronie nie zmienia się, dopóki jego noga nie zostanie zatwierdzona z wyciągu |
| R9 | Prawdziwa noga z wyciągu zastępuje wcześniejsze lustro. Dotyczy to tylko wpisów o pochodzeniu `mirror`; wpis o nieznanym pochodzeniu nie jest kasowany automatycznie |
| R10 | Między różnymi walutami nie powstaje lustro. Para łączy się tylko przy tym samym dniu, przeciwnym znaku i identycznym tytule |
| R11 | Edycja kwoty zmienia obie nogi i obie salda, ale tylko w tej samej walucie. Data idzie za drugą nogą tylko przy lustrze. Zmiana kategorii lub kontrahenta liczy drugą stronę od nowa: lustro znika, noga z wyciągu zostaje odpięta |
| R12 | Usunięcie jednej nogi usuwa obie i koryguje oba salda; jest trwałe. Przy usuwaniu zbiorczym aplikacja ostrzega o nogach spoza zaznaczenia, a zbiorcza zmiana kategorii pomija przelewy |
| R13 | Raporty (domyślnie), Podsumowanie, Wnioski (poza widokiem sald), wykres kategorii na Dashboardzie i Budżet nie liczą przelewów jako przychodu ani wydatku |

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

**Obliczanie pierwszego terminu:** pierwszym terminem jest pierwszy wybrany dzień (tygodnia albo miesiąca) od daty początkowej — nie sama data początkowa. Harmonogram „10. dnia miesiąca” założony 25. wykona się pierwszy raz 10. następnego miesiąca. Jeśli ten dzień jest już w przeszłości, system wyznacza najbliższy przyszły termin zgodny z harmonogramem — nie wykonuje zaległych iteracji.

**Usunięta kategoria i zarchiwizowane konto.** Harmonogram księguje z kategorią, którą miał przy zakładaniu, także gdy później ją usunięto. Archiwizacja konta wyłącza jego transakcje cykliczne i usuwa oczekujące zaplanowane — na zamkniętym koncie nie mogłyby się wykonać, a nocne przetwarzanie stawałoby co noc z błędem widocznym tylko w logu.

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
- Użytkownik wpisuje rzeczywiste saldo konta oraz dzień, na który je uzgadnia (domyślnie dziś)
- System oblicza różnicę: `nowe_saldo - saldo_w_systemie_na_ten_dzień`
- Jeśli różnica ≠ 0: tworzy transakcję korygującą z kategorią systemową `Uzgadnianie salda`, datowaną na wskazany dzień
- Jeśli różnica = 0: żadna transakcja nie jest tworzona

**Uzgodnienie z datą wsteczną.** `Account.balance` jest sumą wszystkich transakcji konta bez względu na ich datę, więc saldem odniesienia nie może być saldo bieżące — jest nim `saldo_bieżące − suma operacji zaksięgowanych PO wskazanym dniu`. Data znaczy „tyle było na **koniec** tego dnia": operacje z samego dnia X wchodzą do odniesienia, odejmowane jest tylko to, co po nim. Dotyczy to także dzisiejszej daty — operacja wpisana z datą w przyszłości (np. czynsz za tydzień) nie wchodzi do salda odniesienia. Tak samo liczy okno uzgadniania (`saldoSystemuNaDzien` w `08_accounts.js`), więc kwota, którą użytkownik tam widzi i potwierdza, nie tworzy korekty. Daty z przyszłości są odrzucane (400).

**Uzgodnienie przed innym uzgodnieniem.** Dwa uzgodnienia nie są ze sobą sprzeczne — mierzą różne dni i oba mogą być prawdziwe. Sprzeczna bywa tylko kwota korekty: jeśli okazuje się, że brakującej kwoty zabrakło już przed lipcem, to korekta z sierpnia (która wtedy łatała tę samą dziurę) była o tyle samo za duża.

Dlatego aplikacja **nie kasuje** późniejszego uzgodnienia i nie wymaga, by użytkownik usunął je ręcznie. Zamiast tego zdejmuje z jego korekty tę samą różnicę:

- korygowane jest **wyłącznie pierwsze** uzgodnienie po wskazanym dniu — dalsze liczą swoją korektę względem niego, więc poprawka propaguje się sama,
- gdy skorygowana kwota wychodzi `0.00`, transakcja jest usuwana (twardo, bez archiwum — to domknięcie rachunku zrobione przez aplikację, nie decyzja użytkownika warta audytu),
- **saldo bieżące pozostaje bez zmian**, a obie daty nadal pokazują kwoty wpisane przez użytkownika.

Formularz opisuje ten skutek przed zapisem (o ile i na jaką kwotę zmieni się która transakcja), bo operacja rusza wiersz, którego użytkownik nie edytował.

Kategoria `Uzgadnianie salda` ma flagę `is_system_category = True` i typ `system_reconciliation` — jest wyróżniona jako systemowa, nie pojawia się w zwykłych listach kategorii. Transakcja wsteczna wpada w historyczny miesiąc, więc zmienia liczby w Raportach za tamten okres (zamierzone — poprawiamy historię); planu budżetu nie rusza, bo kategoria systemowa nie podlega planowaniu.

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

**Cel:** Usunięcie błędnej transakcji.

**Mechanizm (usunięcie trwałe, bez archiwum):**

```
Użytkownik usuwa transakcję
         │
         ▼
  Korekta salda konta:
  Account.balance -= Transaction.amount
         │
         ▼
  Usunięcie rekordu z tabeli transactions
```

Usuniętej transakcji nie da się przywrócić — pomyłkę poprawia się, wpisując operację ponownie. Przelew wewnętrzny znika w całości (obie nogi).

---

### 4.10 Planowanie budżetu miesięcznego

**Cel:** ustalić z wyprzedzeniem, ile ma pójść na każdą kategorię, i widzieć w trakcie miesiąca, jak plan ma się do rzeczywistości.

**Aktor:** użytkownik

**Przebieg:**

1. Użytkownik otwiera zakładkę **Budżet** i wybiera miesiąc (również przyszły).
2. Przy każdej kategorii przychodów i wydatków wpisuje kwotę planu. Puste pole = brak planu.
3. Pod polem aplikacja pokazuje, ile w tej kategorii wydawano dotychczas — **medianę** miesięcznych sum wraz z zakresem min–max. Kliknięcie podpowiedzi wstawia tę kwotę.
4. Aplikacja zestawia plan z trzema liczbami: **wykonane** (zaksięgowane transakcje), **zarezerwowane** (cykliczne i zaplanowane, które jeszcze się nie wykonały) oraz procent zajęcia planu.
5. Nagłówek podsumowuje plan przychodów, plan wydatków i ich różnicę. Ujemny bilans jest sygnalizowany banerem, ale **nie blokuje zapisu** — to decyzja użytkownika.

**Reguły szczegółowe:**

| Zagadnienie | Zachowanie |
|---|---|
| Podziały transakcji | Kwota liczy się do kategorii **podziałów**, nie rodzica. Reszta nieopisana podziałami zostaje na kategorii rodzica, więc suma po kategoriach zawsze równa się sumie transakcji. Raporty liczą to inaczej (po kategorii rodzica) — rozjazd jest świadomy |
| Rezerwacje | Liczone są wyłącznie wystąpienia **od dziś w przód**. Wystąpienie z przeszłości ma już swoją transakcję albo jest zaległością `flask process-scheduled` |
| Kategorie transferowe | Nie podlegają planowaniu — przelew między własnymi kontami nie jest ani przychodem, ani wydatkiem |
| Próg sugestii | Poniżej 3 miesięcy historii danej kategorii aplikacja nie proponuje kwoty, tylko mówi wprost, że danych jest za mało. Od 12 miesięcy dokłada osobno „rok temu w tym miesiącu" |
| Jeden plan na kategorię | Unikalny indeks `(user_token, year, month, category_id)` — ponowny zapis nadpisuje, nie dubluje |

**Czego budżet dziś nie robi:** nie przenosi niewykorzystanej kwoty na kolejny miesiąc (brak rolloveru), nie zna projektów wielomiesięcznych i nie kopiuje planu na kilka miesięcy naprzód.

---

## 5. Reguły biznesowe

| # | Reguła |
|---|--------|
| 1 | Saldo konta jest aktualizowane automatycznie przy każdej operacji (dodanie, usunięcie, zatwierdzenie stagingu) — nigdy ręcznie poza funkcją uzgadniania |
| 2 | Kwoty finansowe przechowywane jako `Decimal` (nigdy `float`) — precision 10, scale 2 |
| 3 | Transakcja wychodzącą (wydatek) ma kwotę ujemną; przychodząca — dodatnią |
| 4 | Przelew wewnętrzny wymaga koniecznie: kategorii `type=transfer` + kontrahenta w formacie `Moje konto: <nazwa>` |
| 5 | Lustro przelewu wewnętrznego powstaje tylko na koncie, które nie dostaje własnych wyciągów, i tylko w tej samej walucie; gdy druga noga już istnieje, nowa noga paruje się z nią zamiast tworzyć lustro (reguły przelewów R1–R13: 4.4) |
| 6 | Kategorie i kontrahenci są miękko usuwani (`is_active=False`) — nigdy hard-delete; filtry zawsze stosują `is_active=True` |
| 7 | Kontrahent może mieć tylko jedną domyślną kategorię; zmiana kategorii kontrahenta dotyczy tylko przyszłych importów |
| 8 | Staging transakcji należy do konkretnego użytkownika i konta; rekord bez `account_id` (starszy import) nie może być zatwierdzony — należy go odrzucić i reimportować |
| 9 | Zatwierdzenie transakcji ze stagingu wymaga jednocześnie kategorii i kontrahenta — nie można zatwierdzić bez obu |
| 10 | Transakcja zaplanowana po wykonaniu ma status `processed` i pozostaje w tabeli jako zapis historyczny |
| 11 | Plan budżetu zapisywany jest kwotą dodatnią niezależnie od typu kategorii; kierunek niesie typ kategorii (`income` / `expense`) |
| 12 | Plan wydatków wolno ustawić ponad plan przychodów — aplikacja informuje o ujemnym bilansie, ale nie blokuje zapisu |

---

## 6. Planowany rozwój

| Funkcja | Opis |
|---------|------|
| **Obsługa kolejnych banków** | Rozszerzenie o formaty PKO BP, Revolut i innych — obecnie obsługiwane są ING Bank Śląski, mBank i Pekao SA. Nowy format wymaga parsera i jednego wpisu w mapie `STATEMENT_PARSERS` |
| **Masowa zmiana kontrahenta** | Edycja zbiorcza obejmuje dziś kategorię i usuwanie; zmiana kontrahenta dla wielu transakcji naraz nie jest zrealizowana |
| **Rollover budżetu** | Niewykorzystana kwota planu nie przenosi się na kolejny miesiąc; nie ma też projektów wielomiesięcznych ani kopiowania planu na kilka miesięcy naprzód |

---

## 7. Znane ograniczenia

| Ograniczenie | Szczegóły |
|--------------|-----------|
| **Trzy banki** | Import obsługuje ING Bank Śląski, mBank i Pekao SA (tylko CSV); transakcje z innych banków należy wprowadzać ręcznie |
| **Brak wielodostępu współbieżnego** | Brak mechanizmu blokad optymistycznych — równoczesna edycja tej samej transakcji przez dwóch użytkowników może prowadzić do wyścigu |
| **Brak zarządzania rolami w UI** | Nie ma panelu administracyjnego; rejestracja jest samoobsługowa, ale każda inna operacja na kontach wymaga dostępu do serwera |
| **Brak resetu hasła przez e-mail** | Aplikacja nie wysyła wiadomości; zapomniane hasło ustawia administrator komendą `flask reset-password` |
| **Transakcje cykliczne bez obsługi zaległości** | Jeśli `flask process-scheduled` nie był uruchamiany przez dłuższy czas, zaległe iteracje nie są nadrabiane — wykonywana jest tylko bieżąca |
| **Waluta stała (PLN)** | Konta mogą mieć pole `currency`, ale logika sald i raportowania zakłada PLN; brak przeliczania kursów walut |
| **Brak eksportu danych** | Aplikacja nie oferuje eksportu transakcji do CSV/PDF/Excel |
| **Nazwy kontrahentów „Moje konto: …” po zmianie nazwy konta** | Zmiana nazwy konta nie zmienia nazwy jego kontrahenta. Przelewy działają dalej (kontrahent jest powiązany z kontem), ale w słowniku i na starych wpisach zostaje stara nazwa; poprawia się ją ręcznie |
