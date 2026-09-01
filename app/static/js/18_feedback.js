// --- ZGŁOSZENIA UWAG ---
// Formularz „Zgłoś uwagę". Treść trafia do bazy na tym serwerze i odczytuje ją
// osoba z dostępem do serwera przez `flask feedback-list` — aplikacja nie pokazuje
// zgłoszeń, nic nie idzie mailem ani do zewnętrznych usług.

function feedbackContext() {
    // Kontekst zbierany automatycznie, żeby nie wypytywać zgłaszającego „a gdzie
    // to było". Nazwa zakładki brana z widocznej etykiety, a nie z identyfikatora —
    // zgłoszenie czyta człowiek, więc ma tam stać „Do weryfikacji", nie „staging".
    const zakladka = document.querySelector('.tab-active')?.textContent
        .replace(/\s+/g, ' ').trim() || 'nieznana';
    const wersja = document.getElementById('openFeedbackBtn')?.dataset.appVersion || '?';
    return `zakładka: ${zakladka} · wersja: ${wersja}`.slice(0, 120);
}

window.openFeedbackModal = function() {
    const modal = document.getElementById('feedback-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.getElementById('feedback-error').classList.add('hidden');
    document.getElementById('feedback-content').focus();
};

window.closeFeedbackModal = function() {
    const modal = document.getElementById('feedback-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
};

document.getElementById('feedback-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const pole = document.getElementById('feedback-content');
    const przycisk = document.getElementById('feedback-submit');
    const errorEl = document.getElementById('feedback-error');
    const pokazBlad = (tekst) => {
        errorEl.textContent = tekst;
        errorEl.classList.remove('hidden');
    };
    errorEl.classList.add('hidden');

    // Blokada na czas żądania: bez tego podwójne kliknięcie zapisuje dwa zgłoszenia.
    przycisk.disabled = true;
    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: pole.value, context: feedbackContext() })
        });

        // Limit (10/godz.) odpowiada 429 bez ciała JSON — obsługujemy osobno, inaczej
        // response.json() rzuca i użytkownik widzi mylące „błąd połączenia".
        if (response.status === 429) {
            pokazBlad('Zbyt wiele zgłoszeń w krótkim czasie. Spróbuj ponownie za godzinę.');
            return;
        }

        const result = await response.json();
        if (!response.ok) {
            // Marshmallow zwraca {pole: [komunikaty]}, serwis — zwykły string.
            const err = result.error;
            pokazBlad(typeof err === 'string' ? err : Object.values(err || {}).flat().join(' '));
            return;
        }

        pole.value = '';
        closeFeedbackModal();
        showToast(result.message, 'success');
    } catch (error) {
        pokazBlad('Błąd połączenia z serwerem.');
    } finally {
        przycisk.disabled = false;
    }
});
