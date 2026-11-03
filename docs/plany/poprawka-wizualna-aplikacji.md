# Poprawka wizualna aplikacji — plan wdrożenia

Stan: **sekcje 1 i 2 wdrożone na produkcję 2026-10-18** (PR #234, v1.2.0). Sekcja 3 — propozycja z 2026-10-24. Sekcja 4 (Wnioski) — propozycja z 2026-11-01. Spisany 2026-10-11. Kolejne zakładki dopisujemy jako następne sekcje.

Makieta (dane przykładowe, zatwierdzona 2026-10-11): https://claude.ai/artifact/JPdP9HGg3HYdpXxmHA2fnH

## 1. Dashboard

Zmiana wyłącznie frontowa: bez modeli, migracji i nowych tras — `/api/init` już wysyła `account_type` kont (także nieaktywnych).

### Co pokazuje makieta

- **Majątek netto**: wartość po lewej, po prawej „Miesiąc temu" i „Rok temu" (wartość z tamtego okresu + zmiana do dziś). Procent tylko przy dodatniej bazie.
- **Majątek w czasie**: przełączniki `Razem / Wg typu kont` i `6 / 12 / Wszystko` zamiast pól od–do, wygładzone linie, opis pod ikoną „i", dymek bez typów kont, które jeszcze nie istniały, klik wybiera miesiąc.
- **Przychody i wydatki wg kategorii**: słupki miesięczne z listą wielokrotnego wyboru kategorii transakcji, bez przelewów wewnętrznych.
- **Pasek wybranego miesiąca**: „Pokaż transakcje" i „Szczegółowy raport" (drill-through).
- **Udział majątku wg typu kont**: pasek i tabela; udział liczony w aktywach (suma sald dodatnich), zobowiązania mają udział ujemny. Reaguje na wybrany miesiąc.
- **Paleta** pod warstwę „Classical": ochra `#b68235` (akcent, majątek netto, przychody), stalowy błękit `#5f6f8c` (wydatki), łupkowy `#4a6fa5` (ROR), szałwia `#5e8f7b` (KO), miodowy `#d0a45a` (rach. maklerski), śliwka `#8b6a8f` (IKZE), popiel `#9b9797` (bez typu), umbra `#8a6b55` (kredyty i karty).
- Znikają kafelki kont (i filtr po nich). Przełącznik „Podgląd skali ×25" zostaje tylko w makiecie.

### Ustalenia z kodu

- „Widok konta" z nagłówka **nie zawęża Dashboardu** (`01_state.js:29` odświeża tylko Transakcje i Podsumowanie) i startuje ustawiony na konto domyślne (`07_categories.js:195`). Gdyby Dashboard go słuchał, „Majątek netto" po wejściu pokazywałby jedno konto.
- Wykres „Przychody vs Wydatki" w Podsumowaniu bierze filtr kont z kafelków Dashboardu (`dashboardAccountIds`), które usuwamy. Commit `351e7f0` przeniósł go kiedyś z Dashboardu.
- Samouczek: krok celuje w usuwane `#networth-range-from`, a krok o „Widoku konta" błędnie obiecuje zawężenie Dashboardu.
- Pierwsze otwarcie Raportów nadpisuje daty presetem „6 miesięcy" (`renderReports()`), więc drill-through potrzebuje własnej funkcji w `16_reports.js`.
- Chart.js 4.4.0: wbudowane `stacked` inaczej traktuje warstwę o wartości 0 — ten sam błąd wyszedł w makiecie, stąd własna funkcja układania warstw.

### Decyzje (rozstrzygnięte 2026-10-18: wg rekomendacji, D3 zmienione)

1. **Filtr kont na Dashboardzie.** Rekomendacja: zawsze wszystkie konta, bez filtra. Salda pojedynczych kont zostają w liście w nagłówku i w Słownikach.
2. **Wykres w Podsumowaniu.** Rekomendacja: zostaje, przepięty na „Widok konta". Alternatywa: usunąć.
3. **Paleta.** ~~Rekomendacja: na razie tylko wykresy Dashboardu.~~ **Rozstrzygnięte 2026-10-18: paleta „Noble” jako stała kolorystyka całej aplikacji** (`PALETA` w `04_helpers.js`, wszystkie wykresy Chart.js); użytkownik będzie ją rozszerzał.
4. **Konto demo.** Opcjonalny etap C: historia 18 miesięcy z kredytem gotówkowym i rachunkiem maklerskim w `demo_service.py`. **Rozstrzygnięte 2026-10-18: tak, w tym samym wdrożeniu.**

### Etap A — majątek (PR 1)

1. Seria majątku per typ konta w `computeNetWorthSeries()`: narastanie per (typ, waluta); `value` bez zmian, dochodzi saldo i liczba kont każdego typu.
   → weryfikacja: vitest — suma typów równa `value` w każdym miesiącu, typ pojawia się od pierwszej transakcji konta, konto walutowe; istniejące testy serii zielone.
2. Czyste funkcje liczące: zmiana m/m i r/r, układanie warstw, udział w aktywach dla wskazanego miesiąca.
   → weryfikacja: vitest pisany przed kodem, w tym test odtwarzający błąd z makiety (warstwa o saldzie 0 przecinająca KO) i procent pomijany przy ujemnej bazie.
3. Kafelek „Majątek netto" w układzie z makiety; notka o kursach NBP zostaje.
   → weryfikacja: przeglądarka na koncie demo i lokalnej kopii bazy, szerokość telefonu, kwota siedmiocyfrowa.
4. Wykres „Majątek w czasie": przełączniki, wygładzenie, ikona „i", dymek, klik w miesiąc.
   → weryfikacja: przeglądarka — okres ujemny, miesiąc otwarcia nowego typu konta, konsola bez błędów.
5. Sekcja „Udział majątku wg typu kont".
   → weryfikacja: test, że udziały aktywów sumują się do 100%; ręcznie — suma dla bieżącego miesiąca równa kafelkowi.
6. Usunięcie kafelków kont i `dashboardAccountIds` z osieroconymi funkcjami i testem filtra; wykres w Podsumowaniu wg decyzji 2.
   → weryfikacja: `npm test`, grep bez pozostałych odwołań, Podsumowanie reaguje na „Widok konta".
7. Paleta jako stałe w `13_dashboard.js` (Chart.js nie czyta CSS).
   → weryfikacja: przeglądarka.
8. Samouczek (`/samouczek dashboard`) i dokumentacja: sekcja Dashboard w `CLAUDE.md`, `docs/DOCUMENTATION.md`.
   → weryfikacja: samouczek przechodzi wszystkie kroki na Dashboardzie.

### Etap B — kategorie i przejścia (PR 2)

9. Wykres „Przychody i wydatki wg kategorii" z listą wielokrotnego wyboru (wzorzec listy kategorii z Raportów). Liczy jak Raporty: po kategorii rodzica, bez przelewów, bez przeliczania walut.
   → weryfikacja: vitest — słupek miesiąca równy KPI Raportów dla tego samego miesiąca i kategorii.
10. Pasek wybranego miesiąca:
    - „Szczegółowy raport" ustawia w Raportach zakres dat i kategorie; na telefonie ukryty, jak zakładka Raporty.
    - „Pokaż transakcje" ustawia miesiąc i przełącza „Widok konta" na „Wszystkie konta"; kategorii nie przenosi (Transakcje nie mają takiego filtra).

    → weryfikacja: test funkcji ustawiającej filtry Raportów; ręcznie — liczby po przejściu zgadzają się ze słupkiem.

### Etap C — konto demo (opcjonalny, decyzja 4)

Oś czasu z makiety: −18 mies. saldo dodatnie bez kredytu; −17 mies. kredyt gotówkowy ok. 40 000 PLN wydany na remont; −8 mies. otwarcie rachunku maklerskiego; −6 mies. ostatnia rata; karta kredytowa z niewielkim zadłużeniem przez cały okres.

### Ryzyka

- **Bieżący miesiąc a kafelek.** Kafelek liczy z sald aktywnych kont, seria z transakcji wszystkich kont — mogą się rozjechać przy koncie nieaktywnym z niezerowym saldem. Sprawdzić na lokalnej kopii bazy przed krokiem 5.
- **„Rok temu"** porównuje dzisiejszy stan z końcem tego samego miesiąca rok wcześniej, nie z tym samym dniem (seria jest miesięczna).

### Tryb pracy

Osobny worktree i gałąź na każdy etap, PR do `main` z kompletem checków. Commity `feat:` z opisem efektu dla użytkownika (release-please → 1.2.0). Wdrożenie bez migracji.

## 2. Transakcje — szybki wpis

Makiety (dane przykładowe, wersja A zaakceptowana 2026-10-11):

- komputer: https://claude.ai/artifact/USwPfVWVSyeLiCDSe1gnt5
- telefon (z przyciskiem „+" i panelem od dołu): https://claude.ai/artifact/1iRZoSts1HPrqwjfVH3i1H
- odrzucona wersja B („Kwota i kafelek"): https://claude.ai/artifact/WYDi7h3CR5nM5ZDHjPyQXS

Zmiana wyłącznie frontowa: zapis idzie istniejącym `POST /api/transactions`, bez modeli, migracji i nowych tras.

### Co pokazuje makieta

- **Nagłówek „Nowa transakcja"** zamiast „+ Dodaj transakcję": bez ikony plusa, większym krojem; obok ikona „i" z instrukcją. Akcje poboczne (Uzgodnij saldo, Importuj wyciąg, Transakcje cykliczne) jako odnośniki, więc jedynym przyciskiem sekcji jest „Zapisz".
- **Jedno pole wpisu**: `biedronka 85,60 wczoraj` + Enter. Rozpoznaje kwotę, kontrahenta (z kategorią domyślną), samą kategorię, datę (`wczoraj`, `przedwczoraj`, `9.10`), konto (`@…`) i przelew własny (`>…`).
- **Autouzupełnianie**: lista kontrahentów i kategorii po pierwszych literach, po `>` i `@` lista kont. Tab dokańcza, strzałki wybierają, Enter po wyborze strzałkami też dokańcza.
- **Szara podpowiedź kolejnego kroku w polu**: dokończenie nazwy → `kwota` → `data  ↵ dziś` → `↵ zapisz`.
- **Rotujące przykłady** w pustym polu, z linią tłumaczącą, co dany przykład by zapisał.
- **„Najczęstsze"** — przyciski najczęściej używanych kontrahentów.
- **Rząd rozpoznanych pól** pod spodem (kwota, kontrahent, kategoria, konto, data); ręczna poprawka wygrywa z rozpoznaniem.
- **„Zapisz" na dole formularza**, w jednym rzędzie z linią „Zapisze: …"; opcja „Zachowaj datę i konto dla kolejnego wpisu".
- **Po zapisie** nowy wiersz ląduje podświetlony w Historii operacji, z „Cofnij".
- **Telefon**: pole i „Zapisz" na całą szerokość, pola w dwóch kolumnach, podpowiedzi wybierane dotknięciem, bez symboli klawiszy. Pasek skrótów „@ konto" / „> przelew" **tylko na urządzeniu dotykowym** — wąskie okno na komputerze go nie pokazuje.

### Podejście

Pole szybkiego wpisu **zastępuje pole „Podpowiedź" (`tx-desc`)**, a istniejące pola formularza zostają jako rząd rozpoznanych pól — z tymi samymi `id`, comboboxem kontrahenta, polem konta docelowego i tym samym handlerem zapisu. Nowy kod to: rozkład tekstu na pola, lista podpowiedzi i przestawienie układu. Dzięki temu okno szybkiego dodania kontrahenta/kategorii, przelewy (`resolveOrCreateTransferContractorId`) i znak kwoty z typu kategorii działają bez zmian.

### Ustalenia z kodu

- Tekst z „Podpowiedzi" jest dziś zapisywany jako **tytuł transakcji** (`desc`, kolumna „Opis" w Historii operacji) — `11_transactions.js:39`, `:79`.
- Transakcja przyjmuje tylko kontrahenta ze słownika (`contractor_id`); wolnego tekstu jako kontrahenta nie ma.
- Rozpoznawanie robi `handleAutoFill()` (`10_contractors.js:94`): nazwa (min. 3 znaki) albo reguła (min. 2) **zawarta** w tekście, pierwsze trafienie w kolejności słownika, wrażliwe na polskie znaki. Ta sama funkcja obsługuje edycję wiersza i formularz cyklicznych.
- Po zapisie formularz czyści opis, kwotę, kontrahenta i komentarz, a **data i konto zostają** (`11_transactions.js:95–102`).
- Konto podpowiada `preferredFormAccountId()`: konto z „Widoku konta", jeśli wybrane, inaczej główne.
- `showToast()` przyjmuje tylko tekst i znika po 3,5 s — nie ma przycisku akcji.
- `99_bootstrap.js:1` ustawia domyślną datę przez `toISOString()`, czyli w UTC.
- Samouczek Transakcji celuje w `#tx-contractor-input`, `#submit-btn`, `#openImportModalBtn`, `#openRecurringModalBtn` i cytuje nazwy „Importuj wyciąg z banku" oraz „Transakcje Cykliczne".
- `tests/js/split.test.js` buduje atrapę DOM z `#tx-desc`.

### Decyzje (rozstrzygnięte 2026-10-18: wszystkie wg rekomendacji)

Każda to miejsce, w którym makieta rozjeżdża się z obecną aplikacją albo wymaga poprawki przed wdrożeniem.

1. **Tytuł transakcji.** Makieta nie ma tytułu, a aplikacja zapisuje go z pola „Podpowiedź". Rekomendacja: tytułem jest część tekstowa wpisu (bez kwoty, daty i znaczników); gdy jest pusta — nazwa kategorii.
2. **Nieznany kontrahent.** Makieta mówi „zostaje jako tekst", ale aplikacja nie zapisuje kontrahenta spoza słownika. Rekomendacja: tekst trafia do tytułu, kontrahent zostaje pusty, a lista podpowiedzi dostaje pozycję „Dodaj kontrahenta «X»", która otwiera istniejące okno szybkiego dodawania z wpisaną nazwą.
3. **Reguły rozpoznawania.** Makieta dopasowuje po początku nazwy i ignoruje polskie znaki; aplikacja szuka nazwy lub reguły w środku tekstu i polskie znaki rozróżnia. Rekomendacja: jedna wspólna funkcja dopasowania (dzisiejsze reguły + nieczułość na polskie znaki) dla szybkiego wpisu, edycji wiersza i cyklicznych; lista podpowiedzi po początku nazwy. Skutek uboczny: edycja i cykliczne też zaczną łapać `zabka` → Żabka.
4. **Komentarz.** Jest w obecnym formularzu, nie ma go w makiecie. Rekomendacja: zostaje jako ostatnie pole rzędu.
5. **Kategoria przelewu po `>`.** Makieta ma jedną kategorię „Przelew własny"; w aplikacji kategorii typu transfer może być kilka. Rekomendacja: pierwsza kategoria typu transfer, do zmiany w polu Kategoria; istniejące pole konta docelowego pokazuje się w rzędzie jak dziś.
6. **Nazwy kont w `@` i `>`.** Makieta wstawia jedno słowo wskazujące konto (`>oszczędnościowe`). Prawdziwe nazwy bywają wielowyrazowe i dzielą słowa (np. dwa konta w tym samym banku) — wtedy jedno słowo nie wskazuje konta jednoznacznie i makieta wybrałaby po cichu pierwsze pasujące. Rekomendacja: wybór z listy ustawia pole Konto albo Konto docelowe i usuwa znacznik z tekstu. To zmienia zaakceptowane zachowanie makiety. **Zmienione 2026-10-18 po teście:** znacznik zostaje w tekście jako pełna nazwa konta ze spacjami („>Poduszka Finansowa”; rozpoznawana jest najdłuższa pasująca nazwa, samo słowo nadal działa jako skrót) — znikający albo ucięty znacznik wyglądał jak błąd.
7. **Data i konto po zapisie.** Dziś oba pola zawsze zostają; w makiecie wracają do „dziś" i konta domyślnego, chyba że zaznaczono „Zachowaj datę i konto". Rekomendacja: jak w makiecie — inaczej podpowiedź „↵ dziś" bywałaby nieprawdziwa. Zmienia dotychczasowy nawyk.
8. **Konto domyślne.** Makieta bierze konto główne; aplikacja bierze konto z „Widoku konta", jeśli jest wybrane. Rekomendacja: zostaje reguła aplikacji.
9. **„Cofnij" po zapisie.** Komunikaty w aplikacji nie mają przycisków. Rekomendacja: rozszerzyć `showToast()` o opcjonalną akcję; cofnięcie to zwykłe usunięcie (trwałe, przy przelewie obie nogi). Alternatywa: bez „Cofnij", zostaje ikona usuwania w wierszu.
10. **Błąd daty domyślnej.** Domyślna data liczona w UTC daje wczorajszy dzień między północą a 1:00 zimą (2:00 latem). „Dziś (domyślnie)" odziedziczyłoby ten błąd. Rekomendacja: `toLocalISODate()` z `04_helpers.js`, jako osobny commit `fix:`.
11. **Data z przyszłości.** Pole Data przyjmuje dowolną datę; zapis `9.10` w szybkim wpisie zawsze oznacza ostatnie takie wystąpienie w przeszłości. Rekomendacja: tak zostaje, przyszłą datę ustawia się w polu Data.
12. **„Najczęstsze".** W makiecie lista jest wpisana na sztywno. Rekomendacja: pięciu kontrahentów z największą liczbą transakcji z ostatnich 90 dni, bez „Moje konto: …", liczone w przeglądarce z załadowanych transakcji.

### Etap T — szybki wpis (PR 3)

1. `fix:` domyślna data w czasie lokalnym (decyzja 10).
   → weryfikacja: test w `tests/js/bootstrap.test.js` z zegarem ustawionym na 00:30 czasu lokalnego.
2. Wspólna funkcja dopasowania kontrahenta wydzielona z `handleAutoFill()` (decyzja 3).
   → weryfikacja: vitest opisujący obecne zachowanie napisany przed zmianą; potem przypadki z polskimi znakami.
3. Rozkład wpisu na pola jako czysta funkcja w nowym module `21_szybki_wpis.js`.
   → weryfikacja: vitest pisany przed kodem — sześć przykładów z makiety, samo `12.10` jako kwota, `43 9.10` jako kwota i data, data z przyszłości cofnięta o rok, przelew na konto źródłowe odrzucony.
4. Pole, lista podpowiedzi, szara podpowiedź kroku, klawisze (Tab, strzałki, Enter, Esc), rotujące przykłady, „Najczęstsze" — wypełniają istniejące pola formularza.
   → weryfikacja: vitest z atrapą DOM (wzór: `reports.test.js`) i testem, że `id` z atrapy istnieją w `base.html`; test XSS — nazwa kontrahenta z kodem HTML wyświetla się jako tekst.
5. `base.html`: nagłówek „Nowa transakcja" z ikoną „i" (wspólny wzorzec z sekcją 1), akcje jako odnośniki, „Zapisz" na dole z linią podsumowania, opcja „Zachowaj datę i konto", pasek skrótów tylko na urządzeniu dotykowym.
   → weryfikacja: przeglądarka na komputerze i w szerokości telefonu; szara podpowiedź stoi równo za wpisanym tekstem.
6. Zapis: tytuł (decyzja 1), reset pól (decyzja 7), podświetlenie nowego wiersza, „Cofnij" (decyzja 9).
   → weryfikacja: ręcznie na koncie demo — wydatek, przychód, przelew (obie nogi i salda obu kont), cofnięcie; `pytest` bez zmian.
7. Samouczek (`/samouczek transactions`) i dokumentacja: kroki celujące w zmienione elementy, nowe nazwy przycisków, liczba modułów JS w `CLAUDE.md`.
   → weryfikacja: samouczek przechodzi wszystkie kroki w zakładce i w oknie importu.

### Poza zakresem

- Wpis z datą spoza widocznego miesiąca albo na konto inne niż „Widok konta" zapisuje się, ale nie widać go w Historii operacji. Pominięte decyzją z 2026-10-11 — bez dodatkowej obsługi.
- Historia operacji w makiecie jest tylko ilustracją; prawdziwa tabela i jej układ na telefonie zostają bez zmian.

### Ryzyka

- **Szara podpowiedź** jest nałożona na pole; przy kroju „Lora" i bardzo długim wpisie może się rozjechać z tekstem. Do sprawdzenia w przeglądarce w kroku 5.
- **Klawiatura ekranowa** może zasłaniać listę podpowiedzi — wyjdzie dopiero na prawdziwym telefonie.

### Szybki wpis z każdej zakładki na telefonie (Etap T2)

Dodane 2026-10-18; pokazane w makiecie telefonu (link wyżej) — ekran Dashboardu z przyciskiem „+".

**Co pokazuje makieta**

- **Przycisk „+" w prawym dolnym rogu**, widoczny od razu po zalogowaniu, na każdej zakładce poza Transakcjami.
- **Panel wysuwany od dołu** z tym samym formularzem szybkiego wpisu — przeniesionym, nie skopiowanym. Kursor stoi w polu, więc klawiatura otwiera się od razu.
- **Po zapisie panel się zamyka**, zostajesz na tej samej zakładce, a na dole pojawia się komunikat z „Cofnij". Z zaznaczonym „Zachowaj datę i konto" panel zostaje otwarty na kolejny wpis.
- **Zamykanie**: ×, dotknięcie tła albo Esc (pierwszy Esc zamyka listę podpowiedzi, drugi panel). Fokus wraca na „+".
- **Skrót na ekranie głównym telefonu**: adres z parametrem otwiera aplikację od razu z panelem (w makiecie `#dodaj`, w aplikacji `?dodaj=1`).

**Ustalenia z kodu**

- `/` pokazuje gościowi wizytówkę, a `/login` przekierowuje zalogowanego na `/` i gubi parametry adresu (`home_bp.py:7–19`).
- Parametry `?demo=1` i `?rejestracja=1` obsługuje już `99_bootstrap.js` — skrót może iść tym samym wzorcem.
- Logowanie woła `login_user(user)` bez „zapamiętaj mnie", a `config.py` nie ustawia trwałej sesji, więc ciasteczko logowania jest sesyjne.

**Decyzje (rozstrzygnięte 2026-10-18: wg rekomendacji; T16 poza zakresem; numeracja ciągła z listą wyżej)**

13. **„+" na zakładce Transakcje.** Rekomendacja: ukryty, bo formularz stoi tam na górze. Alternatywa: widoczny zawsze, dla spójności.
14. **Na jakich urządzeniach widać „+".** Rekomendacja: tylko na dotykowych, tak jak pasek skrótów; wąskie okno na komputerze go nie dostaje, a na komputerze nie ma go wcale.
15. **Skrót a logowanie.** Skrót na `/?dodaj=1` pokazałby wylogowanemu wizytówkę, a `/login` zgubiłby parametr. Rekomendacja: skrót prowadzi na `/login?dodaj=1`, trasa `/login` przy przekierowaniu zachowuje parametr, a front pamięta „otwórz panel" przez logowanie i otwiera go po załadowaniu danych.
16. **Trwałość logowania na telefonie.** Sesyjne ciasteczko może wymagać ponownego logowania po zamknięciu przeglądarki, co spowalnia wpis bardziej niż przejście między zakładkami. Rekomendacja: poza tym etapem — osobna zmiana z przeglądem bezpieczeństwa (np. opcja „Zapamiętaj mnie" przy logowaniu, włączana świadomie przez użytkownika).

Komunikat z „Cofnij" w panelu zależy od decyzji 9.

**Kroki (PR 4, po etapie T)**

1. Przycisk „+" i panel w `base.html`; formularz przenoszony do panelu i z powrotem jako jeden element (bez drugiej kopii `id`); fokus zamknięty w panelu, dopóki jest otwarty.
   → weryfikacja: vitest z atrapą DOM — po otwarciu i zamknięciu formularz wraca na miejsce, `#transaction-form` występuje raz, „+" jest ukryty na zakładce Transakcje.
2. Zamykanie po zapisie (chyba że „Zachowaj"), ×, tłem i Esc; fokus wraca na „+"; komunikat z „Cofnij".
   → weryfikacja: vitest z sekwencjami z makiety; ręcznie w przeglądarce w szerokości telefonu.
3. Skrót `?dodaj=1` według decyzji 15: `/login` zachowuje parametr, `99_bootstrap.js` otwiera panel po załadowaniu danych, także po zalogowaniu.
   → weryfikacja: pytest — zalogowany na `/login?dodaj=1` trafia na `/?dodaj=1` (rozszerzenie `test_zalogowany_na_login_wraca_do_aplikacji`); vitest dla `99_bootstrap.js`.
4. Samouczek: krok wskazujący „+" (na komputerze pominie go `krokWidoczny`).
   → weryfikacja: na telefonie samouczek pokazuje krok, na komputerze go pomija.
5. Prawdziwy telefon.
   → weryfikacja: ręcznie na Androidzie (i iOS, jeśli dostępny) — pole i lista podpowiedzi zostają widoczne nad klawiaturą ekranową.

**Ryzyka**

- Panele przyklejone do dołu ekranu zachowują się różnie przy otwartej klawiaturze, szczególnie w Safari na iOS; może być potrzebne dopasowanie wysokości do widocznej części ekranu. Wyjdzie dopiero na urządzeniu.

## 3. Import wyciągów (dawniej „Do weryfikacji")

Makieta (dane przykładowe, 2026-10-24): https://claude.ai/artifact/PrFZnW8iMBB7sVQ7vdFNMw

Stan: **propozycja do oceny**, nic nie wdrożone.

### Co pokazuje makieta

- **Nazwa**: „Import" w menu (z licznikiem) i „Import wyciągów" jako nagłówek strony.
- **Wgrywanie na stronie**, bez okna: pole „Przeciągnij tu pliki z banku" z przyciskiem „Wybierz pliki" i „albo cały folder", zwinięte „Ustawienia ręczne" (bank, konto), wynik importu per plik („ing_2026-09.csv → Moje ING · 12 operacji, 2 pominięte") i „Historia importów". Przycisk „Importuj wyciąg" znika z zakładki Transakcje.
- **Nagłówek poczekalni**: „Na zatwierdzenie czeka 15 operacji z 3 kont", przyciski „Zatwierdź gotowe (11)", „Rozpoznaj ponownie", „Odrzuć wszystkie".
- **Filtry prostym językiem**: Wszystkie · Gotowe · Do uzupełnienia · Możliwe duplikaty · Przelewy między kontami.
- **Sekcja „Przelewy między Twoimi kontami"** na górze, jedna linia na przelew:
  - kolumna „Przelew": „Moje ING → Wakacje" z podkreślonym kontem, z którego wyciągu pochodzi operacja, i tytułem z banku;
  - kolumna „Druga strona" opisana słowami: „Obie operacje są w tym imporcie", „Druga strona jest już zaksięgowana", „Dopisze ją aplikacja" albo, na czerwono, „Brak — zaimportuj wyciąg z mBank ROR";
  - kwota neutralna (przelew to ani wydatek, ani przychód), pod nią znak i konto („−1,00 z Moje ING");
  - **para z tego samego importu to jeden wiersz** z przyciskiem „Zatwierdź obie";
  - przy pojedynczej operacji „Zmień konto" (pole z etykietą „Na konto" albo „Z konta", zależnie od kierunku) i „To nie przelew" (przenosi operację do zwykłych, do uzupełnienia).
- **Wydatki i przychody pogrupowane po kontach**, nie po plikach (nagłówek „Moje ING · ING · 45…1111 · 6 operacji"): kolumny Data, Z wyciągu (tytuł + kontrahent z banku), Kontrahent, Kategoria, Kwota. Status jako pasek z lewej i plakietka: Gotowe, Uzupełnij kategorię, Możliwy duplikat. Sugestia kontrahenta jako „Nowy: Decathlon · Dodaj". Jeden plik z ING potrafi zawierać kilka kont, a operacje z wcześniejszych importów trafiają do sekcji swojego konta — mówi o tym zdanie pod nagłówkiem poczekalni, a wynik importu na górze pokazuje, który plik trafił na które konta („ing_2026-09.csv → Moje ING i Wakacje").
- **Podgląd możliwego duplikatu bez wychodzenia z importu** (dodane 2026-10-24): „Porównaj z historią" rozwija pod wierszem porównanie „Z wyciągu" / „Już w historii" (data z różnicą dni, kwota, tytuł, kontrahent, kategoria, komentarz, skąd pochodzi zapis) oraz fragment historii tego konta z okna ±4 dni, w którym pasujące kwotą operacje są wyróżnione i można wybrać, z którą porównać. Domyślnie wybrana jest najbliższa data. Przyciski „To ta sama — odrzuć wiersz z wyciągu" i „To inna operacja — zostaw".
- **„Widok konta" nie dotyczy importu** — strona zawsze pokazuje wszystkie konta.
- **Na telefonie zakładka jest ukryta**, jak Raporty.

### Ustalenia z kodu

- Wiersz poczekalni należy do jednego konta (`account_id`), ale tabela **nie pokazuje konta** przy wydatkach i przychodach; przy przelewie widać je tylko jako podkreślenie w linii „Z: … → Na: …" (`transfer_own`).
- Dla przelewu pierwsze pole to zawsze „Wybierz konto docelowe…" (`03_staging.js:292`), a pokazuje konto **po drugiej stronie** (kontrahent „Moje konto: X"). Dla operacji wpływu (np. Wakacje +800) to konto, z którego pieniądze przyszły — etykieta „docelowe" jest wtedy myląca. Drugie pole to kategoria, zwykle „Przelew wewnętrzny", powtarzająca plakietkę „Przelew".
- Kierunek strzałki bierze się ze znaku kwoty (#169), więc obie operacje pary pokazują tę samą linię „Z: Moje ING → Na: Wakacje" i różnią się tylko podkreśleniem — stąd wrażenie dwóch takich samych przelewów.
- Stan drugiej strony (`transfer_pair`: staging / booked / mirror / missing) liczy `_pair_staging_transfer_legs()`. Para jest wykrywana 1:1, ale odpowiedź `/api/staging/pending` **nie mówi, która operacja jest partnerem** — tylko że partner istnieje.
- Stan `mirror` celowo nie ma plakietki (`03_staging.js:79–80`).
- „Zatwierdź zmapowane" zatwierdza wszystkie w pełni przypisane wiersze, **także oznaczone jako możliwy duplikat** (`approveAllStaging`, warunek `isFullyMapped`).
- Zatwierdzanie idzie wiersz po wierszu (`POST /api/staging/<id>/approve`); para zatwierdzona po kolei łączy się sama (druga operacja widzi pierwszą jako `booked`).
- „Do weryfikacji" pojawia się w `base.html`, `03_staging.js`, `17_tour.js` (samouczek transakcji, okna importu i zakładki), `18_feedback.js` (nazwa zakładki w zgłoszeniach), `import_bp.py` (komunikat po imporcie) i obu dokumentach w `docs/`.
- Zakładka jest dziś widoczna na telefonie (bez `hidden sm:flex`), choć przycisk importu jest tam ukryty.
- Kandydaci na duplikat (`_duplicate_candidates`) niosą tylko id, datę, tytuł, surowy tekst kontrahenta, kategorię, pochodzenie i różnicę dni. Pełna transakcja (kontrahent ze słownika, komentarz, podział) i reszta historii konta są już na froncie w globalnym `transactions` z `/api/init`, więc podgląd **nie wymaga zmian na serwerze**.
- Wiersz poczekalni **nie pamięta, z którego pliku pochodzi** — `TransactionStaging` nie ma powiązania z `StatementImport` (ten ma nazwę pliku, ale per konto i partia importu).

### Decyzje do potwierdzenia (otwarte)

1. **Nazwa zakładki.** Propozycja użytkownika: „Importowanie wyciągu". Rekomendacja: „Import" w menu (pasek zakładek jest ciasny, a licznik stoi obok) i „Import wyciągów" w nagłówku strony.
2. **Wgrywanie na stronie zamiast okna.** Rekomendacja: przenieść zawartość okna importu na stronę (strona służy tylko temu). Prostsza alternatywa: przycisk w nagłówku strony otwiera dotychczasowe okno.
3. **Para jako jeden wiersz.** Wymaga, żeby serwer podawał identyfikator partnera (`transfer_pair_id`) — zmiana w `list_pending_staging`. Rekomendacja: tak; „Zatwierdź obie" to dwa zatwierdzenia po kolei, a przy błędzie drugiego zostaje ono na liście jako „druga strona już zaksięgowana". **Pary między walutami** (wymiana w Revolucie: obie operacje tego samego dnia, z identycznym tytułem, ale różne kwoty) pokazują **dwie kwoty z walutami kont** zamiast jednej — makieta ma tylko pary w PLN. Każda kwota przelewu, także pojedynczej operacji, idzie w walucie swojego konta (`walutaKonta()`), nie „PLN" na sztywno.
4. **Poprawianie pary.** Wiersz pary w makiecie nie ma „Zmień konto" (dziś każda operacja ma swoje pole). Rekomendacja: link „Rozdziel", który pokazuje obie operacje osobno, każdą z „Zmień konto".
5. **Kategoria przy przelewie.** Rekomendacja: ukryta, gdy użytkownik ma jedną kategorię typu przelew; widoczna tylko przy kilku.
6. **Stan „Dopisze ją aplikacja".** Dziś celowo bez plakietki. Rekomendacja: pokazywać — właśnie tego brakowało przy interpretacji przelewu na konto bez wyciągów.
7. **„Zatwierdź gotowe" a duplikaty.** Dziś możliwe duplikaty zatwierdzają się hurtem razem z resztą. Rekomendacja: pomijać je, dopóki użytkownik nie rozstrzygnie („To ta sama" / „To inna operacja"). Zmienia obecne zachowanie.
8. **Filtry.** Rekomendacja: „Auto-sugestia", „Częściowo" i „Niezmapowane" łączą się w jedno „Do uzupełnienia"; dochodzi „Przelewy między kontami".
9. **Sortowanie.** Dziś po dacie, tytule i kwocie w jednej tabeli. Rekomendacja: zostaje, ale w obrębie każdej grupy (konta, przelewy).
10. **„Widok konta" na tej zakładce.** Rekomendacja: ukryć przełącznik w nagłówku, gdy otwarty jest Import; samouczek mówi o tym w kroku 2 („operacje wszystkich kont"). Alternatywa: zostawić z dopiskiem „nie dotyczy importu".
11. **Telefon.** Rekomendacja: zakładka ukryta jak Raporty (`hidden sm:flex`). Skutek: na telefonie nie da się zatwierdzić poczekalni i nie widać licznika.
12. **Źródło danych podglądu duplikatu.** Rekomendacja: z globalnego `transactions` po id kandydata (bez zmian na serwerze). Skutek: kandydat z konta nieaktywnego też się pokaże, bo `/api/init` niesie transakcje kont nieaktywnych.
13. **Plik źródłowy przy operacji.** Sekcje to konta, nie pliki. Rekomendacja: wystarczy nazwa banku w nagłówku sekcji i lista „plik → konta" w wyniku importu. Dokładna nazwa pliku przy każdej operacji wymagałaby nowej kolumny w poczekalni i migracji — nie rekomenduję, dopóki nie będzie realnej potrzeby.
14. **Kilka plików naraz a pliki bez numeru rachunku.** Przy imporcie wielu plików wybór konta jest dziś ignorowany (`02_import.js:139–140`), a parsery plików jednokontowych bez numeru (Revolut CSV, jednokontowy CSV z ING) odmawiają bez konta — taki plik kończy się błędem na liście wyników. „Ustawienia ręczne" z makiety działają więc tylko przy jednym pliku. Rekomendacja: przy pliku odrzuconym z powodu braku konta lista wyników pokazuje wybór konta i „Wgraj ponownie" dla tego jednego pliku. Alternatywa: zostawić jak dziś i napisać przy polu wgrywania, że takie pliki wgrywa się pojedynczo.

### Uwagi do implementacji (przegląd 2026-11-01)

- **„To nie przelew"** — wyjście dla operacji, którą import błędnie uznał za przelew między kontami. Rozpoznanie (`analyze_transaction_data`, `budget_service.py:987`) jest pewne tylko przy zgodnym numerze rachunku drugiej strony; reguła kontrahenta „Moje konto: X" i dopasowanie przybliżone potrafią złapać obcą operację. Przycisk:
  - przenosi operację z sekcji przelewów do grupy jej konta jako „Do uzupełnienia";
  - czyści kategorię **i kontrahenta** — sama zmiana kategorii zostawiłaby „Moje konto: X" przy wydatku albo przychodzie. Ta sama pułapka istnieje dziś przy ręcznej zmianie kategorii w poczekalni (lista kontrahentów dalej pokazuje „Moje konto: X");
  - zmienia wyłącznie stan w przeglądarce (jak dziś `updateStagingLocalState`), serwer dostaje wynik dopiero przy zatwierdzeniu — bez nowej trasy;
  - jest tylko przy pojedynczej operacji; parę najpierw rozdziela „Rozdziel" (decyzja 4).

  Osobny przycisk jest potrzebny, bo wiersz przelewu w nowym układzie nie ma listy kategorii (decyzja 5) — bez niego nie da się wyjąć operacji z sekcji przelewów.
- **`transfer_pair_id`**: `_pair_staging_transfer_legs()` zwraca dziś same stany; trzeba zwracać też indeks partnera. Funkcja ma jedno wywołanie (`list_pending_staging`, `budget_service.py:1415`). Testy parowania są w `tests/test_import_flow.py` i `tests/test_transfer_coverage.py` — tam dopisać przypadki z partnerem.
- **Stan po zatwierdzeniu jednej operacji pary.** `approveStaging()` usuwa wiersz lokalnie i nie odświeża poczekalni, więc partner zostaje z nieaktualnym stanem „w tym imporcie". Po „Zatwierdź obie" (zwłaszcza przy błędzie drugiego zatwierdzenia) poczekalnię trzeba pobrać od nowa.
- **Okno podglądu duplikatu** to ±4 dni po stronie serwera (`_DUPLICATE_MATCH_WINDOW_DAYS`, `budget_service.py:1152`). Front musi użyć tej samej wartości — stała z komentarzem wskazującym źródło albo wartość w odpowiedzi `/api/staging/pending`.
- **Liczniki.** Licznik w menu liczy operacje (para = 2, jak dziś), filtry liczą wiersze na ekranie (para = 1) — zapisać to w kodzie, żeby rozjazd nie wyglądał na błąd.
- **XSS.** Tytuł i kontrahent z banku przy przelewie przychodzącym ustala nadawca — wszystko z poczekalni do HTML tylko przez `escapeHtml()` albo `textContent`.

### Samouczek (krok 5)

Treść według `/samouczek` (akcja → efekt, selektory wyłącznie po ID, najwyżej 5 kroków). Projekt zakłada rekomendacje decyzji 1, 2, 7, 10 i 14 — przy innym rozstrzygnięciu poprawić wskazany krok.

**Założenie: klucz zakładki zostaje `staging`.** Zmienia się tylko nazwa wyświetlana (decyzja 1). Identyfikator zakładki (`06_tabs.js`, `#tab-staging`) i klucz w `TOURS` zostają — nowa nazwa wewnętrzna nic nie daje użytkownikowi, a rozlałaby się na `06_tabs.js`, `18_feedback.js` i samouczek.

**Ustalenie:** konto rozpoznaje się tylko po numerze rachunku — pliki bez niego (Revolut CSV, wyciąg ING z jednym kontem) przy imporcie kilku plików kończą się błędem (decyzja 14). Krok `#csvFileInput` okna importu mówi o tym od PR #240 (2026-11-03); krok 2 poniżej przenosi tę treść na stronę.

**Zakładka Import — klucz `staging`, od nowa** (dziś 4 kroki o poczekalni; okno importu ma osobne 4):

| # | `el` | akcja | efekt |
|---|------|-------|-------|
| 1 | `#demo-sample-statement` (tylko demo, przenosi się z okna na stronę) | Pobierz przykładowy wyciąg | Gotowy plik w formacie ING, żeby wypróbować import bez własnego wyciągu z banku. Plik nie ma numeru rachunku, więc przed wgraniem wskaż w „Ustawieniach ręcznych” konto „Konto osobiste”. |
| 2 | `#import-dropzone` (nowe ID) | Przeciągnij tu wyciągi ze wszystkich swoich kont naraz | Bank rozpozna się po zawartości pliku, a konto po numerze rachunku z wyciągu; o plik bez numeru (Revolut, jednokontowy CSV z ING) aplikacja zapyta na liście wyników. Operacje wszystkich kont trafią do poczekalni poniżej, pogrupowane po kontach — salda jeszcze się nie zmienią. |
| 3 | `#stg-transfers-heading` (nowe ID, nagłówek sekcji przelewów) | Sprawdź przelewy między swoimi kontami | Każdy przelew to jeden wiersz „skąd → dokąd”, a kolumna „Druga strona” mówi, czy saldo drugiego konta też się zmieni — czerwone „Brak” znaczy, że trzeba zaimportować jego wyciąg. Gdy aplikacja wzięła zwykłą operację za przelew, kliknij przy niej „To nie przelew”. |
| 4 | `#sf-duplicate` (zostaje) | Kliknij filtr „Możliwe duplikaty” | Zostaną operacje, dla których na tym samym koncie jest już wpis o tej samej kwocie w oknie ±4 dni; „Porównaj z historią” pokaże go obok, bez wychodzenia z importu. „Zatwierdź gotowe” pominie je, dopóki nie rozstrzygniesz. |
| 5 | `#approve-all-btn` (ID zostaje, napis „Zatwierdź gotowe”) | Kliknij „Zatwierdź gotowe” | Dopiero teraz operacje trafiają do historii i zmieniają salda kont. Wiersze do uzupełnienia i możliwe duplikaty czekają dalej w poczekalni. |

- Poza demo samouczek ma 4 kroki; przy pustej poczekalni `krokWidoczny` pomija kroki 3–5 i zostaje wgrywanie. Nagłówek sekcji przelewów nie może sam mieć klasy `hidden` (ukrywać trzeba sekcję wokół niego) — inaczej skrypt weryfikacji ze `/samouczek` zgłosi go jako „UKRYTY DOMYŚLNIE".
- Wariant przy decyzji 14 = alternatywa: w kroku 2 „…plik bez numeru (Revolut, jednokontowy CSV z ING) wgraj osobno, wskazując konto w „Ustawieniach ręcznych”."
- Świadomie pominięte: „Zajrzyj tu po każdym imporcie" (`#staging-heading` — strona sama jest importem), „Popraw kategorię i kontrahenta" (`#th-stg-mapping` — oczywiste przy kolumnach Kontrahent i Kategoria), wybór konta (`#import-account-select` — zwinięty w „Ustawieniach ręcznych", krok 2 mówi, kiedy jest potrzebny), osobny krok o „Widoku konta" (przełącznik ukryty na Imporcie, decyzja 10; krok 2 mówi „operacje wszystkich kont").

**Transakcje — klucz `transactions`** (5 → 4 kroki):
- usunąć krok `#openImportModalBtn` (przycisk znika, decyzja 2);
- w kroku `#submit-btn` „bez etapu weryfikacji, w odróżnieniu od importu z pliku" → „w odróżnieniu od wyciągu z banku, który najpierw czeka w poczekalni zakładki Import"; reszta tekstu bez zmian.

**Okno importu — klucz `import` i silnik:**
- przy decyzji 2 = tak klucz `import` znika razem z oknem, a z nim `TOUR_MODAL_KEYS` i gałąź szukająca otwartego okna w `aktywnyTour()` — okno importu jest jedynym użytkownikiem tego mechanizmu, więc zostałby martwy kod. `krokWidoczny` zostaje bez zmian (komentarz o oknach modalnych do skrócenia). Akapit „Samouczek" w `CLAUDE.md` traci zdania o kluczu `import`;
- przy decyzji 2 = alternatywa (okno zostaje) klucz `import` zostaje; poprawić tylko nazwę zakładki w kroku `#submitImportBtn` (tekst `#csvFileInput` poprawiony w PR #240).

### Kroki (PR 5)

1. Serwer: `transfer_pair_id` w odpowiedzi poczekalni (decyzja 3).
   → weryfikacja: pytest — para z jednego importu wskazuje na siebie nawzajem; trzy wpływy przy jednym wypływie dają jedną parę (parowanie 1:1); pozostałe stany bez partnera.
2. Czyste funkcje frontu: grupowanie po kontach, łączenie par, status wiersza (Gotowe / Do uzupełnienia / Możliwy duplikat), opis drugiej strony, etykieta kierunku („Na konto" / „Z konta") i okno historii do podglądu duplikatu (operacje konta z ±4 dni, kandydaci od najbliższej daty).
   → weryfikacja: vitest pisany przed kodem — operacja wpływu dostaje „Z konta", para daje jeden wiersz z dwiema operacjami, duplikat nie jest „Gotowe" (decyzja 7), okno podglądu obejmuje dokładnie ±4 dni i tylko konto wiersza.
3. `base.html` i `03_staging.js`: nowy układ strony, wgrywanie na stronie (decyzja 2), filtry, „Zatwierdź obie", „Rozdziel", „Zmień konto", „To nie przelew"; nazwa zakładki (decyzja 1); ukrycie na telefonie (decyzja 11).
   → weryfikacja: vitest z atrapą DOM i testem zgodności `id` z `base.html`; ręcznie na koncie demo (poczekalnia ma tam parę i operację bez pary) — zatwierdzenie pary zmienia salda obu kont, operacja „missing" zostaje niesparowana; podgląd duplikatu po dopisaniu ręcznej transakcji o tej samej kwocie i dacie co wiersz poczekalni; para Revolut w dwóch walutach (dane z `tests/test_revolut.py`) pokazuje dwie kwoty; „To nie przelew" na operacji bez pary przenosi ją do grupy konta z pustym kontrahentem i kategorią, a po zatwierdzeniu jako wydatek nie powstaje lustro na drugim koncie.
4. Usunięcie przycisku z Transakcji i okna importu (jeśli decyzja 2 = tak) razem z osieroconym kodem `02_import.js`.
   → weryfikacja: grep bez odwołań do `import-modal` i `openImportModalBtn`; `npm test`.
5. Samouczek według podsekcji „Samouczek (krok 5)" (`/samouczek staging`, `/samouczek transactions`, usunięcie klucza `import` i `TOUR_MODAL_KEYS`) oraz nazwy: `18_feedback.js`, komunikat w `import_bp.py`, `docs/DOCUMENTATION.md`, `docs/PRZEWODNIK_UZYTKOWNIKA.md`, `CLAUDE.md` (akapity Samouczek i Import wyciągów).
   → weryfikacja: skrypt selektorów z `.claude/skills/samouczek/SKILL.md` (krok 4) daje pusty wynik, `node --check app/static/js/17_tour.js`; na koncie demo „?" na zakładce Import pokazuje 5 kroków, po „Odrzuć wszystkie" — 2 (przykładowy wyciąg i wgrywanie); na koncie spoza demo bez kroku 1; na Transakcjach 4 kroki, żaden nie wskazuje importu; grep bez „Do weryfikacji", `TOUR_MODAL_KEYS` i `import-modal`.

### Ryzyka

- **Para wykryta błędnie** (np. dwa przelewy tej samej kwoty tego samego dnia) pokaże się jako jeden wiersz. Parowanie się nie zmienia, ale łączenie w jeden wiersz czyni pomyłkę mniej widoczną — stąd „Rozdziel" (decyzja 4).
- **Wgrywanie na stronie** zmienia miejsce, w którym tryb demo podsuwa przykładowy wyciąg; link musi przejść razem z polem wgrywania.

## 4. Wnioski (Podsumowanie + Raporty)

Makieta (dane przykładowe, 2026-11-01): https://claude.ai/artifact/L7o2LjhL3byCaBxQbsPgJe

Stan: **propozycja do oceny**, nic nie wdrożone. Ustalenia z rozmowy 2026-11-01: wnioski z reguł liczonych w przeglądarce (model językowy wyłącznie własny, na serwerze — patrz „Poza zakresem”); wszystkie cztery rodzaje wniosków (trendy kategorii, jednorazowe zdarzenia, stałe opłaty, bilans); własny dashboard etapami; zakładka Dashboard zostaje osobno.

### Co pokazuje makieta

- **Jedna zakładka „Wnioski”** zamiast Podsumowania i Raportów, z jednym wyborem miesiąca na górze (domyślnie ostatni pełny miesiąc). Wnioski i widoki liczą się do niego.
- **Wnioski na górze**: karty z rodzajem (Trend kategorii, Jednorazowe zdarzenie, Stała opłata, Bilans), plakietką kierunku („więcej niż zwykle”, „podwyżka”, „nowa”…), kwotą, jednym zdaniem z porównaniem do typowego miesiąca i małym wykresem 7 miesięcy. Na górze 6 najważniejszych, reszta pod „Pokaż wszystkie”. Przy karcie „Pokaż operacje” i „Ukryj”. Rozwijane „Jak powstają wnioski” wypisuje progi.
- **Wnioski są liczone, nie wpisane**: makieta ma 19 miesięcy przykładowej historii i liczy reguły. Październik 2026: zakup w Media Expert, niższy niż zwykle odsetek przychodów, który został (z przyczyną), karnet CityFit, który przestał się pojawiać, wpływ z OLX, restauracje rosnące od 3 miesięcy, nowa opłata Disney+, podwyżka Netflixa. Styczeń: podwyżka czynszu. Lipiec: wakacje i podwyżka pensji.
- **Widoki pod wnioskami**: chipy z widokami wbudowanymi („Miesiąc w liczbach” = dawne Podsumowanie, „Przychody i wydatki w czasie” = dawny wykres z Podsumowania) i własnymi. Filtry: okres względem wybranego miesiąca (miesiąc, 3, 6 lub 12 miesięcy, od początku roku), konta, kategorie, kontrahenci; „Liczy”: oba / wydatki / przychody; „Pokaż”: w czasie / wg kategorii / wg kontrahentów. Kafelki z porównaniem do poprzedniego okresu tej samej długości (przy samych wydatkach: suma, średnio na miesiąc, liczba operacji, największy wydatek), wykres, tabela „Zestawienie” / „Operacje”. Przy 2–6 wybranych kategoriach wykres w czasie piętrzy je osobno.
- **Zapisywanie**: zmieniony widok dostaje kropkę i przyciski „Zapisz zmiany”, „Zapisz jako nowy widok”, „Cofnij zmiany”. Wbudowanych nie da się nadpisać ani usunąć. Nazwa wymagana i niepowtarzalna.
- **„Pokaż operacje” we wniosku** ustawia niezapisany widok (np. „Restauracje, maj – paź 2026”) z tabelą operacji, który można zapisać.

### Ustalenia z kodu

- Podsumowanie (`12_summary.js`) dzieli miesiąc z Transakcjami: strzałki to wspólne `changeMonth()` i `viewDate` (`04_helpers.js:107`), do tego własne pola zakresu (`filter-month`, `filter-start`, `filter-end`). Słucha „Widoku konta” (`globalAccountFilter`). Wykres „Przychody vs Wydatki” rysuje `renderDashboardChart()` z `13_dashboard.js`.
- `tab-summary` sprawdzają `01_state.js` (`changeGlobalAccount`), `04_helpers.js` (`changeMonth`), `05_recurring.js:498` i `06_tabs.js`; listę zakładek ma też `21_szybki_wpis.js:511`.
- Raporty (`16_reports.js`): filtry kont, kategorii i kontrahentów, daty z presetami liczonymi do dziś (bieżący, niepełny miesiąc wchodzi w zakres), przełącznik przelewów, kafelki, dwa wykresy, tabela do 100 wierszy. Na telefonie ukryte.
- Wejścia z innych miejsc: „cała historia konta” z listy kont (`viewAccountSummary()`, `08_accounts.js:135`, otwiera Podsumowanie) i „Szczegółowy raport” z Dashboardu (`rptPokazOkres()`, wołane z `13_dashboard.js:488`). Zgodność liczb Dashboard ↔ Raporty pilnuje `tests/js/dashboard_obroty.test.js`; Raporty mają `tests/js/reports.test.js` z testem zgodności `id` atrapy z `base.html`.
- Samouczek ma klucze `summary` i `reports` (`17_tour.js`).
- Globalny stan frontu nie zawiera podziałów transakcji — liczenie po kategoriach w przeglądarce to zawsze kategoria transakcji (jak Raporty i Dashboard), nie podziały (jak Budżet).
- Raporty, Podsumowanie i wykres obrotów na Dashboardzie sumują kwoty bez przeliczania walut. Kursy z końca miesiąca są już na froncie (`kursPLN()`, `monthly_rates` z `/api/init`).
- Aplikacja nie ma miejsca na zapis ustawień użytkownika — widoki na koncie wymagają nowej tabeli. Testy na SQLite nie obsługują kolumn JSON (`CLAUDE.md`), więc konfiguracja widoku to tekst walidowany schematem.
- Konto demo ma pełne prawa zapisu, a `wipe_user_data()` (`demo_service.py:118`) kasuje dane użytkownika tabelą po tabeli. Nowa tabela musi tam trafić, inaczej widoki zapisane przez gości przetrwają nocne odtworzenie demo.

### Decyzje do potwierdzenia (otwarte)

1. **Miesiąc Wniosków a miesiąc Transakcji.** Dziś Podsumowanie i Transakcje dzielą `viewDate`. Rekomendacja: Wnioski mają własny wybór miesiąca, domyślnie ostatni pełny; strzałki w Transakcjach go nie przestawiają. Powód: Transakcje otwierają się na bieżącym miesiącu, a wnioski liczą się z pełnych.
2. **Wnioski z bieżącego miesiąca.** Rekomendacja: brak — bieżący miesiąc pokazuje komunikat i same widoki (jak w makiecie). Alternatywa: porównanie „do tego samego dnia” — więcej reguł i więcej fałszywych alarmów w pierwszych dniach miesiąca.
3. **Przeliczanie walut.** Rekomendacja: Wnioski i widoki liczą w PLN po kursie z końca miesiąca (`kursPLN`), a konto bez kursu wypada z sum jawnie (notka jak pod Majątkiem netto). Żeby „Szczegółowy raport” z Dashboardu dawał te same liczby, `obrotyMiesieczne()` przechodzi na to samo liczenie — test `dashboard_obroty` zostaje, dochodzi przypadek konta w EUR. Alternatywa: bez przeliczania, jak dziś — wtedy wniosek „wydatki wzrosły” może wynikać z samego wyjazdu z kartą w euro.
4. **Podziały transakcji.** Rekomendacja: jak Raporty i Dashboard (kategoria transakcji). Budżet zostaje jedynym widokiem liczącym podziały — ten rozjazd jest już opisany w `CLAUDE.md`.
5. **Przelewy wewnętrzne.** Rekomendacja: zawsze poza sumami, bez przełącznika z Raportów. Przelewy widać w Transakcjach.
6. **„Widok konta”.** Rekomendacja: nie dotyczy Wniosków (jak Dashboardu) — przełącznik ukryty na tej zakładce, konta wybiera się w filtrze widoku. „Cała historia konta” z listy kont otwiera Wnioski z niezapisanym widokiem tego konta.
7. **Okres w widoku.** Makieta ma tylko okresy względne, zapisywane razem z widokiem, dzięki czemu widok się nie starzeje. Raporty mają dowolne daty od–do. Rekomendacja: okresy względne plus „Cała historia” (potrzebna „całej historii konta”); dowolny zakres dat dopiero, gdy okaże się potrzebny.
8. **„Ukryj” przy wniosku.** Makieta je ma. Rekomendacja: w pierwszej wersji bez — wniosek dotyczy jednego miesiąca i w kolejnym sam znika, a trwałe ukrywanie wymaga zapisu na koncie. Dołożyć, gdy w użyciu okaże się potrzebne.
9. **Progi reguł.** Wartości z makiety: trend ≥ 25% i ≥ 200 zł (spadek tylko w kategoriach z wydatkami co miesiąc); jednorazowy wydatek ≥ 20% typowych miesięcznych wydatków i ≥ 500 zł; nowy kontrahent ≥ 200 zł; nietypowy wpływ ≥ 300 zł; stała opłata: raz w miesiącu, 3 miesiące z rzędu, kwota ±15%, dzień ±5, zmiana ≥ 3%, „przestała się pojawiać” po 2 pustych miesiącach; bilans ± 10 punktów; przychody ≥ 5% i ≥ 300 zł; typowy miesiąc = mediana z 6 poprzednich, minimum 3 miesiące historii; „jedna przyczyna, jeden wniosek” przy 70%. Rekomendacja: przyjąć jako startowe stałe w kodzie (bez ustawień dla użytkownika) i przed wdrożeniem przepuścić przez prawdziwe dane z lokalnej kopii bazy.
10. **Telefon.** Rekomendacja: zakładka widoczna (Podsumowanie było, Raporty nie), wnioski w jednej kolumnie, widoki do oglądania; zapisywanie i zmiana widoków tylko na komputerze.
11. **Gdzie liczyć wnioski.** Rekomendacja: w przeglądarce z globalnego stanu, jak Dashboard — czyste funkcje w nowym module, testowane vitestem. Serwer miałby sens dopiero przy modelu językowym albo powiadomieniach o nowych wnioskach, których nie ma w zakresie.
12. **Zapis widoków.** Rekomendacja: na koncie — nowa tabela, lista w `/api/init`, trasy POST/PUT/DELETE, limit (np. 30 widoków). Konfiguracja wskazuje konta, kategorie i kontrahentów po ID; nieaktywny element wypada z filtra przy wyświetlaniu, a widok pokazuje o tym notkę. Alternatywa: `localStorage` — bez migracji, ale widoki tylko w jednej przeglądarce (nie będzie ich na telefonie).
13. **Wdrożenie w dwóch krokach.** Rekomendacja: PR 6a dodaje Wnioski obok Podsumowania i Raportów; PR 6b usuwa stare zakładki, gdy nowa się sprawdzi. Jeden PR byłby duży, a stare zakładki są siatką bezpieczeństwa na czas sprawdzania progów.

### Etap 2 — tablica z kafelków (poza PR 6)

Tablica to kilka widoków ułożonych w siatce; każdy kafelek ma konfigurację taką jak widok z etapu 1, więc model danych z decyzji 12 wystarcza (kafelek wskazuje zapisany widok). Do ustalenia przy etapie 2: stała siatka czy przeciąganie, rozmiary kafelków, czy wnioski mogą być kafelkiem, ile tablic.

### Poza zakresem: model językowy

Wyłącznie model uruchomiony na własnym serwerze, bez płatnego API. Przed decyzją sprawdzić zasoby VPS: model na samym procesorze potrzebuje kilku GB pamięci i odpowiada w sekundach, a dzieli maszynę z aplikacją i PostgreSQL. Rozsądna rola: opis prozą wniosków już policzonych regułami — na wejściu zestawienie, nie pojedyncze transakcje. Takie przetwarzanie trzeba opisać w polityce prywatności.

### Kroki (PR 6)

1. Czyste funkcje wniosków w nowym module: typowy miesiąc, cztery rodzaje reguł, „jedna przyczyna, jeden wniosek”, kolejność.
   → weryfikacja: vitest pisany przed kodem, na danych jak w makiecie — Media Expert jako zdarzenie jednorazowe, a nie trend Elektroniki; CityFit „przestała się pojawiać” dopiero po 2 pustych miesiącach; Disney+ „nowa” przy 2–3 płatnościach; podwyżki Netflixa i czynszu; brak wniosków przy historii krótszej niż 3 miesiące i w bieżącym miesiącu; przelewy wewnętrzne nie zmieniają żadnej sumy; konto w EUR przeliczone po kursie z końca miesiąca (przy decyzji 3 = tak).
2. Serwer: model widoku z migracją, serwis (`user_token` pierwszym argumentem, walidacja konfiguracji schematem, limit), trasy POST/PUT/DELETE, lista w `/api/init`, kasowanie w `wipe_user_data()`.
   → weryfikacja: pytest — zapis, zmiana i usunięcie z asercją statusu i stanu bazy; IDOR w `tests/test_authorization.py` (cudzy widok przy PUT/DELETE); odrzucenie nieznanych kluczy i złych wartości konfiguracji; limit; `seed-demo` kasuje widoki gościa; `flask db check` czysty.
3. Front: zakładka Wnioski (`base.html`), moduł widoków (filtry, kafelki, wykres, tabela, zapis), ukrycie „Widoku konta” na tej zakładce (decyzja 6), przekierowanie „całej historii konta” i „Szczegółowego raportu” na Wnioski.
   → weryfikacja: vitest — widok daje te same liczby co dzisiejsze Raporty przy tych samych filtrach (przypadki przeniesione z `reports.test.js`), „Szczegółowy raport” z Dashboardu otwiera ten sam miesiąc i kategorie (`dashboard_obroty.test.js` przepięty na widok), test zgodności `id` atrapy z `base.html`; ręcznie na koncie demo — „Pokaż operacje” przy każdym wniosku pokazuje operacje, które go tworzą; zapisany, zmieniony i usunięty widok przeżywa przeładowanie strony.
4. Konto demo: sprawdzić, jakie wnioski daje ostatni pełny miesiąc; jeśli za mało różnych rodzajów — dopisać do `demo_service.py` zdarzenia jak w makiecie (jednorazowy zakup, nowa opłata).
   → weryfikacja: na demo w ostatnim pełnym miesiącu co najmniej 3 wnioski różnych rodzajów; istniejące testy demo zielone.
5. Samouczek (`/samouczek`): nowy klucz zakładki (wybór miesiąca, karta wniosku, „Pokaż operacje”, filtry, zapis widoku). Dokumentacja: `CLAUDE.md` (akapity Dashboard i Raporty, liczba modułów), `docs/DOCUMENTATION.md`, `docs/PRZEWODNIK_UZYTKOWNIKA.md`, `README.md`.
   → weryfikacja: skrypt selektorów ze `/samouczek` daje pusty wynik; samouczek przechodzi wszystkie kroki na koncie demo.
6. (PR 6b, decyzja 13) Usunięcie Podsumowania i Raportów: `12_summary.js`, `16_reports.js`, klucze samouczka `summary` i `reports`, odwołania do `tab-summary` w `01_state.js`, `04_helpers.js`, `05_recurring.js`, `06_tabs.js`, `21_szybki_wpis.js`; `renderDashboardChart()` zastępuje widok wbudowany.
   → weryfikacja: grep bez `tab-summary`, `tab-reports`, `renderSummary`, `renderReports`; `npm test`; ręcznie bez błędów w konsoli — strzałki miesiąca w Transakcjach, zmiana „Widoku konta”, zapis transakcji cyklicznej.

### Ryzyka

- **Fałszywe alarmy.** Rachunki co dwa miesiące (prąd) przy krótkiej historii dają „mniej niż zwykle” — w makiecie lipiec 2025, Media −76%. Płatność kartą u jednego kontrahenta raz w miesiącu potrafi udawać stałą opłatę. Progi trzeba sprawdzić na prawdziwych danych przed wdrożeniem (decyzja 9).
- **Zmiana nawyków.** Podsumowanie było widoczne na telefonie i słuchało „Widoku konta”. Kto przeglądał tam jedno konto, zrobi to teraz filtrem kont w widoku.
- **Rozjazd liczb z Budżetem** przy transakcjach z podziałami (decyzja 4), a przy decyzji 3 = tak — także przy kontach walutowych.

## 5. Pozostałe zakładki

*(do uzupełnienia po przeglądzie)*
