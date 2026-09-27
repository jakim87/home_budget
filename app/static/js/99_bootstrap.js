document.getElementById('tx-date').value = new Date().toISOString().split('T')[0];
initContractorCombobox();

// Wejście z wizytówki: /login?demo=1 loguje na konto demo, /login?rejestracja=1 otwiera rejestrację.
const wejscieZWizytowki = new URLSearchParams(window.location.search);
if (wejscieZWizytowki.has('demo') || wejscieZWizytowki.has('rejestracja')) {
    history.replaceState(null, '', window.location.pathname);
}
if (wejscieZWizytowki.has('demo') && document.getElementById('demo-login-btn')) {
    // Bez równoległego fetchInitialData(): jego 401 mógłby dojść po zalogowaniu
    // i przykryć aplikację modalem. Handler logowania sam pobiera dane.
    loginAsDemo();
} else {
    fetchInitialData();
    if (wejscieZWizytowki.has('rejestracja')) {
        showLoginModal();
        showAuthView('register');
    }
}
