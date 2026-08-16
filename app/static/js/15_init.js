// --- POŁĄCZENIE Z BACKENDEM (FLASK) ---
async function fetchInitialData({ skipStagingRefresh = false } = {}) {
    try {
        const response = await fetch('/api/init');
        if (!response.ok) {
            if (response.status === 401) {
                showLoginModal(); // Zamiast cichego błędu, pokaż modal logowania
                return;
            }
            // For other server errors, try to parse the error and show it.
            const errorData = await response.json().catch(() => ({ error: 'Błąd pobierania danych z serwera.' }));
            showToast(errorData.error || 'Nie udało się pobrać danych z serwera.', 'error');
            return;
        }
        const data = await response.json();
        const prevAccounts = accounts; // snapshot przed podmianą — do wykrycia spłaty kredytu (Faza 2)
        transactions = data.transactions || [];
        categories = data.categories || [];
        contractors = data.contractors || [];
        accounts = data.accounts || [];
        inactiveAccounts = data.inactive_accounts || [];

        updateCategorySelects();
        updateContractorSelects();
        updateAccountSelects();
        renderCategories();
        renderContractors();
        renderAccounts();
        renderInactiveAccounts();
        renderTransactions();
        renderDashboard();
        await fetchPlannedTransactions();
        await fetchRecurringTransactions();
        await fetchRecurringPreview(viewDate.getFullYear(), viewDate.getMonth() + 1);
        renderTransactions();
        detectLoanPayoff(prevAccounts, accounts); // Faza 2: kredyt doszedł do 0 -> zaproponuj zamknięcie
        if (!skipStagingRefresh) {
            await fetchPendingStaging(); // Po załadowaniu categories/contractors, żeby badge i dropdown były poprawne
        }
        maybeOfferTour(); // Pusta aplikacja przy pierwszym wejściu -> propozycja samouczka
    } catch (error) {
        console.error('Błąd pobierania danych z API:', error);
        showToast('Nie udało się pobrać danych z serwera.', 'error');
    }
}

// --- INICJALIZACJA APLIKACJI ---

// --- LOGIKA LOGOWANIA ---
function showLoginModal() {
    document.getElementById('login-modal').classList.remove('hidden');
    document.getElementById('login-modal').classList.add('flex');
}

function hideLoginModal() {
    document.getElementById('login-modal').classList.add('hidden');
    document.getElementById('login-modal').classList.remove('flex');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.classList.add('hidden');

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const result = await response.json();

        if (response.ok) {
            hideLoginModal();
            // Po udanym logowaniu, pobierz dane aplikacji
            await fetchInitialData();
            await fetchPendingStaging();
        } else {
            errorEl.textContent = result.error || 'Wystąpił nieznany błąd.';
            errorEl.classList.remove('hidden');
        }
    } catch (error) {
        errorEl.textContent = 'Błąd połączenia z serwerem.';
        errorEl.classList.remove('hidden');
    }
});

// --- RESET DANYCH TESTOWYCH ---
window.resetDevData = async function() {
    if (!confirm('Uwaga! Ta operacja nieodwracalnie usunie wszystkie transakcje, kategorie, kontrahentów i transakcje cykliczne. Salda kont zostaną wyzerowane.\n\nCzy na pewno chcesz kontynuować?')) return;
    try {
        const response = await fetch('/api/dev/reset', { method: 'POST' });
        if (response.ok) {
            showToast('Dane zostały wyczyszczone. Odświeżam stronę...', 'info');
            setTimeout(() => window.location.reload(), 1200);
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd podczas czyszczenia danych.', 'error');
        }
    } catch (e) {
        showToast('Błąd połączenia z serwerem.', 'error');
    }
};

