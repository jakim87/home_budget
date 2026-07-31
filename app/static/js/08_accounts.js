// --- KONTA (SŁOWNIK) ---
function formatAccountNumber(num) {
    if (!num) return '';
    const digits = num.replace(/\D/g, '');
    const groups = [2, 4, 4, 4, 4, 4, 4];
    let result = '', i = 0;
    for (const len of groups) {
        if (i >= digits.length) break;
        result += (result ? ' ' : '') + digits.slice(i, i + len);
        i += len;
    }
    return result;
}

// Kolor plakietki typu konta — Kredyt wyróżniony (zobowiązanie), reszta neutralnie.
function accountTypeBadge(type) {
    if (!type) return '';
    const colors = {
        'ROR': 'bg-indigo-50 text-indigo-600',
        'KO': 'bg-emerald-50 text-emerald-600',
        'Kredyt': 'bg-rose-50 text-rose-600',
        'Rach. Maklerski': 'bg-violet-50 text-violet-600',
        'IKZE': 'bg-violet-50 text-violet-600',
    };
    const cls = colors[type] || 'bg-slate-100 text-slate-500';
    return `<span class="text-[10px] font-semibold px-1.5 py-0.5 rounded ${cls}">${type}</span>`;
}

function renderAccounts() {
    const list = document.getElementById('account-list');
    list.innerHTML = '';
    accounts.forEach((a, idx) => {
        const li = document.createElement('li');
        li.className = 'py-3 px-3 flex justify-between items-center group';
        li.innerHTML = `
            <div>
                <span class="font-medium text-slate-700 flex items-center gap-2">
                    ${a.name} ${a.bank_name ? `<span class="text-xs text-slate-400 font-normal">(${a.bank_name})</span>` : ''}
                    ${accountTypeBadge(a.account_type)}
                    ${a.is_default ? '<svg class="w-4 h-4 text-amber-400" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg>' : ''}
                </span>
                ${a.account_number ? `<span class="text-xs text-slate-500 block break-all font-mono mt-0.5">${formatAccountNumber(a.account_number)}</span>` : ''}
                ${(a.owner || a.co_owner) ? `<span class="text-xs text-slate-400 block mt-0.5">${[a.owner, a.co_owner].filter(Boolean).join(' / ')}</span>` : ''}
            </div>
            <div class="flex gap-1 items-center">
                <div class="flex flex-col opacity-0 group-hover:opacity-100">
                    <button onclick="moveAccount(${a.id}, -1)" ${idx === 0 ? 'disabled' : ''} class="text-slate-400 hover:text-indigo-600 disabled:opacity-30 disabled:hover:text-slate-400 p-0.5 rounded-md hover:bg-indigo-50 transition-colors" title="Przesuń wyżej">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path></svg>
                    </button>
                    <button onclick="moveAccount(${a.id}, 1)" ${idx === accounts.length - 1 ? 'disabled' : ''} class="text-slate-400 hover:text-indigo-600 disabled:opacity-30 disabled:hover:text-slate-400 p-0.5 rounded-md hover:bg-indigo-50 transition-colors" title="Przesuń niżej">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                </div>
                <button onclick="editAccount(${a.id})" class="text-slate-400 hover:text-indigo-600 p-1.5 rounded-md hover:bg-indigo-50 transition-colors opacity-0 group-hover:opacity-100" title="Edytuj konto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                </button>
                <button onclick="deleteAccount(${a.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100" title="Usuń konto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
                <button onclick="openReconcileModal(${a.id}, '${a.name}', ${a.balance})" class="text-slate-400 hover:text-green-600 p-1.5 rounded-md hover:bg-green-50 transition-colors opacity-0 group-hover:opacity-100" title="Uzgadniaj saldo">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                </button>
            </div>
        `;
        list.appendChild(li);
    });
}

// Konta nieaktywne / archiwalne (Faza 3). Konta zamknięte lub spłacone — poza
// aktywnym słownikiem, ale z zachowaną historią transakcji (wliczaną do wykresu
// Majątku). Każde ma przycisk podglądu swoich transakcji.
function renderInactiveAccounts() {
    const section = document.getElementById('inactive-accounts-section');
    const list = document.getElementById('inactive-accounts-list');
    if (!section || !list) return;
    if (!inactiveAccounts || inactiveAccounts.length === 0) {
        section.classList.add('hidden');
        list.innerHTML = '';
        return;
    }
    section.classList.remove('hidden');
    list.innerHTML = inactiveAccounts.map(a => `
        <li class="py-3 px-3 flex justify-between items-center gap-2">
            <div class="min-w-0">
                <span class="font-medium text-slate-600 flex items-center gap-2 flex-wrap">
                    ${a.name} ${a.bank_name ? `<span class="text-xs text-slate-400 font-normal">(${a.bank_name})</span>` : ''}
                    ${accountTypeBadge(a.account_type)}
                    <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">nieaktywne</span>
                </span>
                ${a.account_number ? `<span class="text-xs text-slate-400 block break-all font-mono mt-0.5">${formatAccountNumber(a.account_number)}</span>` : ''}
            </div>
            <div class="flex items-center gap-3 shrink-0">
                <span class="text-sm font-semibold ${Number(a.balance) < 0 ? 'text-rose-600' : 'text-slate-500'}">${Number(a.balance).toFixed(2)} PLN</span>
                <button onclick="viewAccountSummary(${a.id})" class="text-xs text-indigo-600 hover:text-indigo-800 hover:underline whitespace-nowrap" title="Cała historia konta w Podsumowaniu (zakres dat)">Podsumowanie →</button>
                <button onclick="viewAccountTransactions(${a.id})" class="text-xs text-indigo-600 hover:text-indigo-800 hover:underline whitespace-nowrap" title="Transakcje tego konta (miesięcznie)">Transakcje →</button>
            </div>
        </li>
    `).join('');
}

// Podgląd historii transakcji konta (także nieaktywnego): ustaw filtr na to konto
// i przełącz na zakładkę Transakcje. Zakładka jest zawężona do miesiąca (viewDate),
// a konta archiwalne mają starą historię — więc skaczemy na ich NAJNOWSZY miesiąc
// z transakcjami, żeby lista nie była pusta. Transakcje kont nieaktywnych są w
// globalnym stanie (filtr /api/init idzie po user_token, nie is_active).
window.viewAccountTransactions = function(id) {
    globalAccountFilter = id.toString();
    const globalAcc = document.getElementById('global-account-filter');
    if (globalAcc) globalAcc.value = globalAccountFilter;
    const dates = transactions.filter(t => t.account_id == id && t.date).map(t => t.date).sort();
    if (dates.length > 0) {
        const [y, m] = dates[dates.length - 1].split('-').map(Number);
        viewDate = new Date(y, m - 1, 1);
    }
    switchTab('transactions');
    renderTransactions();
};

// Cała historia konta w zakładce Podsumowanie: ustaw filtr na to konto i zakres
// dat obejmujący WSZYSTKIE jego transakcje (od pierwszej do ostatniej). Działa
// dla kont aktywnych i archiwalnych — Podsumowanie liczy z globalnego stanu.
window.viewAccountSummary = function(id) {
    globalAccountFilter = id.toString();
    const globalAcc = document.getElementById('global-account-filter');
    if (globalAcc) globalAcc.value = globalAccountFilter;
    const dates = transactions.filter(t => t.account_id == id && t.date).map(t => t.date).sort();
    document.getElementById('filter-month').value = '';
    if (dates.length > 0) {
        document.getElementById('filter-start').value = dates[0];
        document.getElementById('filter-end').value = dates[dates.length - 1];
    }
    switchTab('summary');
    renderSummary();
};

window.moveAccount = async function(id, direction) {
    const idx = accounts.findIndex(a => a.id === id);
    const newIdx = idx + direction;
    if (idx === -1 || newIdx < 0 || newIdx >= accounts.length) return;

    // Optymistyczna zmiana w UI, przed potwierdzeniem z serwera.
    [accounts[idx], accounts[newIdx]] = [accounts[newIdx], accounts[idx]];
    renderAccounts();
    updateAccountSelects();

    try {
        const response = await fetch('/api/accounts/reorder', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ordered_ids: accounts.map(a => a.id) })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || 'Nie udało się zapisać kolejności kont.');
        }
    } catch (e) {
        // Cofnij zmianę lokalnie, jeśli zapis się nie powiódł.
        [accounts[idx], accounts[newIdx]] = [accounts[newIdx], accounts[idx]];
        renderAccounts();
        updateAccountSelects();
        showToast(e.message || 'Nie udało się zapisać kolejności kont.', 'error');
    }
};

window.editAccount = function(id) {
    const a = accounts.find(acc => acc.id === id);
    if (!a) return;
    document.getElementById('acc-id').value = a.id;
    document.getElementById('acc-name').value = a.name;
    document.getElementById('acc-bank').value = a.bank_name || '';
    document.getElementById('acc-number').value = formatAccountNumber(a.account_number);
    document.getElementById('acc-type').value = a.account_type || '';
    document.getElementById('acc-owner').value = a.owner || '';
    document.getElementById('acc-co-owner').value = a.co_owner || '';
    document.getElementById('acc-default').checked = a.is_default || false;
    
    document.getElementById('acc-cancel-btn').classList.remove('hidden');
    document.getElementById('acc-submit-btn').textContent = 'Zapisz zmiany';
    document.getElementById('acc-submit-btn').classList.replace('bg-indigo-600', 'bg-blue-600');
    document.getElementById('acc-submit-btn').classList.replace('hover:bg-indigo-700', 'hover:bg-blue-700');
};

window.cancelEditAccount = function() {
    document.getElementById('account-form').reset();
    document.getElementById('acc-id').value = '';
    document.getElementById('acc-default').checked = false;
    document.getElementById('acc-cancel-btn').classList.add('hidden');
    document.getElementById('acc-submit-btn').textContent = 'Zapisz do słownika';
    document.getElementById('acc-submit-btn').classList.replace('bg-blue-600', 'bg-indigo-600');
    document.getElementById('acc-submit-btn').classList.replace('hover:bg-blue-700', 'hover:bg-indigo-700');
};

document.getElementById('acc-number').addEventListener('input', function(e) {
    const digitsOnly = e.target.value.replace(/\D/g, '').slice(0, 26);
    e.target.value = formatAccountNumber(digitsOnly);
});

document.getElementById('account-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('acc-id').value;
    const name = document.getElementById('acc-name').value.trim();
    const bank_name = document.getElementById('acc-bank').value.trim();
    const account_number = document.getElementById('acc-number').value.trim();
    const account_type = document.getElementById('acc-type').value || null;
    const owner = document.getElementById('acc-owner').value.trim() || null;
    const co_owner = document.getElementById('acc-co-owner').value.trim() || null;
    const is_default = document.getElementById('acc-default').checked;

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/accounts/${id}` : '/api/accounts';

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, bank_name, account_number, account_type, owner, co_owner, is_default })
        });
        if (response.ok) {
            const saved = await response.json();
            if (id) {
                if (is_default) accounts.forEach(a => a.is_default = false);
                const idx = accounts.findIndex(a => a.id == id);
                if (idx !== -1) accounts[idx] = saved;
                showToast('Zaktualizowano konto.');
            } else {
                if (is_default) accounts.forEach(a => a.is_default = false);
                accounts.push(saved);
                showToast('Dodano konto do słownika.');
                updateAccountSelects();
            }
            cancelEditAccount();
            renderAccounts();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisu', 'error');
        }
    } catch (e) { showToast('Błąd zapisywania konta.', 'error'); }
});

window.deleteAccount = async function(id) {
    if (!confirm('Usunąć to konto ze słownika?')) return;
    const res = await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
    if (res.ok) {
        accounts = accounts.filter(a => a.id !== id);
        renderAccounts();
        updateAccountSelects();
    }
}

// --- FLOW SPŁATY KREDYTU (Faza 2) ---
// Kredyt dochodzący do salda 0 = spłacony. Wykrywamy PRZEJŚCIE (poprzednie saldo
// != 0 -> 0) po odświeżeniu danych i proponujemy zamknięcie konta. Przejście
// łapiemy centralnie w fetchInitialData, więc działa dla każdej ścieżki zmiany
// salda (transakcja, uzgodnienie, edycja, zatwierdzenie stagingu).
function detectLoanPayoff(prevAccounts, newAccounts) {
    if (!Array.isArray(prevAccounts) || prevAccounts.length === 0) return;
    const prevById = new Map(prevAccounts.map(a => [a.id, a]));
    for (const a of newAccounts) {
        if (a.account_type !== 'Kredyt') continue;
        if (Number(a.balance) !== 0) continue;          // spłacony = saldo dokładnie 0
        const prev = prevById.get(a.id);
        if (!prev || Number(prev.balance) === 0) continue; // brak przejścia (nie nękaj)
        promptCloseLoan(a);
        break; // jeden monit naraz
    }
}

async function promptCloseLoan(account) {
    const msg = `Kredyt „${account.name}" został spłacony (saldo 0,00 PLN). Zamknąć konto?\n\n`
        + `Konto stanie się nieaktywne, ale pozostanie widoczne w historii Majątku `
        + `oraz w historii spłaconych kredytów.`;
    if (!confirm(msg)) return;
    const res = await fetch(`/api/accounts/${account.id}`, { method: 'DELETE' });
    if (res.ok) {
        showToast(`Kredyt „${account.name}" zamknięty.`);
        fetchInitialData();
    } else {
        showToast('Nie udało się zamknąć konta.', 'error');
    }
}

// --- UZGADNIANIE SALDA ---
const reconcileModal = document.getElementById('reconcile-modal');
const reconcileAccountName = document.getElementById('reconcile-account-name');
const reconcileCurrentBalance = document.getElementById('reconcile-current-balance');
const reconcileNewBalanceInput = document.getElementById('reconcile-new-balance');
const reconcileForm = document.getElementById('reconcile-form');
let currentReconcileAccountId = null;

window.openReconcileModal = function(accountId, accountName, currentBalance) {
    document.getElementById('reconcile-comment').value = '';
    if (accountId) {
        // Tryb: otwierany z karty konta — konto znane z góry
        currentReconcileAccountId = accountId;
        document.getElementById('reconcile-account-selector').classList.add('hidden');
        document.getElementById('reconcile-account-display').classList.remove('hidden');
        reconcileAccountName.innerText = accountName;
        reconcileCurrentBalance.innerText = `${currentBalance.toFixed(2)} PLN`;
        reconcileNewBalanceInput.value = currentBalance.toFixed(2);
    } else {
        // Tryb: otwierany z zakładki Transakcje — użytkownik wybiera konto
        currentReconcileAccountId = null;
        document.getElementById('reconcile-account-selector').classList.remove('hidden');
        document.getElementById('reconcile-account-display').classList.add('hidden');
        const sel = document.getElementById('reconcile-account-select');
        sel.innerHTML = '<option value="">Wybierz konto...</option>' +
            accounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)} (${a.balance.toFixed(2)} PLN)</option>`).join('');
        reconcileCurrentBalance.innerText = '—';
        reconcileNewBalanceInput.value = '';
    }
    reconcileModal.classList.remove('hidden');
    reconcileModal.classList.add('flex');
};

window.onReconcileAccountChange = function(val) {
    if (!val) {
        currentReconcileAccountId = null;
        reconcileCurrentBalance.innerText = '—';
        reconcileNewBalanceInput.value = '';
        return;
    }
    const acc = accounts.find(a => a.id == parseInt(val));
    if (acc) {
        currentReconcileAccountId = acc.id;
        reconcileCurrentBalance.innerText = `${acc.balance.toFixed(2)} PLN`;
        reconcileNewBalanceInput.value = acc.balance.toFixed(2);
    }
};

window.closeReconcileModal = function() {
    reconcileModal.classList.add('hidden');
    reconcileModal.classList.remove('flex');
    currentReconcileAccountId = null;
    reconcileForm.reset();
};

reconcileModal.addEventListener('click', (e) => {
    if (e.target === reconcileModal) closeReconcileModal();
});

reconcileForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    if (!currentReconcileAccountId) return;

    const newBalance = parseFloat(reconcileNewBalanceInput.value);
    if (isNaN(newBalance)) {
        showToast('Wprowadź prawidłową kwotę salda.', 'error');
        return;
    }

    const commentVal = document.getElementById('reconcile-comment')?.value.trim() || '';

    try {
        const response = await fetch(`/api/accounts/${currentReconcileAccountId}/reconcile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_balance: newBalance, comment: commentVal || null })
        });

        if (response.ok) {
            showToast('Saldo uzgodnione pomyślnie!');
            closeReconcileModal();
            fetchInitialData(); // Odśwież dane, aby zobaczyć nową transakcję i zaktualizowane saldo
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd podczas uzgadniania salda.', 'error');
        }
    } catch (error) {
        showToast('Błąd połączenia z API.', 'error');
    }
});

