// --- KOMUNIKAT O ZMIANIE DOKUMENTÓW PRAWNYCH ---
// Serwer w /api/init (`legal_notice`) mówi, czy baner ma się pokazać: data zmiany
// dokumentów jest nowsza niż ta, którą użytkownik potwierdził. Front tylko wyświetla.

function czyPokazacKomunikatPrawny(notice) {
    return !!(notice && notice.show);
}

function renderKomunikatPrawny(notice) {
    const el = document.getElementById('legal-notice');
    if (!el) return;
    const data = document.getElementById('legal-notice-date');
    if (data && notice && notice.updated) data.textContent = notice.updated;
    el.classList.toggle('hidden', !czyPokazacKomunikatPrawny(notice));
}

async function potwierdzKomunikatPrawny() {
    try {
        const response = await fetch('/api/legal-ack', { method: 'POST' });
        if (!response.ok) {
            showToast('Nie udało się zapisać potwierdzenia.', 'error');
            return;
        }
        renderKomunikatPrawny({ show: false });
    } catch (error) {
        console.error('Błąd zapisu potwierdzenia dokumentów:', error);
        showToast('Nie udało się zapisać potwierdzenia.', 'error');
    }
}
