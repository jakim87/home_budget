// --- SAMOUCZEK ---
// Treść edytowana przez /samouczek — patrz .claude/skills/samouczek/SKILL.md
// Formuła: akcja → efekt. Selektory wyłącznie po ID.

const TOURS = {
    dashboard: [
        {
            el: '#dashboard-net-worth',
            akcja: 'Spójrz na Majątek netto',
            efekt: 'To suma sald wszystkich aktywnych kont. Rośnie i maleje wraz z każdą zapisaną operacją — konta zamknięte i nieaktywne nie są tu liczone.',
        },
        {
            el: '#networth-range-from',
            akcja: 'Ustaw zakres miesięcy',
            efekt: 'Wykres poniżej pokaże, jak Twój majątek zmieniał się w wybranym okresie. Przydaje się, żeby zobaczyć trend zamiast pojedynczej liczby.',
        },
        {
            el: '#dashboard-toggle-yearly',
            akcja: 'Kliknij „Rocznie"',
            efekt: 'Wykres przychodów i wydatków przełączy się z ujęcia miesięcznego na roczne. Ten sam zestaw operacji, inna skala.',
        },
        {
            el: '#global-account-filter',
            akcja: 'Wybierz konto z listy „Widok konta"',
            efekt: 'Zawęża CAŁĄ aplikację do jednego konta — dashboard, historię i podsumowanie; w historii dochodzi wtedy kolumna „Saldo po" ze stanem konta po każdej operacji. Wróć na „Wszystkie konta", jeśli czegoś nie widzisz tam, gdzie się spodziewasz.',
        },
    ],

    transactions: [
        {
            el: '#openImportModalBtn',
            akcja: 'Kliknij „Importuj wyciąg"',
            efekt: 'Otworzy się okno wgrywania wyciągu — CSV, HTML lub PDF z ING albo mBanku, rozpoznawane automatycznie po zawartości pliku. Wgrane operacje trafiają najpierw do poczekalni w zakładce „Do weryfikacji" — saldo konta jeszcze się nie zmienia.',
        },
        {
            el: '#tx-contractor-input',
            akcja: 'Zacznij wpisywać nazwę kontrahenta',
            efekt: 'Pole podpowiada istniejących kontrahentów i podstawia ich domyślną kategorię. Kontrahent nazwany „Moje konto: …" oznacza przelew własny — aplikacja utworzy wtedy lustrzaną operację na koncie docelowym.',
        },
        {
            el: '#submit-btn',
            akcja: 'Zapisz operację',
            efekt: 'Saldo wskazanego konta zmieni się natychmiast — bez etapu weryfikacji, w odróżnieniu od importu z pliku. Sprawdź konto przed zapisem, to najczęstsze źródło rozjazdu z wyciągiem.',
        },
        {
            // Nagłówek kolumny, nie całe <tbody>: podświetlenie listy obejmowało całą
            // tabelę, więc użytkownik i tak musiał sam szukać, o które ikony chodzi.
            el: '#th-tx-actions',
            akcja: 'Skorzystaj z ikon w kolumnie „Akcje"',
            efekt: 'Edycja działa w miejscu, bez przeładowania. Usunięcie nie kasuje danych na stałe — operacja trafia do archiwum i można ją stamtąd odzyskać przez 60 dni.',
        },
        {
            el: '#openRecurringModalBtn',
            akcja: 'Kliknij „Transakcje Cykliczne"',
            efekt: 'Otworzy się okno z harmonogramami i operacjami zaplanowanymi na przyszłość. Powtarzalną płatność szybciej jednak założysz z gotowego wpisu: wejdź w edycję jego wiersza, a obok „Zapisz" pojawi się ikona cyklu, która przeniesie kwotę, kategorię, kontrahenta i dzień miesiąca do formularza.',
        },
    ],

    // Okno importu. Klucz bez odpowiadającej zakładki — patrz TOUR_MODAL_KEYS.
    // Pierwszy krok istnieje tylko w trybie demo; poza nim silnik go pominie.
    import: [
        {
            el: '#demo-sample-statement',
            akcja: 'Pobierz przykładowy wyciąg',
            efekt: 'Gotowy plik w formacie ING, żeby wypróbować import bez sięgania po własny wyciąg z banku. Wgraj go poniżej i wskaż konto „Konto osobiste".',
        },
        {
            el: '#import-account-select',
            akcja: 'Zostaw konto nierozpoznane, jeśli nie wiesz',
            efekt: 'Aplikacja rozpozna je sama po numerze rachunku z wyciągu. Wybieraj ręcznie tylko, gdy plik numeru nie zawiera — wskazanie złego konta rozjeżdża salda.',
        },
        {
            el: '#csvFileInput',
            akcja: 'Wskaż pliki z historią',
            efekt: 'Naraz możesz wgrać wiele plików, także w różnych formatach — CSV, HTML i PDF z ING oraz mBanku. Bank i format są rozpoznawane po zawartości, nie po rozszerzeniu.',
        },
        {
            el: '#submitImportBtn',
            akcja: 'Uruchom import',
            efekt: 'Operacje trafią do poczekalni w zakładce „Do weryfikacji" — salda kont jeszcze się NIE zmienią. Zmieni je dopiero zatwierdzenie tam.',
        },
    ],

    // Filtry i lista pojawiają się dopiero, gdy coś czeka na zatwierdzenie —
    // przy pustej poczekalni silnik pominie te kroki i zostaną dwa skrajne.
    staging: [
        {
            el: '#staging-heading',
            akcja: 'Zajrzyj tu po każdym imporcie',
            efekt: 'Operacje z wyciągu czekają w tej poczekalni i nie ruszają jeszcze sald kont. To bufor między plikiem z banku a Twoją historią.',
        },
        {
            el: '#sf-duplicate',
            akcja: 'Kliknij filtr „Możliwy duplikat"',
            efekt: 'Zostaną same operacje, dla których na tym samym koncie istnieje już wpis o identycznej kwocie w oknie ±4 dni. Sprawdź je przed zatwierdzeniem — to zwykle skutek dwukrotnego wgrania tego samego wyciągu.',
        },
        {
            // Nagłówek tej jednej kolumny, nie całe <tbody> — podświetlenie listy
            // obejmowało cały ekran i nie wskazywało, gdzie właściwie patrzeć.
            el: '#th-stg-mapping',
            akcja: 'Popraw kategorię i kontrahenta w wierszach',
            efekt: 'Aplikacja podpowiada je z reguł dopasowania kontrahentów, ale to Twoja ostatnia okazja na korektę — po zatwierdzeniu poprawiasz już gotową operację w historii.',
        },
        {
            el: '#approve-all-btn',
            akcja: 'Zatwierdź operacje',
            efekt: 'Dopiero teraz wpisy trafiają do historii i zmieniają salda kont. To jedyny moment w całym imporcie, w którym Twoje pieniądze „się ruszają".',
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

// Zakładki mają swój samouczek pod kluczem równym nazwie zakładki; `import` to
// jedyny klucz bez zakładki — dotyczy okna importu, które przykrywa całą stronę.
const TOUR_MODAL_KEYS = { import: 'import-modal' };

function aktywnyTour() {
    const otwartyModal = Object.entries(TOUR_MODAL_KEYS).find(
        ([, modalId]) => !document.getElementById(modalId).classList.contains('hidden')
    );
    if (otwartyModal) return otwartyModal[0];

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
// getClientRects() zamiast offsetParent — offsetParent jest null także dla elementów
// position:fixed, czyli dla wszystkiego w oknach modalnych, które są przecież widoczne.
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
        steps: kroki.map(k => ({
            element: k.el,
            popover: { title: k.akcja, description: k.efekt },
        })),
    });
    aktywnyDriver.drive();
}
