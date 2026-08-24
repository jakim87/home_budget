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
        // Kreator pierwszego konta ma pierwszeństwo przed samouczkiem: bez konta
        // nie da się dodać transakcji, więc samouczek prowadziłby przez ślepy zaułek.
        // Dwa dialogi naraz i tak by się pobiły o uwagę.
        if (pendingFirstAccount && accounts.length === 0) {
            pendingFirstAccount = false;
            showFirstAccountModal();
        } else {
            maybeOfferTour(); // Pusta aplikacja przy pierwszym wejściu -> propozycja samouczka
        }
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

// --- REJESTRACJA ---

// Ustawiane po udanej rejestracji, konsumowane w fetchInitialData(): świeże konto
// nie ma żadnego konta bankowego, więc od razu po zalogowaniu proponujemy kreator.
let pendingFirstAccount = false;

// Przełącza modal między widokiem logowania a rejestracji. Wołane z onclick w base.html.
window.showAuthView = function(view) {
    const login = document.getElementById('auth-view-login');
    const register = document.getElementById('auth-view-register');
    login.classList.toggle('hidden', view === 'register');
    register.classList.toggle('hidden', view !== 'register');

    // Czyścimy błąd z poprzedniego widoku — inaczej po przełączeniu wisi komunikat
    // dotyczący czegoś, czego użytkownik już nie widzi.
    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('register-error').classList.add('hidden');

    const pierwszePole = view === 'register' ? 'register-username' : 'login-username';
    document.getElementById(pierwszePole).focus();
};

document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('register-username').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const password2 = document.getElementById('register-password2').value;
    const errorEl = document.getElementById('register-error');

    const pokazBlad = (tekst) => {
        errorEl.textContent = tekst;
        errorEl.classList.remove('hidden');
    };
    errorEl.classList.add('hidden');

    // Zgodność haseł sprawdzamy po stronie klienta — serwer nie zna pola "powtórz".
    if (password !== password2) {
        pokazBlad('Hasła nie są takie same.');
        return;
    }
    if (password.length < 10) {
        pokazBlad('Hasło musi mieć co najmniej 10 znaków.');
        return;
    }

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        // Limit rejestracji (5/godz.) odpowiada 429 bez ciała JSON — obsługujemy osobno,
        // inaczej response.json() rzuca i użytkownik widzi "błąd połączenia".
        if (response.status === 429) {
            pokazBlad('Zbyt wiele prób rejestracji. Spróbuj ponownie za godzinę.');
            return;
        }

        const result = await response.json();
        if (!response.ok) {
            // Marshmallow zwraca obiekt {pole: [komunikaty]}, serwis — zwykły string.
            const err = result.error;
            pokazBlad(typeof err === 'string' ? err : Object.values(err || {}).flat().join(' '));
            return;
        }

        // Rejestracja nie loguje automatycznie (serwer nie zakłada sesji), więc
        // logujemy od razu tymi samymi danymi — inaczej człowiek musiałby wpisać je
        // drugi raz zaraz po założeniu konta.
        const login = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (!login.ok) {
            showAuthView('login');
            showToast('Konto założone. Zaloguj się, aby kontynuować.', 'info');
            return;
        }

        pendingFirstAccount = true;
        hideLoginModal();
        await fetchInitialData();
    } catch (error) {
        pokazBlad('Błąd połączenia z serwerem.');
    }
});

// --- KREATOR PIERWSZEGO KONTA ---

function showFirstAccountModal() {
    const modal = document.getElementById('first-account-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.getElementById('first-account-name').focus();
}

function hideFirstAccountModal() {
    const modal = document.getElementById('first-account-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

window.skipFirstAccount = function() {
    hideFirstAccountModal();
    showToast('Konto dodasz w każdej chwili w zakładce Słowniki.', 'info');
};

document.getElementById('first-account-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('first-account-name').value.trim();
    const balanceRaw = document.getElementById('first-account-balance').value;
    const errorEl = document.getElementById('first-account-error');
    errorEl.classList.add('hidden');

    if (!name) {
        errorEl.textContent = 'Podaj nazwę konta.';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const response = await fetch('/api/accounts/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, bank_name: '', is_default: true })
        });
        const result = await response.json();
        if (!response.ok) {
            const err = result.error;
            errorEl.textContent = typeof err === 'string' ? err : Object.values(err || {}).flat().join(' ');
            errorEl.classList.remove('hidden');
            return;
        }

        // Konto zawsze powstaje z saldem 0 (create_account wymusza to celowo — saldo
        // ma wynikać z transakcji). Podane saldo startowe księgujemy uzgodnieniem,
        // czyli tą samą drogą, którą użytkownik skorygowałby je później ręcznie.
        const saldo = parseFloat(balanceRaw);
        if (!isNaN(saldo) && saldo !== 0) {
            await fetch(`/api/accounts/${result.id}/reconcile`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_balance: saldo, comment: 'Saldo początkowe' })
            });
        }

        hideFirstAccountModal();
        await fetchInitialData();
        showToast(`Konto „${name}" gotowe. Możesz dodawać transakcje.`, 'success');
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

