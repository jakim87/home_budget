// --- ZAKŁADKI ---
function switchTab(tabName) {
    ['dashboard', 'transactions', 'summary', 'wnioski', 'budget', 'categories', 'staging', 'reports'].forEach(name => {
        document.getElementById(`tab-${name}`).classList.add('tab-hidden');
        const btn = document.getElementById(`btn-tab-${name}`);
        btn.classList.remove('tab-active');
        btn.classList.add('tab-inactive');
    });

    document.getElementById(`tab-${tabName}`).classList.remove('tab-hidden');
    const activeBtn = document.getElementById(`btn-tab-${tabName}`);
    activeBtn.classList.remove('tab-inactive');
    activeBtn.classList.add('tab-active');

    // Raporty korzystają z pełnej szerokości okna; pozostałe zakładki mają limit
    // (max-w-7xl — węższy nie mieści 8-kolumnowej tabeli historii operacji).
    const container = document.getElementById('main-container');
    if (tabName === 'reports') {
        container.classList.remove('max-w-7xl');
    } else {
        container.classList.add('max-w-7xl');
    }

    // Import zawsze pokazuje wszystkie konta — przełącznik „Widok konta" by tu mylił. Wnioski
    // też: konta wybiera się w filtrze widoku (decyzja 6).
    document.getElementById('global-account-filter').parentElement.classList.toggle('hidden', tabName === 'staging' || tabName === 'wnioski');

    if (panelWpisuOtwarty()) zamknijPanelWpisu();  // formularz wraca do zakładki Transakcje
    odswiezPrzyciskWpisu(tabName);

    if (tabName === 'dashboard') renderDashboard();
    if (tabName === 'summary') renderSummary();
    if (tabName === 'transactions') renderTransactions();
    if (tabName === 'staging') renderStaging();
    if (tabName === 'reports') renderReports();
    if (tabName === 'wnioski') renderWnioski();
    if (tabName === 'budget') renderBudget();
}

function switchDict(name) {
    ['categories', 'contractors', 'accounts'].forEach(d => {
        document.getElementById(`dict-panel-${d}`).classList.add('hidden');
        document.getElementById(`dict-btn-${d}`).classList.remove('dict-nav-active');
    });
    document.getElementById(`dict-panel-${name}`).classList.remove('hidden');
    document.getElementById(`dict-btn-${name}`).classList.add('dict-nav-active');
}

