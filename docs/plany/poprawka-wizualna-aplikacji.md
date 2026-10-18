# Poprawka wizualna aplikacji — plan wdrożenia

Stan: **sekcje 1 i 2 wdrożone lokalnie 2026-10-18** na gałęzi `feat/poprawka-wizualna` (worktree `budget-wizualna`), bez PR i wdrożenia na serwer. Spisany 2026-10-11. Kolejne zakładki dopisujemy jako następne sekcje.

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
6. **Nazwy kont w `@` i `>`.** Makieta wstawia jedno słowo wskazujące konto (`>oszczędnościowe`). Prawdziwe nazwy bywają wielowyrazowe i dzielą słowa (np. dwa konta w tym samym banku) — wtedy jedno słowo nie wskazuje konta jednoznacznie i makieta wybrałaby po cichu pierwsze pasujące. Rekomendacja: wybór z listy ustawia pole Konto albo Konto docelowe i usuwa znacznik z tekstu. To zmienia zaakceptowane zachowanie makiety. **Zmienione 2026-10-18 po teście:** znacznik zostaje w tekście (pierwsze jednoznaczne słowo nazwy albo pełna nazwa z „_” zamiast spacji) — znikający znacznik wyglądał jak wyczyszczenie wpisu.
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

## 3. Pozostałe zakładki

*(do uzupełnienia po przeglądzie)*
