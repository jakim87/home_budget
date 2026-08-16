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
            efekt: 'Zawęża CAŁĄ aplikację do jednego konta — dashboard, historię i podsumowanie. Wróć na „Wszystkie konta", jeśli czegoś nie widzisz tam, gdzie się spodziewasz.',
        },
    ],

    transactions: [
        {
            el: '#openImportModalBtn',
            akcja: 'Kliknij „Importuj wyciąg"',
            efekt: 'Otworzy się okno wgrywania pliku CSV z banku. Wgrane operacje trafiają najpierw do poczekalni w zakładce „Do weryfikacji" — saldo konta jeszcze się nie zmienia.',
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
            el: '#transaction-list',
            akcja: 'Skorzystaj z ikon w kolumnie „Akcje"',
            efekt: 'Edycja działa w miejscu, bez przeładowania. Usunięcie nie kasuje danych na stałe — operacja trafia do archiwum i można ją stamtąd odzyskać przez 60 dni.',
        },
        {
            el: '#openRecurringModalBtn',
            akcja: 'Kliknij „Transakcje Cykliczne"',
            efekt: 'Otworzy się okno z harmonogramami i operacjami zaplanowanymi na przyszłość. Powtarzalną płatność szybciej jednak założysz z gotowego wpisu: wejdź w edycję jego wiersza, a obok „Zapisz" pojawi się ikona cyklu, która przeniesie kwotę, kategorię, kontrahenta i dzień miesiąca do formularza.',
        },
    ],

    staging: [
        {
            el: '#sf-duplicate',
            akcja: 'Kliknij filtr „Możliwy duplikat"',
            efekt: 'Zostaną same operacje, dla których na tym samym koncie istnieje już wpis o identycznej kwocie w oknie ±4 dni. Sprawdź je, zanim zatwierdzisz — to zwykle skutek dwukrotnego wgrania tego samego wyciągu.',
        },
        {
            el: '#staging-list',
            akcja: 'Popraw kategorię i kontrahenta w wierszach',
            efekt: 'Aplikacja podpowiada je automatycznie na podstawie reguł kontrahentów, ale to Twoja ostatnia okazja na korektę — po zatwierdzeniu poprawiasz już gotową operację w historii.',
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
            el: '#cont-rules',
            akcja: 'Wpisz reguły dopasowania kontrahenta',
            efekt: 'To fragmenty tekstu wyszukiwane w opisie operacji przy imporcie. Trafiony fragment automatycznie ustawia kontrahenta i jego kategorię — im lepsze reguły, tym mniej pracy w poczekalni.',
        },
        {
            el: '#acc-number',
            akcja: 'Podaj numer rachunku przy dodawaniu konta',
            efekt: 'Numer jest sprawdzany pod kątem poprawności i wyświetlany w formie zamaskowanej. Służy też do automatycznego rozpoznania konta przy wgrywaniu wyciągu.',
        },
        {
            el: '#account-list',
            akcja: 'Zamknij konto ikoną na liście',
            efekt: 'Konta się dezaktywuje, a nie usuwa — historia operacji zostaje nienaruszona, ale konto znika z list wyboru i przestaje wchodzić do majątku netto. Trafia wtedy do sekcji kont nieaktywnych pod listą.',
        },
    ],

    reports: [
        {
            el: '#rpt-accounts-wrap',
            akcja: 'Zawęź konta, kategorie i kontrahentów',
            efekt: 'Każdy filtr działa niezależnie i łączy się z pozostałymi. Licznik przy nazwie pokazuje, ile pozycji jest aktualnie zaznaczonych.',
        },
        {
            el: '#rpt-exclude-transfers',
            akcja: 'Zostaw zaznaczone „Pomiń przelewy własne"',
            efekt: 'Przelewy między Twoimi kontami nie są ani przychodem, ani wydatkiem. Odznacz tylko wtedy, gdy świadomie chcesz zobaczyć przepływy wewnętrzne — inaczej raport zawyży obie strony.',
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

// Uruchamiany wyłącznie kliknięciem „?" — samouczek startujący sam kończy dwa razy
// mniej osób niż wywołany świadomie.
function startTour() {
    // Aktywna zakładka czytana z DOM — switchTab() nie trzyma jej w zmiennej.
    const aktywna = Object.keys(TOURS).find(
        name => !document.getElementById(`tab-${name}`).classList.contains('tab-hidden')
    );

    window.driver.js.driver({
        nextBtnText: 'Dalej',
        prevBtnText: 'Wstecz',
        doneBtnText: 'Gotowe',
        steps: TOURS[aktywna].map(k => ({
            element: k.el,
            popover: { title: k.akcja, description: k.efekt },
        })),
    }).drive();
}
