# Skill: Tworzenie i aktualizacja samouczka w aplikacji

## Opis
Pisze i aktualizuje treść wbudowanego samouczka (`app/static/js/17_tour.js`) w formule **akcja → efekt**: każdy krok wskazuje realny element interfejsu, mówi co użytkownik ma kliknąć i co się wtedy stanie. Skill wyłącznie **autorzy treść i weryfikuje selektory** — nie przebudowuje silnika touru.

## Kiedy używać
Wywołaj przez `/samouczek [zakładka]`, gdzie zakładka to jedna z: `dashboard`, `transactions`, `staging`, `summary`, `categories`, `reports`, albo `all` (domyślnie: pyta, której zakładki dotyczy zmiana).

Typowe powody wywołania:
- doszła nowa funkcja i trzeba dopisać kroki,
- zmieniło się UI i selektory w samouczku są nieaktualne,
- pierwsze napisanie samouczka dla zakładki.

---

## Instrukcja wykonania

### Krok 1 — Ustal zakres i przeczytaj stan obecny

Przeczytaj **równolegle**:
- `app/static/js/17_tour.js` — jeśli istnieje; to jest plik do zaktualizowania, nie do nadpisania w całości
- `app/templates/base.html` — źródło prawdy dla selektorów i tego, co faktycznie jest na ekranie
- `app/static/js/06_tabs.js` — lista zakładek i co się renderuje przy przełączeniu

Pliki JS z logiką zakładki znajdź po nazwie funkcji renderującej, którą `switchTab()` woła dla tej zakładki — np. `grep -l "function renderStaging" app/static/js/*.js` — i przeczytaj też pliki, do których ta funkcja się odwołuje.

**Nie zgaduj, co robi przycisk.** Znajdź jego handler w JS i przeczytaj, co faktycznie wykonuje — samouczek, który kłamie o efekcie, jest gorszy niż jego brak.

### Krok 2 — Wybierz kroki

Reguły doboru, wynikające z danych o skuteczności samouczków:

- **3–4 kroki na zakładkę, nigdy więcej niż 5.** Trzykrokowy tour kończy 72% użytkowników, siedmiokrokowy 16%. Jeśli masz 8 kandydatów — wybierz 4 i odpuść resztę.
- **Element ukrywany warunkowo nie może być krokiem.** Jeśli w szablonie ma `class="hidden"` zdejmowaną z JS (licznik przy zakładce, sekcja pojawiająca się dopiero przy danych), tour podświetli pustkę. Wskaż element widoczny zawsze.
- **Tylko ścieżka do wartości.** Krok wchodzi do samouczka, jeśli bez niego użytkownik nie osiągnie celu zakładki. Nie opisuj każdego przycisku.
- **Priorytet dla mechaniki nieoczywistej.** Rzeczy, które użytkownik zrozumie sam (przycisk „Usuń" usuwa), pomiń. Rzeczy, które go zaskoczą, opisz zawsze:
  - saldo konta zmienia się dopiero po **zatwierdzeniu** stagingu, nie po wgraniu pliku,
  - usunięcie transakcji przenosi ją do archiwum (60 dni), nie kasuje,
  - dezaktywacja kategorii/kontrahenta to soft-delete, nie usunięcie,
  - kontrahent nazwany `Moje konto: X` tworzy lustrzaną transakcję na koncie X,
  - kategorie bez `user_token` są globalne i użytkownik ich nie usunie,
  - dane dashboardu liczą się w przeglądarce z już pobranych transakcji.
- **Kolejność = kolejność wykonywania**, nie kolejność elementów na ekranie.

### Krok 3 — Zapisz treść

Plik `app/static/js/17_tour.js`, format:

```js
// Treść samouczka. Edytowane przez /samouczek — patrz .claude/skills/samouczek/SKILL.md
const TOURS = {
    dashboard: [
        {
            el: '#net-worth-value',
            akcja: 'Spójrz na Majątek netto',
            efekt: 'To suma sald wszystkich aktywnych kont. Aktualizuje się po każdym zatwierdzonym imporcie i po ręcznym dodaniu transakcji.',
        },
    ],
};
```

Twarde reguły formatu:

- **`el` to wyłącznie selektor ID** (`#coś`). Klasy i selektory strukturalne rozjeżdżają się przy pierwszej zmianie Tailwinda. Jeśli element nie ma ID — dodaj mu ID w `base.html` (to jedyna zmiana poza plikiem samouczka, na jaką pozwala ten skill).
- **`akcja`** — tryb rozkazujący, jedno zdanie, zaczyna się od czasownika: „Kliknij…", „Wybierz…", „Wgraj…". Bez kropki na końcu.
- **`efekt`** — co się stanie i dlaczego to ma znaczenie. Maksymalnie dwa zdania. Zawsze konkret: nie „zobaczysz podsumowanie", tylko „zobaczysz sumy wydatków per kategoria za wybrany miesiąc".
- Kolejność kluczy w obiekcie zawsze: `el`, `akcja`, `efekt`.
- Polszczyzna z pełną diakrytyką, cudzysłowy drukarskie („…") w treści.

Jeśli plik już istnieje — **zmień tylko klucz z zakresu wywołania**, resztę zostaw nietkniętą.

### Krok 4 — Weryfikacja selektorów (obowiązkowa)

Każdy selektor musi istnieć w szablonie. Uruchom:

```bash
grep -oP "el:\s*'#\K[^']+" app/static/js/17_tour.js | sort -u | while read id; do
    grep -q "id=\"$id\"" app/templates/base.html || echo "BRAK W SZABLONIE: #$id"
    grep -q "id=\"$id\"[^>]*class=\"[^\"]*\bhidden\b" app/templates/base.html && echo "UKRYTY DOMYŚLNIE: #$id"
done
node --check app/static/js/17_tour.js
```

Pusty wynik (poza brakiem błędów składni) = wszystko w porządku. Każda linia to błąd do naprawienia **przed** zakończeniem:
- `BRAK W SZABLONIE` — popraw selektor albo dodaj ID do `base.html`,
- `UKRYTY DOMYŚLNIE` — wskaż inny element, ten bywa niewidoczny i tour podświetli pustkę.

Sprawdź też, czy `17_tour.js` jest podpięty w `base.html` (sekcja `<script src=...>` na końcu pliku, w kolejności numerycznej). Jeśli nie — dodaj.

### Krok 5 — Raport

Wypisz zwięźle:
1. Które zakładki zaktualizowano i ile kroków ma teraz każda.
2. Wynik weryfikacji selektorów.
3. Czy trzeba było dodać jakieś ID do `base.html` — wymień je.
4. Co świadomie pominięto w samouczku i dlaczego (żeby decyzja była zapisana, a nie zapomniana).

---

## Zasady jakości

- **Prawda ponad zwięzłość.** Efekt opisany w samouczku musi zgadzać się z tym, co robi handler. Jeśli nie masz pewności — przeczytaj kod, nie zgaduj.
- **Nie tłumacz oczywistości.** Każdy krok, który użytkownik odgadłby sam, to koszt bez zwrotu.
- **Bez żargonu implementacyjnego w treści dla użytkownika.** W `efekt` nie pojawia się „staging", „endpoint", „soft-delete" ani nazwy tabel — pisz „poczekalnia importu", „operacja trafia do archiwum".
- **Samouczek nigdy nie uruchamia się sam.** Wywołanie tylko kliknięciem („?"). Tour startujący automatycznie kończy dwukrotnie mniej osób niż uruchamiany świadomie.
- **Zero nowych zależności.** Silnik touru już jest — ten skill dokłada wyłącznie treść.
