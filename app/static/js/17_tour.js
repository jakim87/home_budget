// --- SAMOUCZEK ---
// Treść edytowana przez /samouczek — patrz .claude/skills/samouczek/SKILL.md
// Formuła: akcja → efekt. Selektory wyłącznie po ID.

const TOURS = {
    dashboard: [
        {
            el: '#dashboard-net-worth-card',
            akcja: 'Spójrz na Majątek netto',
            efekt: 'To suma sald wszystkich aktywnych kont, a obok porównanie z końcem poprzedniego miesiąca i tego samego miesiąca rok temu. Dashboard zawsze liczy wszystkie konta — „Widok konta” w nagłówku go nie zawęża.',
        },
        {
            el: '#networth-view-typy',
            akcja: 'Kliknij „Wg typu kont”',
            efekt: 'Wykres rozłoży majątek na warstwy: rachunki, oszczędności, inwestycje, a kredyty i karty pod zerem. Linia na wierzchu to majątek netto — dlatego biegnie niżej niż szczyt warstw o kwotę zobowiązań.',
        },
        {
            el: '#networth-history-chart',
            akcja: 'Kliknij wybrany miesiąc na wykresie',
            efekt: 'Sekcja „Udział majątku wg typu kont” pokaże stan z końca tego miesiąca, a pod wykresem pojawią się przyciski „Pokaż transakcje” i „Szczegółowy raport” dla tego miesiąca.',
        },
        {
            el: '#dash-cat-btn',
            akcja: 'Wybierz kategorie z listy',
            efekt: 'Wykres przychodów i wydatków policzy tylko zaznaczone kategorie, tak samo jak zakładka Raporty — przelewy między własnymi kontami nigdy się tu nie liczą. Bez zaznaczenia widać wszystkie przychody i wydatki.',
        },
    ],

    transactions: [
        {
            el: '#tx-desc',
            akcja: 'Wpisz transakcję jedną linią, np. „Biedronka 85,60 wczoraj”',
            efekt: 'Aplikacja rozpozna kontrahenta z jego kategorią, kwotę i datę i wpisze je w pola poniżej — Tab dokańcza podpowiedź. „@” zmienia konto, a „>” robi przelew na własne konto, który pojawi się też na koncie docelowym.',
        },
        {
            el: '#submit-btn',
            akcja: 'Naciśnij Enter albo kliknij „Zapisz”',
            efekt: 'Saldo konta zmieni się od razu — w odróżnieniu od wyciągu z banku, który najpierw czeka w poczekalni zakładki Import. Linia obok przycisku mówi, co dokładnie się zapisze; po zapisie komunikat przez chwilę pozwala to „Cofnij”.',
        },
        {
            // Nagłówek kolumny, nie całe <tbody>: podświetlenie listy obejmowało całą
            // tabelę, więc użytkownik i tak musiał sam szukać, o które ikony chodzi.
            el: '#th-tx-actions',
            akcja: 'Skorzystaj z ikon w kolumnie „Akcje”',
            efekt: 'Edycja działa w miejscu, bez przeładowania. Usunięcie jest trwałe — aplikacja nie ma kosza ani archiwum, więc pomyłkę poprawia się, wpisując operację ponownie.',
        },
        {
            el: '#openRecurringModalBtn',
            akcja: 'Kliknij „Transakcje cykliczne”',
            efekt: 'Otworzy się okno z harmonogramami i operacjami zaplanowanymi na przyszłość. Powtarzalną płatność szybciej jednak założysz z gotowego wpisu: wejdź w edycję jego wiersza, a obok „Zapisz” pojawi się ikona cyklu, która przeniesie kwotę, kategorię, kontrahenta i dzień miesiąca do formularza.',
        },
    ],

    // Zakładka Import. Pierwszy krok istnieje tylko w trybie demo, filtry tylko przy
    // niepustej poczekalni — silnik pominie kroki wskazujące niewidoczne elementy.
    staging: [
        {
            el: '#demo-sample-statement',
            akcja: 'Pobierz przykładowy wyciąg',
            efekt: 'Gotowy plik w formacie ING, żeby wypróbować import bez własnego wyciągu z banku. Plik nie ma numeru rachunku, więc przed wgraniem wskaż w „Ustawieniach ręcznych” konto „Konto osobiste”.',
        },
        {
            el: '#import-dropzone',
            akcja: 'Przeciągnij tu wyciągi ze wszystkich swoich kont naraz',
            efekt: 'Bank rozpozna się po zawartości pliku, a konto po numerze rachunku z wyciągu; o plik bez numeru (Revolut, wyciąg ING z jednym kontem) aplikacja zapyta na liście wyników. Operacje wszystkich kont trafią do poczekalni poniżej, pogrupowane po kontach — salda jeszcze się nie zmienią.',
        },
        {
            // Filtr zamiast nagłówka sekcji przelewów: nagłówek buduje JS, a selektory
            // samouczka muszą istnieć w base.html (weryfikacja w /samouczek).
            el: '#sf-transfer',
            akcja: 'Sprawdź przelewy między swoimi kontami',
            efekt: 'Każdy przelew to jeden wiersz „skąd → dokąd”, a kolumna „Druga strona” mówi, czy saldo drugiego konta też się zmieni — czerwone „Brak” znaczy, że trzeba zaimportować jego wyciąg. Gdy aplikacja wzięła zwykłą operację za przelew, kliknij przy niej „To nie przelew”.',
        },
        {
            el: '#sf-duplicate',
            akcja: 'Kliknij filtr „Możliwe duplikaty”',
            efekt: 'Zostaną operacje, dla których na tym samym koncie jest już wpis o tej samej kwocie w oknie ±4 dni; „Porównaj z historią” pokaże go obok, bez wychodzenia z importu. „Zatwierdź gotowe” pominie je, dopóki nie rozstrzygniesz.',
        },
        {
            el: '#approve-all-btn',
            akcja: 'Kliknij „Zatwierdź gotowe”',
            efekt: 'Dopiero teraz operacje trafiają do historii i zmieniają salda kont. Wiersze do uzupełnienia i możliwe duplikaty czekają dalej w poczekalni.',
        },
    ],

    summary: [
        {
            el: '#filter-month',
            akcja: 'Wybierz miesiąc',
            efekt: 'Wszystkie liczby poniżej przeliczą się dla tego okresu — przychody, wydatki, bilans i rozbicie na kategorie.',
        },
        {
            el: '#filter-start',
            akcja: 'Albo podaj własny zakres dat',
            efekt: 'Nadpisuje wybór miesiąca. Przydaje się do okresów rozliczeniowych, które nie pokrywają się z kalendarzem.',
        },
        {
            el: '#summary-total',
            akcja: 'Sprawdź bilans okresu',
            efekt: 'Różnica między przychodami a wydatkami. Wartość ujemna oznacza, że w tym okresie wydałeś więcej, niż wpłynęło.',
        },
        {
            el: '#dashboard-toggle-yearly',
            akcja: 'Kliknij „Rocznie"',
            efekt: 'Wykres poniżej przełączy się z ujęcia miesięcznego na roczne — trend niezależny od wybranego wyżej okresu.',
        },
        {
            el: '#summary-category-list',
            akcja: 'Przejrzyj rozbicie na kategorie',
            efekt: 'Pokazuje, gdzie faktycznie poszły pieniądze. Operacje bez kategorii lądują osobno — to sygnał, że warto uzupełnić regułę kontrahenta.',
        },
    ],

    categories: [
        {
            el: '#dict-btn-categories',
            akcja: 'Otwórz „Kategorie"',
            efekt: 'Zobaczysz swoje kategorie razem z systemowymi. Systemowych nie da się usunąć — są wspólne dla całej aplikacji i pilnują spójności raportów.',
        },
        {
            el: '#dict-btn-contractors',
            akcja: 'Przejdź do „Kontrahenci"',
            efekt: 'W polu reguł dopasowania wpisujesz fragmenty tekstu wyszukiwane w opisie operacji przy imporcie. Trafiony fragment sam ustawia kontrahenta i jego kategorię — im lepsze reguły, tym mniej pracy w poczekalni.',
        },
        {
            el: '#dict-btn-accounts',
            akcja: 'Przejdź do „Konta"',
            efekt: 'Numer rachunku jest tu sprawdzany pod kątem poprawności i służy do automatycznego rozpoznania konta przy wgrywaniu wyciągu. Konta się nie usuwa, tylko zamyka — historia zostaje, ale konto znika z list wyboru i z majątku netto.',
        },
    ],

    budget: [
        {
            el: '#budget-month-display',
            akcja: 'Wybierz miesiąc',
            efekt: 'Plan ustawiasz osobno na każdy miesiąc. Strzałki przenoszą też w przyszłość — budżet na kolejny miesiąc możesz ułożyć, zanim się zacznie.',
        },
        {
            el: '#budget-rows',
            akcja: 'Wpisz kwotę planu przy kategorii',
            efekt: 'Puste pole znaczy „bez planu". Pod polem podpowiedź mówi, ile wydawałeś do tej pory — mediana, nie średnia, żeby jedna droga naprawa nie zawyżyła całości. Kliknięcie w podpowiedź wstawia tę kwotę.',
        },
        {
            el: '#budget-balance',
            akcja: 'Sprawdź bilans planu',
            efekt: 'Różnica między planem przychodów a planem wydatków. Ujemny jest dozwolony — aplikacja o nim mówi, ale niczego nie blokuje.',
        },
        {
            el: '#budget-planned-expense',
            akcja: 'Zerknij na kolumnę „Zarezerwowane"',
            efekt: 'To transakcje cykliczne i zaplanowane, które jeszcze się nie wykonały. Zajmują budżet z góry, więc przekroczenie widać, zanim pieniądze wyjdą z konta.',
        },
    ],

    reports: [
        {
            el: '#rpt-accounts-wrap',
            akcja: 'Zawęź konta, kategorie i kontrahentów',
            efekt: 'Każdy filtr działa niezależnie i łączy się z pozostałymi. Licznik przy nazwie pokazuje, ile pozycji jest aktualnie zaznaczonych.',
        },
        {
            el: '#rpt-categories-wrap',
            akcja: 'Otwórz filtr „Kategorie"',
            efekt: 'Na górze panelu jest „Ukryj transfery wewnętrzne", domyślnie włączone — przelewy między Twoimi kontami nie są ani przychodem, ani wydatkiem. Odznacz je tylko świadomie, inaczej raport zawyży obie strony.',
        },
        {
            el: '#rpt-date-from',
            akcja: 'Ustaw zakres dat raportu',
            efekt: 'Wskaźniki, oba wykresy i tabela poniżej liczą się wyłącznie z operacji mieszczących się w tym przedziale.',
        },
        {
            el: '#rpt-kpi-net',
            akcja: 'Odczytaj wynik netto',
            efekt: 'Przychody minus wydatki dla ustawionych filtrów. Obok znajdziesz liczbę operacji, z których powstał — dobry sposób, by wychwycić raport zbudowany na dwóch przypadkowych wpisach.',
        },
    ],
};

// Propozycja samouczka przy pierwszym wejściu. Model User nie ma znacznika pierwszego
// logowania, więc „nowego użytkownika" rozpoznajemy po jedynym sygnale, jaki mamy:
// zero kont i zero operacji. Odpowiedź zapamiętuje przeglądarka, żeby nie pytać dwa razy.
//
// To wciąż nie jest auto-start: użytkownik świadomie decyduje, czy wejść w tour —
// samo pytanie nie łamie zasady, że samouczek nie uruchamia się sam.
const TOUR_OFFER_KEY = 'budget.tourOffered';

window.maybeOfferTour = function() {
    if (accounts.length || transactions.length) return;

    try {
        if (localStorage.getItem(TOUR_OFFER_KEY)) return;
        // Zapis PRZED pytaniem — odmowa liczy się tak samo jak zgoda, inaczej
        // pytalibyśmy przy każdym wejściu kogoś, kto raz powiedział „nie".
        localStorage.setItem(TOUR_OFFER_KEY, '1');
    } catch (e) {
        // Przeglądarka bez dostępu do pamięci (tryb prywatny) — odpuszczamy pytanie.
        // Lepiej nie zapytać wcale niż pytać przy każdym odświeżeniu.
        return;
    }

    if (confirm(
        'Witaj! Wygląda na to, że zaczynasz — chcesz przejść krótki samouczek?\n\n' +
        'Możesz go uruchomić w dowolnym momencie przyciskiem „?" u góry strony.'
    )) {
        startTour();
    }
};

// Zakładki mają swój samouczek pod kluczem równym nazwie zakładki.
function aktywnyTour() {
    // Aktywna zakładka czytana z DOM — switchTab() nie trzyma jej w zmiennej.
    return Object.keys(TOURS).find(name => {
        const tab = document.getElementById(`tab-${name}`);
        return tab && !tab.classList.contains('tab-hidden');
    });
}

// Element bywa nieobecny na ekranie mimo poprawnego selektora: siedzi w zwiniętym
// panelu, w nieaktywnej sekcji Słowników albo jego sekcja pojawia się dopiero przy
// danych (lista poczekalni przed pierwszym importem). Krok wskazujący coś takiego
// driver.js pokazałby jako dymek zawieszony w pustce.
//
// getClientRects() zamiast offsetParent — offsetParent jest null także dla widocznych
// elementów position:fixed.
function krokWidoczny(krok) {
    const el = document.querySelector(krok.el);
    return !!el && el.getClientRects().length > 0;
}

// Instancja trwa dłużej niż wywołanie startTour(), bo samouczek zostaje otwarty aż
// do „Gotowe" albo zamknięcia. Trzymamy ją, żeby móc zamknąć poprzednią.
let aktywnyDriver = null;

// Uruchamiany wyłącznie kliknięciem „?" — samouczek startujący sam kończy dwa razy
// mniej osób niż wywołany świadomie.
function startTour() {
    const kroki = (TOURS[aktywnyTour()] || []).filter(krokWidoczny);

    // Świadomie mówimy o tym wprost zamiast pokazywać pusty samouczek: cichy brak
    // treści wygląda jak awaria przycisku „?".
    if (!kroki.length) {
        showToast('Samouczek nie ma tu teraz czego pokazać — wróć, gdy pojawią się dane.', 'info');
        return;
    }

    // Nieukończony samouczek trzyma własną nakładkę i podświetlenie. Bez zamknięcia
    // dwie instancje nakładają się na siebie: dymek pokazuje nowy krok, a podświetlony
    // zostaje element ze starego. Dzieje się to za każdym razem, gdy ktoś otworzy „?",
    // nie dojdzie do końca i kliknie „?" ponownie w innym miejscu.
    aktywnyDriver?.destroy();

    aktywnyDriver = window.driver.js.driver({
        nextBtnText: 'Dalej',
        prevBtnText: 'Wstecz',
        doneBtnText: 'Gotowe',
        // Na telefonie driver.js wyśrodkowuje element, a wtedy dymek nie mieści się ani
        // nad nim, ani pod nim i ląduje na podświetleniu. Element przy górnej krawędzi
        // zostawia dymkowi miejsce pod spodem. 20 px zapasu na obwódkę podświetlenia.
        onHighlightStarted: el => {
            if (!el || !window.matchMedia('(max-width: 639px)').matches) return;
            el.scrollIntoView({ block: 'start' });
            window.scrollBy(0, -20);
        },
        steps: kroki.map(k => ({
            element: k.el,
            popover: { title: k.akcja, description: k.efekt },
        })),
    });
    aktywnyDriver.drive();
}
