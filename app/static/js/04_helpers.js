// --- FUNKCJE POMOCNICZE ---
function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// Kwota do wyświetlenia: przecinek dziesiętny i twarda spacja co trzy cyfry
// (1234.5 → "1 234,50"). Twarda, żeby kwota nie łamała się w wąskiej kolumnie.
function formatKwota(v) {
    return Number(v).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
}

// Kurs NBP: ile PLN za 1 jednostkę waluty. Z `ym` ('RRRR-MM') — kurs na koniec
// tego miesiąca, bez — najnowszy. null = brak kursu (nie zero: konto bez kursu
// ma wypaść z sumy jawnie, a nie zaniżać jej po cichu).
function kursPLN(waluta, ym) {
    if (!waluta || waluta === 'PLN') return 1;
    const najnowszy = currencies[waluta];
    if (!ym) return najnowszy ? najnowszy.rate : null;
    const kurs = monthlyRates[waluta] && monthlyRates[waluta][ym];
    if (kurs !== undefined) return kurs;
    // Miesiąc po ostatniej tabeli (transakcje z datą w przyszłości) — najnowszy kurs.
    return najnowszy && ym >= najnowszy.date.slice(0, 7) ? najnowszy.rate : null;
}

// Suma sald kont w PLN. `brak` — waluty bez kursu, których konta pominięto.
function sumaSaldPLN(konta) {
    const brak = new Set();
    const suma = konta.reduce((s, a) => {
        const kurs = kursPLN(a.currency);
        if (kurs === null) { brak.add(a.currency); return s; }
        return s + a.balance * kurs;
    }, 0);
    return { suma, brak: [...brak] };
}

function walutaKonta(id) {
    const a = accounts.find(x => x.id == id) || inactiveAccounts.find(x => x.id == id);
    return (a && a.currency) || 'PLN';
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => { if(container.contains(toast)) toast.remove(); }, 3500);
}

// Data lokalna jako YYYY-MM-DD. Nie używamy toISOString(), bo ten przelicza na UTC
// i w naszej strefie potrafi cofnąć wynik o dobę.
function toLocalISODate(d) {
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${m}-${day}`;
}

function isSameMonthAndYear(dateString, targetDateObj) {
    if (!dateString) return false;
    const [year, month] = dateString.split('-');
    return parseInt(month, 10) - 1 === targetDateObj.getMonth() && parseInt(year, 10) === targetDateObj.getFullYear();
}

async function changeMonth(offset) {
    viewDate.setMonth(viewDate.getMonth() + offset);
    await fetchRecurringPreview(viewDate.getFullYear(), viewDate.getMonth() + 1);
    renderTransactions();
    if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) {
        // Reset filtrów niestandardowych przy strzałkach
        document.getElementById('filter-month').value = '';
        document.getElementById('filter-start').value = '';
        document.getElementById('filter-end').value = '';
        renderSummary();
    }
}

