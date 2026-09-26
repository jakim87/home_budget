// --- FUNKCJE POMOCNICZE ---
function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// Kwota do wyświetlenia: przecinek dziesiętny i twarda spacja co trzy cyfry
// (1234.5 → "1 234,50"). Twarda, żeby kwota nie łamała się w wąskiej kolumnie.
function formatKwota(v) {
    return Number(v).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
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

