// --- STAN APLIKACJI ---
let viewDate = new Date(); // Zarządza widocznym miesiącem

// Puste tablice - dane zostaną pobrane z backendu
let transactions = [];
let categories = [];
let pendingStaging = [];
let stagingFilter = 'all';
let stagingSort = { field: 'date', dir: 'desc' };
let contractors = [];
let accounts = [];
let inactiveAccounts = []; // konta zamknięte/archiwalne — poza aktywnym słownikiem, z zachowaną historią transakcji
let currencies = {};   // najnowsza tabela A NBP: { EUR: { name, rate, date } }
let monthlyRates = {}; // kurs na koniec miesiąca dla walut kont użytkownika: { EUR: { 'RRRR-MM': kurs } }

let inlineEditingTxId = null;

// Stan transakcji cyklicznych
let recurringTransactions = [];
let plannedTransactions = [];
let virtualTransactions = [];

// Stan okna rozbijania
let splitTxId = null;

// --- NOWE: GLOBALNY FILTR KONT ---
let globalAccountFilter = '';

window.changeGlobalAccount = function(val) {
    globalAccountFilter = val;
    renderTransactions();
    if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) {
        renderSummary();
    }
};

