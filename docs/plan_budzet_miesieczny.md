# Plan: planowanie budżetu miesięcznego (#96)

Dokument roboczy. Powstał z rozmowy poprzedzającej implementację — zapisuje **decyzje
i ich uzasadnienia**, żeby nie trzeba ich było odtwarzać. Do usunięcia po domknięciu #96
(tak jak wcześniejsze `docs/review_*.md`).

Gałąź: `feat/planowanie-budzetu-miesiecznego` (założona z `main` po merge PR #151).

---

## 1. Co budujemy

Zakładka **Budżet** — plan przychodów i wydatków na miesiąc, zestawiony z wykonaniem.
Nie jest to prosty limit per kategoria: planujemy obie strony, żeby było widać, czy plan
wydatków mieści się w planie przychodów.

Model `Budget` w bazie **istnieje od dawna i nie jest nigdzie używany** (`app/models.py`,
tabela `budgets`, migracje `f69346079ef2` i `639f42d22d1a`). Przyjmuje dowolną kategorię,
więc wiersz dla kategorii przychodowej to po prostu „planowany przychód".

```
budgets: id, user_token, year, month, category_id, amount
```

---

## 2. Decyzje (podjęte, nie do ponownego otwierania bez powodu)

| # | Decyzja | Uzasadnienie |
|---|---------|--------------|
| D1 | Planujemy **przychody i wydatki** | Bez planu przychodów nie wiadomo, czy plan wydatków się w czymkolwiek mieści |
| D2 | Przekroczenie planu przychodów przez plan wydatków jest **dozwolone, ale jasno pokazane** | To decyzja użytkownika, nie błąd — aplikacja ma informować, nie blokować |
| D3 | Transakcje **cykliczne i zaplanowane rezerwują budżet** | Bez tego budżet ostrzega po fakcie. `recurring_service.get_recurring_preview(user_token, year, month)` już istnieje i liczy projekcje po stronie serwera |
| D4 | Budżet jest **świadomy podziałów** transakcji | W budżecie dokładność per kategoria JEST produktem. Świadomie różnimy się tu od Raportów, które liczą po kategorii rodzica |
| D5 | Sugestie **zastępują** „skopiuj z poprzedniego miesiąca" | Kopiowanie ręczne to friction, kopiowanie raz = plan się starzeje |
| D6 | Sugestie **per kategoria** (klikalna podpowiedź przy polu), nie „zastosuj wszystkie" | Hurtowe zatwierdzanie zachęca do bezmyślności, a w budżecie myślenie jest wartością |
| D7 | Podstawą sugestii jest **mediana**, nie średnia | Wydatki domowe są skośne. Transport `400, 380, 420, 3200, 390, 410` → średnia 866 (limit, którego nikt nie ustawi), mediana 405 (twój normalny miesiąc) |
| D8 | Sugestia pokazuje też **zakres min–max** | Mediana chowa fakt, że naprawa auta się powtórzy. Zakres przywraca tę informację bez psucia propozycji |
| D9 | Kategorie typu `transfer` **nie podlegają planowaniu** | Przelew między własnymi kontami nie jest ani przychodem, ani wydatkiem |
| D10 | Nowa zakładka na górnym pasku, własna nawigacja miesiącem | — |
| D11 | Sugestie formułowane jako **fakt o przeszłości**, nie porada | Regulamin (#63) mówi, że aplikacja nie zastępuje doradcy. „Tyle wydawałeś: mediana 405 zł" zamiast „Powinieneś wydawać 405 zł". Nic nie kosztuje, jest uczciwsze i bardziej użyteczne |

---

## 3. Rzeczy do rozstrzygnięcia PRZED pisaniem kodu

### R1. Znak i niepełność podziałów — **blokujące**

Ustalone przy analizie kodu, wymaga decyzji:

- Podziały zapisywane są **kwotami dodatnimi** (`renderSplitRows()`: `min="0"`;
  `saveSplitModal()` porównuje do `Math.abs(tx.amount)`), podczas gdy transakcja-rodzic
  ma znak (wydatek ujemny). Przy liczeniu trzeba **nałożyć znak rodzica na podział**.
- Walidacja dopuszcza podział **niepełny**: sprawdza tylko `totalSplit > abs(tx.amount)`.
  Czyli transakcja 300 zł może mieć podziały na 200 zł, a 100 zł zostaje nieprzypisane.

**Propozycja:** kwota podziału dziedziczy znak rodzica, a **reszta (`abs(rodzic) − suma
podziałów`) zostaje na kategorii rodzica**. Dzięki temu suma po wszystkich kategoriach
zawsze równa się sumie transakcji — niezmiennik, który da się przetestować i który chroni
przed cichym gubieniem pieniędzy w raporcie.

Do potwierdzenia przed implementacją.

### R2. Jakość historycznych kategorii

Historia sięga kilku lat, ale część pochodzi z importów wyciągów z autokategoryzacją.
Jeśli stare transakcje mają kategorie przypisane byle jak, sugestie będą śmieciem.

**Do zrobienia jako krok 0** (zapytanie diagnostyczne, nie kod produkcyjny): ile miesięcy
danych ma **każda kategoria z osobna** i ile transakcji w miesiącu jest bez kategorii.
Kategoria założona 2 miesiące temu ma 2 miesiące danych, niezależnie od tego, że baza ma
3 lata — dlatego próg liczy się per kategoria, nie globalnie.

---

## 4. Silnik sugestii

### Progi uczciwości

| Historia danej kategorii | Co aplikacja mówi |
|---|---|
| < 3 miesiące | Nic. Wprost: „za mało danych, ustaw ręcznie" |
| 3–11 miesięcy | Mediana z dostępnych miesięcy + zakres min–max |
| 12–23 miesiące | To samo **plus osobno**: „ten sam miesiąc rok temu: X zł" |
| 24+ miesiące | Dopiero tu rozmowa o sezonowości ma sens statystyczny |

**Dlaczego nie sezonowość od razu:** po roku danych masz dokładnie **jedną obserwację na
każdy miesiąc kalendarzowy**. Jeden grudzień to nie wzorzec, to anegdota. Do stwierdzenia
„grudzień jest u ciebie systematycznie droższy" trzeba 2–3 lat. Dochodzi dryf cen —
porównanie do grudnia sprzed dwóch lat bez korekty o inflację jest mylące, a aplikacja
inflacji nie zna i nie powinna jej zgadywać.

Dlatego w progu 12+ dwie liczby pokazujemy **osobno, obok siebie**, nigdy zmieszane w jedną.
Człowiek zobaczy „mediana 400, ale rok temu w grudniu 900" i wyciągnie wniosek lepiej niż
dowolny wzór, który dałoby się dziś napisać.

### Konsekwencja architektoniczna

Sugestia pochodzi z **nazwanej, wymiennej strategii**, która zwraca nie tylko liczbę, ale
i **wyjaśnienie, na jakiej podstawie** powstała. Wtedy dołożenie sezonowości za dwa lata
to nowa strategia — bez dotykania UI ani kontraktu API.

```python
{
    'kwota': Decimal('405.00'),
    'podstawa': 'mediana z 6 miesięcy',
    'zakres_min': Decimal('380.00'),
    'zakres_max': Decimal('3200.00'),
    'liczba_miesiecy': 6,
    'rok_temu': Decimal('900.00'),   # None poniżej progu 12 miesięcy
}
```

Nie budujemy dziś mechanizmu sezonowości — **nie da się go przetestować**, bo nie ma danych,
na których wyszedłby prawdziwy wynik.

---

## 5. Kroki implementacji

Konwencja z `CLAUDE.md`: każdy krok ma jawne kryterium weryfikacji. TDD: RED → GREEN.

```
0. Diagnostyka danych (R2) → weryfikacja: wiem, ile kategorii ma >= 3 miesiące historii
   i ile transakcji jest bez kategorii; jeśli wynik jest zły, wracam z tym do rozmowy

1. Migracja: unikalny indeks (user_token, year, month, category_id) na budgets
   → weryfikacja: flask db migrate generuje TYLKO ten indeks (bez dryfu), upgrade czysto,
     flask db check zielony (bramka CI w jakosc.yml)
   Uwaga: tabela budgets jest pusta (nigdy nie używana), więc indeks nie ma czego naruszyć

2. app/services/budget_plan_service.py  (NAZWA: nie budget_service.py — ta jest zajęta
   przez CRUD transakcji i parsery wyciągów; kolizja nazw byłaby myląca)

   - wykonanie_per_kategoria(user_token, year, month)
       Sumy świadome podziałów (D4, R1). Kształt zapytania:
         część 1: transakcje BEZ podziałów        → po t.category_id, SUM(t.amount)
         część 2: podziały                        → po s.category_id, SUM(znak * s.amount)
         część 3: reszta niepodzielona            → po t.category_id
       złożone UNION ALL i zagregowane po category_id
   - rezerwacje_per_kategoria(user_token, year, month)
       Cykliczne (get_recurring_preview) + zaplanowane, tylko daty >= dziś
   - lista_budzetu(user_token, year, month)
       Wiersze per kategoria (plan, wykonane, zarezerwowane) + agregat
       {planowane_przychody, planowane_wydatki, bilans_planu}
   - ustaw_plan / usun_plan  — tylko income/expense, nie transfer (D9)
   - zaproponuj_plan(user_token, year, month, kategoria_id, strategia='mediana')

   → weryfikacja (testy PRZED implementacją, tests/test_budget_plan.py):
     * transakcja z podziałami liczy się do kategorii podziałów, nie rodzica
     * podział niepełny: reszta zostaje na kategorii rodzica; SUMA po wszystkich
       kategoriach == suma transakcji (niezmiennik z R1)
     * kategoria transferowa odrzucona przy ustawianiu planu
     * cykliczna z datą w przyszłości podnosi „zarezerwowane", nie „wykonane"
     * cykliczna z datą przeszłą NIE jest liczona podwójnie (raz jako projekcja,
       raz jako wykonana transakcja) — to najgroźniejszy błąd w tym module
     * bilans_planu ujemny gdy plan wydatków > plan przychodów (D2)
     * mediana, nie średnia (D7): dane 400,380,420,3200,390,410 → 405
     * poniżej 3 miesięcy historii sugestia = brak, z powodem

3. app/blueprints/budget_bp.py
   GET    /api/budgets/<year>/<month>
   PUT    /api/budgets/<year>/<month>/<category_id>
   DELETE /api/budgets/<year>/<month>/<category_id>
   GET    /api/budgets/<year>/<month>/<category_id>/sugestia
   rejestracja w app/__init__.py
   → weryfikacja: testy IDOR w tests/test_authorization.py wzorem #26 — cudza kategoria
     i cudzy plan nie mogą być odczytane ani zmienione

4. Front: zakładka Budżet (app/static/js/20_budget.js) + sekcja w base.html + skrypt
   - tabela: kategoria | plan | wykonane | zarezerwowane | pasek | %
   - pasek dwusegmentowy: wykonane (pełny kolor) + zarezerwowane (kreskowany)
   - pionowa kreska „tu powinieneś być" = dzień miesiąca / liczba dni (patrz niżej)
   - kierunek paska zależny od typu: dla wydatku przekroczenie planu = czerwone,
     dla przychodu osiągnięcie planu = zielone (to dobra wiadomość)
   - nagłówek: Planowane przychody / Planowane wydatki / Bilans planu, czerwony baner
     gdy bilans ujemny (D2)
   - przy każdym polu planu klikalna podpowiedź z sugestią (D6) z opisem podstawy (D11)
   → weryfikacja: testy vitest (wzorzec tests/js/reports.test.js) na kierunku paska
     i wykrywaniu przekroczenia; test pilnujący, że użyte id istnieją w base.html;
     ręczny przebieg w przeglądarce

5. Dokumentacja: CLAUDE.md (nowa sekcja + liczba modułów JS), README (funkcja
   z „Planowane" do „Zrealizowane"), docs/DOCUMENTATION.md
   → weryfikacja: opis zgadza się z tym, co faktycznie powstało
```

### Uwaga do kroku 4: kreska „tu powinieneś być"

Wydane 200 z 1500 to 13% — zielono. Ale czy dobrze, zależy, czy jest 3., czy 28. dzień
miesiąca. Bez odniesienia do upływu czasu pasek postępu jest ozdobą, nie informacją.
Kreska liniowa jest przybliżeniem (czynsz idzie 10. jednym strzałem, nie po 1/30 dziennie),
ale wraz z segmentem „zarezerwowane" z D3 daje obraz wystarczająco uczciwy.

---

## 6. Dług, który ten PR świadomie zostawia

- **Trzecia implementacja nawigacji po miesiącach** (Transakcje mają `viewDate`, Raporty
  presety zakresu, Budżet dostanie swoją). Nie blokuje, ale dług się nawarstwia.
- **Raporty pozostają nieświadome podziałów** — po tej zmianie Budżet i Raporty policzą
  kategorie różnie dla transakcji rozbitych. Świadome (D4), ale trzeba to udokumentować
  w CLAUDE.md, żeby nie wyglądało na błąd.
- **Brak rolloveru** niewykorzystanej kwoty, brak projektów wielomiesięcznych, brak
  planowania na kilka miesięcy w przód. Pytania z #96 zostają otwarte — łatwiej je
  rozstrzygnąć po miesiącu używania najprostszej wersji niż przed.

---

## 7. Od czego zacząć jutro

1. Krok 0 (diagnostyka danych) — zapytanie SQL, wynik do rozmowy.
2. Potwierdzić R1 (znak i reszta przy podziałach niepełnych).
3. Dopiero potem migracja i testy serwisu (RED).
