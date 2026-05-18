// --- STAN APLIKACJI ---
let viewDate = new Date(); // Zarządza widocznym miesiącem

// Puste tablice - dane zostaną pobrane z backendu
let transactions = [];
let categories = [];
let pendingStaging = [];
let contractors = [];
let accounts = [];

let currentTxType = 'expense';
let inlineEditingTxId = null;

// Stan transakcji cyklicznych
let recurringTransactions = [];
let currentRecType = 'expense';

// Stan okna rozbijania
let splitTxId = null;

// --- IMPORT TRANSAKCJI ---
const openImportModalBtn = document.getElementById('openImportModalBtn');
const closeImportModalBtn = document.getElementById('closeImportModalBtn');
const closeImportModalBtnAlt = document.getElementById('closeImportModalBtnAlt');
const importModal = document.getElementById('import-modal');
const importForm = document.getElementById('importForm');
const fileInput = document.getElementById('csvFileInput');
const importErrorMsg = document.getElementById('importError');
const importBtnText = document.getElementById('importBtnText');
const importBtnLoader = document.getElementById('importBtnLoader');
const submitImportBtn = document.getElementById('submitImportBtn');

function openImportModal() {
    importModal.classList.remove('hidden');
    importModal.classList.add('flex');
    importErrorMsg.classList.add('hidden');
    fileInput.value = '';
}

function closeImportModal() {
    importModal.classList.add('hidden');
    importModal.classList.remove('flex');
}

openImportModalBtn.addEventListener('click', openImportModal);
closeImportModalBtn.addEventListener('click', closeImportModal);
closeImportModalBtnAlt.addEventListener('click', closeImportModal);

importModal.addEventListener('click', (e) => {
    if (e.target === importModal) closeImportModal();
});

importForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    importErrorMsg.classList.add('hidden');
    
    const accId = document.getElementById('import-account-select').value;
    if (!accId) {
        showImportError('Proszę najpierw wybrać konto z listy.');
        return;
    }

    const file = fileInput.files[0];
    if (!file) {
        showImportError('Proszę wybrać plik.');
        return;
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
        showImportError('Nieprawidłowy format. Wybrany plik musi mieć rozszerzenie .csv');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('account_id', accId);

    setImportLoadingState(true);

    try {
        const response = await fetch('/api/import/ing', { method: 'POST', body: formData });
        const result = await response.json();

        if (response.ok) {
            showToast(`Sukces! ${result.message}`, 'success');
            closeImportModal();
            fetchPendingStaging(); // Odśwież listę do weryfikacji po udanym imporcie
        } else {
            showImportError(result.error || 'Wystąpił błąd serwera podczas importu pliku.');
        }
    } catch (error) {
        showImportError('Błąd połączenia z serwerem. Sprawdź, czy aplikacja jest uruchomiona.');
    } finally {
        setImportLoadingState(false);
    }
});

function showImportError(message) {
    importErrorMsg.textContent = message;
    importErrorMsg.classList.remove('hidden');
}

function setImportLoadingState(isLoading) {
    if (isLoading) {
        submitImportBtn.disabled = true;
        submitImportBtn.classList.add('opacity-75', 'cursor-not-allowed');
        importBtnText.textContent = 'Importowanie...';
        importBtnLoader.classList.remove('hidden');
    } else {
        submitImportBtn.disabled = false;
        submitImportBtn.classList.remove('opacity-75', 'cursor-not-allowed');
        importBtnText.textContent = 'Zaimportuj';
        importBtnLoader.classList.add('hidden');
    }
}

// --- LOGIKA STAGINGU (OCZEKUJĄCYCH TRANSAKCJI) ---
async function fetchPendingStaging() {
    try {
        const response = await fetch('/api/staging/pending');
        if (!response.ok) {
            // If 401, it just means the user is not logged in yet. Don't show an error.
            // For other errors, log it. The main fetchInitialData will show a toast.
            if (response.status !== 401) {
                console.error('Błąd pobierania transakcji ze stagingu:', await response.text());
            }
            return;
        }
        pendingStaging = await response.json();
        renderStaging();
    } catch (error) {
        console.error('Błąd pobierania transakcji ze stagingu:', error);
    }
}

function renderStaging() {
    const list = document.getElementById('staging-list');
    const empty = document.getElementById('staging-empty');
    const badge = document.getElementById('staging-badge');
    
    list.innerHTML = '';
    
    if (pendingStaging.length > 0) {
        badge.innerText = pendingStaging.length;
        badge.classList.remove('hidden');
        empty.classList.add('hidden');
        list.parentElement.classList.remove('hidden');
        
        pendingStaging.forEach(t => {
            const isPositive = t.amount >= 0;
            const amountClass = isPositive ? 'text-emerald-600' : 'text-rose-600';
            const amountText = `${isPositive ? '+' : ''}${Math.abs(t.amount).toFixed(2)} PLN`;
            
            // Sprawdzenie statusu zmapowania przez system
            const isFullyMapped = t.proposed_category && t.proposed_contractor_id;
            const isPartiallyMapped = t.proposed_category || t.proposed_contractor_id;
            
            let rowBg = 'hover:bg-slate-50';
            let badgeHtml = '';
            let btnClass = 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500';
            
            if (isFullyMapped) {
                rowBg = 'bg-emerald-50/40 hover:bg-emerald-100/50';
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700 uppercase tracking-wider" title="Transakcja w pełni zmapowana">Zmapowano</span>`;
                btnClass = 'bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500';
            } else if (isPartiallyMapped) {
                rowBg = 'bg-blue-50/30 hover:bg-blue-100/50';
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700 uppercase tracking-wider" title="Znaleziono częściowe dopasowanie">Częściowo</span>`;
            }

            const row = document.createElement('tr');
            row.className = `${rowBg} transition-colors`;
            row.innerHTML = `
                <td class="p-4 border-b border-slate-100 text-sm text-slate-500 whitespace-nowrap">${t.date}</td>
                <td class="p-4 border-b border-slate-100 font-medium text-slate-800">
                    <div class="flex items-center gap-2 mb-0.5">
                        <span>${t.title}</span>
                        ${badgeHtml}
                    </div>
                    ${t.contractor ? `<div class="text-xs text-slate-500 font-normal mt-0.5">${t.contractor}</div>` : ''}
                </td>
                <td class="p-4 border-b border-slate-100">
                    <select id="staging-cont-${t.id}" onchange="updateStagingLocalState(${t.id}, 'proposed_contractor_id', this.value)" class="w-full p-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white cursor-pointer mb-2">
                        <option value="">Wybierz kontrahenta...</option>
                        ${getContractorOptionsHtml(t.proposed_contractor_id)}
                    </select>
                    <select id="staging-cat-${t.id}" onchange="updateStagingLocalState(${t.id}, 'proposed_category', this.value)" class="w-full p-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white cursor-pointer">
                        <option value="">Wybierz kategorię...</option>
                        ${getCategoryOptionsHtml(t.proposed_category)}
                    </select>
                </td>
                <td class="p-4 border-b border-slate-100 font-bold ${amountClass} text-right whitespace-nowrap">${amountText}</td>
                <td class="p-4 border-b border-slate-100 text-center">
                    <button onclick="approveStaging(${t.id})" class="px-4 py-2 ${btnClass} text-white text-sm font-medium rounded-lg transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2">
                        Zatwierdź
                    </button>
                </td>
            `;
            list.appendChild(row);
        });
    } else {
        badge.classList.add('hidden');
        empty.classList.remove('hidden');
        list.parentElement.classList.add('hidden');
    }
}

window.updateStagingLocalState = function(id, field, value) {
    const item = pendingStaging.find(t => t.id === id);
    if (item && value !== '__NEW_CATEGORY__' && value !== '__NEW_CONTRACTOR__') {
        item[field] = value;
    }
}

window.approveStaging = async function(id) {
    const catSelect = document.getElementById(`staging-cat-${id}`);
    const contSelect = document.getElementById(`staging-cont-${id}`);
    const category = catSelect.value;
    const contractor_id = contSelect.value;
    
    if (!category || !contractor_id) {
        showToast('Błąd: wybierz kontrahenta i kategorię przed zatwierdzeniem.', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/staging/${id}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: category, contractor_id: contractor_id })
        });
        
        if (response.ok) {
            showToast('Transakcja zatwierdzona!');
            // Usuń z lokalnej listy i odśwież widok stagingu
            pendingStaging = pendingStaging.filter(t => t.id !== id);
            renderStaging();
            // Odśwież główną listę transakcji (żeby zatwierdzona od razu pojawiła się w statystykach)
            fetchInitialData(); 
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zatwierdzania transakcji.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z API.', 'error');
    }
}

window.approveAllStaging = async function() {
    // Filtrujemy tylko te transakcje, które mają uzupełnionego i kontrahenta, i kategorię (tzw. "zielone")
    const mapped = pendingStaging.filter(t => t.proposed_category && t.proposed_contractor_id);
    
    if (mapped.length === 0) {
        showToast('Brak w pełni zmapowanych transakcji (posiadających kategorię i kontrahenta).', 'info');
        return;
    }
    
    if (!confirm(`Czy na pewno chcesz zatwierdzić ${mapped.length} zmapowanych transakcji?`)) return;
    
    let successCount = 0;
    // Wysyłamy prośby sekwencyjnie (błyskawiczne API Flaska to obsłuży bez zatykania bazy)
    for (const t of mapped) {
        const res = await fetch(`/api/staging/${t.id}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: t.proposed_category, contractor_id: t.proposed_contractor_id })
        });
        if (res.ok) successCount++;
    }
    
    if (successCount > 0) {
        showToast(`Pomyślnie zatwierdzono ${successCount} transakcji!`, 'success');
        fetchPendingStaging();
        fetchInitialData();
    }
}

window.clearStaging = async function() {
    if (!confirm('Czy na pewno chcesz odrzucić WSZYSTKIE oczekujące transakcje? Tej operacji nie można cofnąć.')) return;
    
    try {
        const response = await fetch('/api/staging/pending', {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(result.message, 'info');
            pendingStaging = [];
            renderStaging();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd podczas odrzucania transakcji.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z API.', 'error');
    }
}

// --- FUNKCJE POMOCNICZE ---
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => { if(container.contains(toast)) toast.remove(); }, 3500);
}

function isSameMonthAndYear(dateString, targetDateObj) {
    const d = new Date(dateString);
    return d.getMonth() === targetDateObj.getMonth() && d.getFullYear() === targetDateObj.getFullYear();
}

function changeMonth(offset) {
    viewDate.setMonth(viewDate.getMonth() + offset);
    renderTransactions();
    if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) {
        // Reset filtrów niestandardowych przy strzałkach
        document.getElementById('filter-month').value = '';
        document.getElementById('filter-start').value = '';
        document.getElementById('filter-end').value = '';
        renderSummary();
    }
}

// --- LOGIKA TRANSAKCJI CYKLICZNYCH (GENEROWANIE WIRTUALNYCH) ---
function generateVirtualTransactions(targetYear, targetMonth, startLimit, endLimit) {
    let virtualTx = [];
    
    let periodStart, periodEnd;
    if (startLimit || endLimit) {
        periodStart = startLimit ? new Date(startLimit) : new Date(2000, 0, 1);
        periodEnd = endLimit ? new Date(endLimit) : new Date(2100, 11, 31);
    } else {
        periodStart = new Date(targetYear, targetMonth, 1);
        periodEnd = new Date(targetYear, targetMonth + 1, 0);
    }

    recurringTransactions.forEach(rt => {
        const rtStart = new Date(rt.startDate);
        const rtEnd = rt.endDate ? new Date(rt.endDate) : new Date(2100, 11, 31);
        
        if (rtEnd < periodStart || rtStart > periodEnd) return;

        if (rt.freqType === 'months') {
            let curr = new Date(rtStart.getFullYear(), rtStart.getMonth(), rt.freqDay);
            while (curr <= periodEnd && curr <= rtEnd) {
                if (curr >= rtStart && curr >= periodStart) virtualTx.push(createVirtualTxObject(rt, curr));
                curr.setMonth(curr.getMonth() + parseInt(rt.freqMonthsVal));
            }
        } else if (rt.freqType === 'days') {
            let curr = new Date(rtStart);
            while (curr <= periodEnd && curr <= rtEnd) {
                if (curr >= periodStart) virtualTx.push(createVirtualTxObject(rt, curr));
                curr.setDate(curr.getDate() + parseInt(rt.freqDaysVal));
            }
        } else if (rt.freqType === 'specific_days') {
            let currMonthStart = new Date(Math.max(rtStart, periodStart));
            currMonthStart.setDate(1);
            
            while (currMonthStart <= periodEnd && currMonthStart <= rtEnd) {
                rt.freqSpecificDays.forEach(day => {
                    let curr = new Date(currMonthStart.getFullYear(), currMonthStart.getMonth(), day);
                    if (curr >= rtStart && curr >= periodStart && curr <= periodEnd && curr <= rtEnd && curr.getMonth() === currMonthStart.getMonth()) {
                        virtualTx.push(createVirtualTxObject(rt, curr));
                    }
                });
                currMonthStart.setMonth(currMonthStart.getMonth() + 1);
            }
        }
    });
    return virtualTx;
}

function createVirtualTxObject(rt, dateObj) {
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const d = String(dateObj.getDate()).padStart(2, '0');
    return {
        id: `virt-${rt.id}-${y}${m}${d}`,
        date: `${y}-${m}-${d}`,
        desc: `${rt.desc}`,
        amount: rt.amount,
        category: rt.category,
        isVirtual: true,
        virtualSourceId: rt.id
    };
}

function getFullTransactionsList(monthFilter, startFilter, endFilter) {
    let year, month;
    if (monthFilter) {
        [year, month] = monthFilter.split('-');
        year = parseInt(year);
        month = parseInt(month) - 1;
    } else {
        year = viewDate.getFullYear();
        month = viewDate.getMonth();
    }
    const virtuals = generateVirtualTransactions(year, month, startFilter, endFilter);
    return [...transactions, ...virtuals];
}

// --- OKNO TRANSAKCJI CYKLICZNYCH ---
window.openRecurringModal = function() {
    updateCategorySelects();
    document.getElementById('rec-start-date').value = new Date().toISOString().split('T')[0];
    renderRecurringList();
    document.getElementById('recurring-modal').classList.remove('hidden');
    document.getElementById('recurring-modal').classList.add('flex');
};

window.closeRecurringModal = function() {
    document.getElementById('recurring-modal').classList.add('hidden');
    document.getElementById('recurring-modal').classList.remove('flex');
    document.getElementById('recurring-form').reset();
    document.getElementById('rec-start-date').value = new Date().toISOString().split('T')[0];
    toggleRecEndDate();
    toggleRecFreqInputs();
};

window.setRecType = function(type) {
    currentRecType = type;
    const btnExp = document.getElementById('rec-type-expense');
    const btnInc = document.getElementById('rec-type-income');
    if (type === 'expense') {
        btnExp.className = 'flex-1 px-4 py-2 rounded-md bg-rose-100 text-rose-700 font-medium text-sm transition-colors shadow-sm';
        btnInc.className = 'flex-1 px-4 py-2 rounded-md text-slate-500 hover:bg-slate-100 font-medium text-sm transition-colors';
    } else {
        btnInc.className = 'flex-1 px-4 py-2 rounded-md bg-emerald-100 text-emerald-700 font-medium text-sm transition-colors shadow-sm';
        btnExp.className = 'flex-1 px-4 py-2 rounded-md text-slate-500 hover:bg-slate-100 font-medium text-sm transition-colors';
    }
};

window.toggleRecEndDate = function() {
    const isIndefinite = document.getElementById('rec-indefinite').checked;
    document.getElementById('rec-end-date').disabled = isIndefinite;
    if (isIndefinite) document.getElementById('rec-end-date').value = '';
};

window.toggleRecFreqInputs = function() {
    const type = document.getElementById('rec-freq-type').value;
    document.getElementById('rec-opts-months').classList.toggle('hidden', type !== 'months');
    document.getElementById('rec-opts-months').classList.toggle('flex', type === 'months');
    document.getElementById('rec-opts-days').classList.toggle('hidden', type !== 'days');
    document.getElementById('rec-opts-days').classList.toggle('flex', type === 'days');
    document.getElementById('rec-opts-specific').classList.toggle('hidden', type !== 'specific_days');
    document.getElementById('rec-opts-specific').classList.toggle('flex', type === 'specific_days');
};

window.deleteRecurring = function(id) {
    recurringTransactions = recurringTransactions.filter(t => t.id !== id);
    renderRecurringList();
    renderTransactions(); 
    if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) renderSummary();
    showToast('Cykl usunięty.', 'info');
};

function renderRecurringList() {
    const list = document.getElementById('recurring-list');
    const empty = document.getElementById('recurring-empty');
    list.innerHTML = '';
    
    if (recurringTransactions.length === 0) {
        empty.classList.remove('hidden');
        list.parentElement.classList.add('hidden');
    } else {
        empty.classList.add('hidden');
        list.parentElement.classList.remove('hidden');

        recurringTransactions.forEach(rt => {
            const isExp = rt.amount < 0;
            let freqText = '';
            if (rt.freqType === 'months') freqText = `Co ${rt.freqMonthsVal} mies. (dz: ${rt.freqDay})`;
            else if (rt.freqType === 'days') freqText = `Co ${rt.freqDaysVal} dni`;
            else if (rt.freqType === 'specific_days') freqText = `Dni: ${rt.freqSpecificDays.join(', ')}`;
            const endText = rt.endDate ? `Do ${rt.endDate}` : 'Bezterminowo';

            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50 transition-colors group';
            row.innerHTML = `
                <td class="p-3 border-b border-slate-100">
                    <div class="font-medium text-slate-800">${rt.desc}</div>
                    <div class="text-xs text-slate-500">${rt.category}</div>
                </td>
                <td class="p-3 border-b border-slate-100 text-sm">
                    <div class="text-indigo-600 font-medium">${freqText}</div>
                    <div class="text-xs text-slate-500">Od ${rt.startDate} | ${endText}</div>
                </td>
                <td class="p-3 border-b border-slate-100 font-bold text-right ${isExp ? 'text-rose-600' : 'text-emerald-600'}">
                    ${isExp ? '-' : '+'}${Math.abs(rt.amount).toFixed(2)} PLN
                </td>
                <td class="p-3 border-b border-slate-100 text-center">
                    <button onclick="deleteRecurring(${rt.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100" title="Usuń cykl">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            `;
            list.appendChild(row);
        });
    }
}

document.getElementById('recurring-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const desc = document.getElementById('rec-desc').value.trim();
    const rawAmount = parseFloat(document.getElementById('rec-amount').value);
    const category = document.getElementById('rec-category').value;
    const startDate = document.getElementById('rec-start-date').value;
    const isIndefinite = document.getElementById('rec-indefinite').checked;
    const endDate = isIndefinite ? null : document.getElementById('rec-end-date').value;

    if (!desc || isNaN(rawAmount) || rawAmount <= 0 || !startDate) {
        showToast('Wypełnij poprawnie wszystkie pola.', 'error'); return;
    }
    if (!isIndefinite && !endDate) {
        showToast('Podaj datę zakończenia.', 'error'); return;
    }
    if (!isIndefinite && new Date(startDate) > new Date(endDate)) {
        showToast('Data zakończenia nie może być wcześniejsza niż rozpoczęcia.', 'error'); return;
    }

    const freqType = document.getElementById('rec-freq-type').value;
    let freqMonthsVal, freqDay, freqDaysVal, freqSpecificDays;

    if (freqType === 'months') {
        freqMonthsVal = parseInt(document.getElementById('rec-freq-months-val').value);
        freqDay = parseInt(document.getElementById('rec-freq-months-day').value);
    } else if (freqType === 'days') {
        freqDaysVal = parseInt(document.getElementById('rec-freq-days-val').value);
    } else if (freqType === 'specific_days') {
        const rawDays = document.getElementById('rec-freq-specific-val').value;
        freqSpecificDays = rawDays.split(',').map(d => parseInt(d.trim())).filter(d => !isNaN(d) && d >= 1 && d <= 31);
        if (freqSpecificDays.length === 0) {
            showToast('Podaj poprawne dni miesiąca (np. 1, 15).', 'error'); return;
        }
    }

    const finalAmount = currentRecType === 'expense' ? -Math.abs(rawAmount) : Math.abs(rawAmount);

    recurringTransactions.push({
        id: Date.now(), desc, amount: finalAmount, category, startDate, endDate,
        freqType, freqMonthsVal, freqDay, freqDaysVal, freqSpecificDays
    });
    
    showToast('Transakcja cykliczna została dodana.', 'success');
    document.getElementById('recurring-form').reset();
    document.getElementById('rec-start-date').value = startDate;
    toggleRecEndDate(); toggleRecFreqInputs();
    renderRecurringList();
    renderTransactions(); 
    if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) renderSummary();
});

// --- ZAKŁADKI ---
function switchTab(tabName) {
    ['transactions', 'summary', 'categories', 'staging'].forEach(name => {
        document.getElementById(`tab-${name}`).classList.add('tab-hidden');
        const btn = document.getElementById(`btn-tab-${name}`);
        btn.classList.remove('tab-active');
        btn.classList.add('tab-inactive');
    });
    
    document.getElementById(`tab-${tabName}`).classList.remove('tab-hidden');
    const activeBtn = document.getElementById(`btn-tab-${tabName}`);
    activeBtn.classList.remove('tab-inactive');
    activeBtn.classList.add('tab-active');

    if (tabName === 'summary') renderSummary();
    if (tabName === 'transactions') renderTransactions();
    if (tabName === 'staging') renderStaging();
}

// --- KATEGORIE ---
function getCategoryOptionsHtml(selectedValue = null) {
    const expCategories = categories.filter(c => c.type === 'expense');
    const incCategories = categories.filter(c => c.type === 'income');
    
    let html = `<optgroup label="Wydatki">`;
    expCategories.forEach(c => {
        const sel = c.name === selectedValue ? 'selected' : '';
        html += `<option value="${c.name}" ${sel}>${c.name}</option>`;
    });
    html += `</optgroup><optgroup label="Przychody">`;
    incCategories.forEach(c => {
        const sel = c.name === selectedValue ? 'selected' : '';
        html += `<option value="${c.name}" ${sel}>${c.name}</option>`;
    });
    html += `</optgroup>`;
    html += `<option value="__NEW_CATEGORY__" class="font-bold text-blue-600">➕ Dodaj nową kategorię...</option>`;
    return html;
}

function getContractorOptionsHtml(selectedId = null) {
    let html = '';
    contractors.forEach(c => {
        const sel = (c.id == selectedId) ? 'selected' : '';
        html += `<option value="${c.id}" ${sel}>${c.name}</option>`;
    });
    html += `<option value="__NEW_CONTRACTOR__" class="font-bold text-blue-600">➕ Dodaj nowego kontrahenta...</option>`;
    return html;
}

function updateCategorySelects() {
    const formSelect = document.getElementById('tx-category');
    const recSelect = document.getElementById('rec-category');
    const contCatSelect = document.getElementById('cont-cat');
    
    const currentFormVal = formSelect.value;
    formSelect.innerHTML = getCategoryOptionsHtml(currentFormVal);

    if(recSelect) recSelect.innerHTML = getCategoryOptionsHtml();
    if(contCatSelect) {
        const currentContCat = contCatSelect.value;
        contCatSelect.innerHTML = `<option value="">Brak domyślnej kategorii</option>` + getCategoryOptionsHtml(currentContCat);
    }
    
    renderTransactions(); // Refresh inline selects
}

function updateContractorSelects() {
    const txCont = document.getElementById('tx-contractor');
    if(txCont) {
        const curr = txCont.value;
        txCont.innerHTML = `<option value="">Brak kontrahenta</option>` + getContractorOptionsHtml(curr);
    }
    renderTransactions();
}

function updateAccountSelects() {
    let html = '<option value="">Wybierz konto...</option>';
    accounts.forEach(a => html += `<option value="${a.id}">${a.name} ${a.bank_name ? `(${a.bank_name})` : ''}</option>`);
    
    const txAcc = document.getElementById('tx-account');
    if (txAcc) txAcc.innerHTML = html;
    
    const impAcc = document.getElementById('import-account-select');
    if (impAcc) impAcc.innerHTML = html;
}

function renderCategories() {
    const list = document.getElementById('category-list');
    list.innerHTML = '';
    
    categories.forEach(c => {
        const isUsed = transactions.some(t => t.category === c.name || (t.splits && t.splits.some(s => s.category === c.name)));
        const typeLabel = c.type === 'expense' ? '<span class="text-rose-500 bg-rose-50 px-2 py-0.5 rounded text-xs font-medium">Wydatek</span>' : '<span class="text-emerald-500 bg-emerald-50 px-2 py-0.5 rounded text-xs font-medium">Przychód</span>';
        
        const li = document.createElement('li');
        li.className = 'py-3 px-3 flex justify-between items-center group';
        li.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="font-medium text-slate-700">${c.name}</span>
                ${typeLabel}
            </div>
            <button onclick="deleteCategory('${c.name}')" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100 ${isUsed ? 'hidden' : ''}" title="Usuń kategorię">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            </button>
            ${isUsed ? '<span class="text-xs text-slate-400 italic">W użyciu</span>' : ''}
        `;
        list.appendChild(li);
    });
}

document.getElementById('category-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const nameInput = document.getElementById('cat-name');
    const typeInput = document.getElementById('cat-type');
    const name = nameInput.value.trim();
    const type = typeInput.value;
    
    if (name && !categories.find(c => c.name.toLowerCase() === name.toLowerCase())) {
        try {
            const response = await fetch('/api/categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, type: type })
            });
            
            if (response.ok) {
                const savedCat = await response.json();
                categories.push({ name: savedCat.name, type: savedCat.type });
                nameInput.value = '';
                renderCategories();
                updateCategorySelects();
                showToast(`Dodano kategorię: ${name}`);
            } else {
                const err = await response.json();
                showToast(err.error || 'Błąd zapisu na serwerze.', 'error');
            }
        } catch (error) {
            console.error(error);
            showToast('Błąd połączenia z serwerem.', 'error');
        }
    } else {
        showToast('Kategoria o tej nazwie już istnieje!', 'error');
    }
});

window.deleteCategory = async function(name) {
    if (!confirm(`Czy na pewno chcesz usunąć kategorię: ${name}?`)) return;
    
    try {
        const response = await fetch(`/api/categories/${encodeURIComponent(name)}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            categories = categories.filter(c => c.name !== name);
            renderCategories();
            updateCategorySelects();
            showToast(`Usunięto kategorię: ${name}`, 'info');
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisu na serwerze.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem API.', 'error');
    }
}

// --- KONTA (SŁOWNIK) ---
function renderAccounts() {
    const list = document.getElementById('account-list');
    list.innerHTML = '';
    accounts.forEach(a => {
        const li = document.createElement('li');
        li.className = 'py-3 px-3 flex justify-between items-center group';
        li.innerHTML = `
            <div>
                <span class="font-medium text-slate-700 block">${a.name} ${a.bank_name ? `<span class="text-xs text-slate-400 font-normal ml-1">(${a.bank_name})</span>` : ''}</span>
                ${a.account_number ? `<span class="text-xs text-slate-500 block break-all font-mono mt-0.5">${a.account_number}</span>` : ''}
            </div>
            <div class="flex gap-1">
                <button onclick="editAccount(${a.id})" class="text-slate-400 hover:text-indigo-600 p-1.5 rounded-md hover:bg-indigo-50 transition-colors opacity-0 group-hover:opacity-100" title="Edytuj konto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                </button>
                <button onclick="deleteAccount(${a.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100" title="Usuń konto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
        `;
        list.appendChild(li);
    });
}

window.editAccount = function(id) {
    const a = accounts.find(acc => acc.id === id);
    if (!a) return;
    document.getElementById('acc-id').value = a.id;
    document.getElementById('acc-name').value = a.name;
    document.getElementById('acc-bank').value = a.bank_name || '';
    document.getElementById('acc-number').value = a.account_number || '';
    
    document.getElementById('acc-cancel-btn').classList.remove('hidden');
    document.getElementById('acc-submit-btn').textContent = 'Zapisz zmiany';
    document.getElementById('acc-submit-btn').classList.replace('bg-indigo-600', 'bg-blue-600');
    document.getElementById('acc-submit-btn').classList.replace('hover:bg-indigo-700', 'hover:bg-blue-700');
};

window.cancelEditAccount = function() {
    document.getElementById('account-form').reset();
    document.getElementById('acc-id').value = '';
    document.getElementById('acc-cancel-btn').classList.add('hidden');
    document.getElementById('acc-submit-btn').textContent = 'Zapisz do słownika';
    document.getElementById('acc-submit-btn').classList.replace('bg-blue-600', 'bg-indigo-600');
    document.getElementById('acc-submit-btn').classList.replace('hover:bg-blue-700', 'hover:bg-indigo-700');
};

document.getElementById('account-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('acc-id').value;
    const name = document.getElementById('acc-name').value.trim();
    const bank_name = document.getElementById('acc-bank').value.trim();
    const account_number = document.getElementById('acc-number').value.trim();
    
    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/accounts/${id}` : '/api/accounts';

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, bank_name, account_number })
        });
        if (response.ok) {
            const saved = await response.json();
            if (id) {
                const idx = accounts.findIndex(a => a.id == id);
                if (idx !== -1) accounts[idx] = saved;
                showToast('Zaktualizowano konto.');
            } else {
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

// --- SZYBKIE DODAWANIE W LOCIE ---
let currentQuickAddSelect = null;

document.addEventListener('change', function(e) {
    if (e.target && e.target.tagName === 'SELECT') {
        if (e.target.value === '__NEW_CATEGORY__') {
            currentQuickAddSelect = e.target;
            openQuickCategoryModal();
        } else if (e.target.value === '__NEW_CONTRACTOR__') {
            currentQuickAddSelect = e.target;
            openQuickContractorModal();
        }
    }
});

window.openQuickCategoryModal = function() {
    document.getElementById('quick-cat-name').value = '';
    document.getElementById('quick-category-modal').classList.remove('hidden');
    document.getElementById('quick-category-modal').classList.add('flex');
};

window.closeQuickCategoryModal = function() {
    document.getElementById('quick-category-modal').classList.add('hidden');
    document.getElementById('quick-category-modal').classList.remove('flex');
    if (currentQuickAddSelect && currentQuickAddSelect.value === '__NEW_CATEGORY__') {
        currentQuickAddSelect.value = '';
    }
    currentQuickAddSelect = null;
};

window.openQuickContractorModal = function() {
    document.getElementById('quick-cont-name-inp').value = '';
    document.getElementById('quick-cont-rules-inp').value = '';
    
    const qCatSelect = document.getElementById('quick-cont-cat-select');
    let catHtml = `<option value="">Brak domyślnej kategorii</option>`;
    categories.filter(c=>c.type==='expense').forEach(c => catHtml += `<option value="${c.name}">${c.name}</option>`);
    categories.filter(c=>c.type==='income').forEach(c => catHtml += `<option value="${c.name}">${c.name}</option>`);
    qCatSelect.innerHTML = catHtml;

    document.getElementById('quick-contractor-modal').classList.remove('hidden');
    document.getElementById('quick-contractor-modal').classList.add('flex');
};

window.closeQuickContractorModal = function() {
    document.getElementById('quick-contractor-modal').classList.add('hidden');
    document.getElementById('quick-contractor-modal').classList.remove('flex');
    if (currentQuickAddSelect && currentQuickAddSelect.value === '__NEW_CONTRACTOR__') {
        currentQuickAddSelect.value = '';
    }
    currentQuickAddSelect = null;
};

document.getElementById('quick-category-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const name = document.getElementById('quick-cat-name').value.trim();
    const type = document.getElementById('quick-cat-type').value;

    try {
        const response = await fetch('/api/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, type })
        });
        if (response.ok) {
            const saved = await response.json();
            categories.push(saved);
            
            const selectId = currentQuickAddSelect ? currentQuickAddSelect.id : null;
            if (selectId && selectId.startsWith('staging-cat-')) {
                const stgId = parseInt(selectId.replace('staging-cat-', ''));
                updateStagingLocalState(stgId, 'proposed_category', saved.name);
            }

            updateCategorySelects();
            renderCategories();
            renderStaging();

            if (selectId) {
                const el = document.getElementById(selectId);
                if (el) el.value = saved.name;
            }
            
            closeQuickCategoryModal();
            showToast(`Dodano kategorię: ${name}`);
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisu', 'error');
        }
    } catch(e) { showToast('Błąd połączenia', 'error'); }
});

document.getElementById('quick-contractor-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const name = document.getElementById('quick-cont-name-inp').value.trim();
    const rules = document.getElementById('quick-cont-rules-inp').value.trim();
    const category = document.getElementById('quick-cont-cat-select').value;

    try {
        const response = await fetch('/api/contractors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, rules, category })
        });
        if (response.ok) {
            const saved = await response.json();
            contractors.push(saved);
            
            const selectId = currentQuickAddSelect ? currentQuickAddSelect.id : null;
            if (selectId && selectId.startsWith('staging-cont-')) {
                const stgId = parseInt(selectId.replace('staging-cont-', ''));
                updateStagingLocalState(stgId, 'proposed_contractor_id', saved.id);
            }

            updateContractorSelects();
            renderContractors();
            renderStaging();

            if (selectId) {
                const el = document.getElementById(selectId);
                if (el) el.value = saved.id;
            }
            
            closeQuickContractorModal();
            showToast(`Dodano kontrahenta: ${name}`);
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisu', 'error');
        }
    } catch(e) { showToast('Błąd połączenia', 'error'); }
});

// --- KONTRAHENCI (SŁOWNIK) ---
function renderContractors() {
    const list = document.getElementById('contractor-list');
    list.innerHTML = '';
    contractors.forEach(c => {
        const li = document.createElement('li');
        li.className = 'py-3 px-3 flex justify-between items-center group';
        li.innerHTML = `
            <div>
                <span class="font-medium text-slate-700 block">${c.name}</span>
                <span class="text-xs text-slate-400 block break-all">Reguły: ${c.rules || '-'}</span>
            </div>
            <div class="flex gap-1">
                <button onclick="editContractor(${c.id})" class="text-slate-400 hover:text-blue-600 p-1.5 rounded-md hover:bg-blue-50 transition-colors opacity-0 group-hover:opacity-100" title="Edytuj kontrahenta">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                </button>
                <button onclick="deleteContractor(${c.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100" title="Usuń kontrahenta">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
        `;
        list.appendChild(li);
    });
}

window.editContractor = function(id) {
    const c = contractors.find(cont => cont.id === id);
    if (!c) return;
    document.getElementById('cont-id').value = c.id;
    document.getElementById('cont-name').value = c.name;
    document.getElementById('cont-rules').value = c.rules || '';
    document.getElementById('cont-cat').value = c.default_category_name || '';
    
    document.getElementById('cont-cancel-btn').classList.remove('hidden');
    document.getElementById('cont-submit-btn').textContent = 'Zapisz zmiany';
    document.getElementById('cont-submit-btn').classList.replace('bg-emerald-600', 'bg-blue-600');
    document.getElementById('cont-submit-btn').classList.replace('hover:bg-emerald-700', 'hover:bg-blue-700');
};

window.cancelEditContractor = function() {
    document.getElementById('contractor-form').reset();
    document.getElementById('cont-id').value = '';
    document.getElementById('cont-cancel-btn').classList.add('hidden');
    document.getElementById('cont-submit-btn').textContent = 'Zapisz do słownika';
    document.getElementById('cont-submit-btn').classList.replace('bg-blue-600', 'bg-emerald-600');
    document.getElementById('cont-submit-btn').classList.replace('hover:bg-blue-700', 'hover:bg-emerald-700');
};

document.getElementById('contractor-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('cont-id').value;
    const name = document.getElementById('cont-name').value.trim();
    const rules = document.getElementById('cont-rules').value.trim();
    const category = document.getElementById('cont-cat').value;
    
    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/contractors/${id}` : '/api/contractors';

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, rules, category })
        });
        if (response.ok) {
            const saved = await response.json();
            if (id) {
                const idx = contractors.findIndex(c => c.id == id);
                if (idx !== -1) contractors[idx] = saved;
                showToast('Zaktualizowano kontrahenta.');
            } else {
                contractors.push(saved);
                showToast('Dodano kontrahenta do słownika.');
            }
            cancelEditContractor();
            renderContractors();
            updateContractorSelects();
        }
    } catch (e) { showToast('Błąd zapisywania kontrahenta.', 'error'); }
});

window.deleteContractor = async function(id) {
    if (!confirm('Usunąć tego kontrahenta?')) return;
    const res = await fetch(`/api/contractors/${id}`, { method: 'DELETE' });
    if (res.ok) {
        contractors = contractors.filter(c => c.id !== id);
        renderContractors();
        updateContractorSelects();
    }
}

// --- AUTO-UZUPEŁNIANIE NA PODSTAWIE OPISU ---
window.handleAutoFill = function(textValue, contSelectEl, catSelectEl) {
    if (!textValue || textValue.length < 2) return;
    const text = textValue.toLowerCase();

    for (const c of contractors) {
        let matchFound = false;
        
        // Sprawdź dokładną nazwę (minimum 3 znaki, żeby uniknąć losowych trafień)
        if (c.name && c.name.length >= 3 && text.includes(c.name.toLowerCase())) {
            matchFound = true;
        }
        
        // Sprawdź przypisane słowa kluczowe
        if (!matchFound && c.rules) {
            const rules = c.rules.split(',').map(r => r.trim().toLowerCase()).filter(r => r.length >= 2);
            for (const rule of rules) {
                if (text.includes(rule)) {
                    matchFound = true;
                    break;
                }
            }
        }

        if (matchFound) {
            if (contSelectEl && contSelectEl.value != c.id) {
                contSelectEl.value = c.id;
            }
            if (catSelectEl && c.default_category_name && catSelectEl.value !== c.default_category_name) {
                catSelectEl.value = c.default_category_name;
            }
            return; // Zatrzymujemy szukanie na pierwszym dopasowaniu
        }
    }
}

// --- TRANSAKCJE ---
function toggleTxType(type) {
    currentTxType = type;
    const btnExpense = document.getElementById('type-expense');
    const btnIncome = document.getElementById('type-income');
    
    if (type === 'expense') {
        btnExpense.className = 'flex-1 px-4 py-2 rounded-md bg-rose-100 text-rose-700 font-medium text-sm transition-colors shadow-sm';
        btnIncome.className = 'flex-1 px-4 py-2 rounded-md text-slate-500 hover:bg-slate-100 font-medium text-sm transition-colors';
    } else {
        btnIncome.className = 'flex-1 px-4 py-2 rounded-md bg-emerald-100 text-emerald-700 font-medium text-sm transition-colors shadow-sm';
        btnExpense.className = 'flex-1 px-4 py-2 rounded-md text-slate-500 hover:bg-slate-100 font-medium text-sm transition-colors';
    }
}

// Podpięcie Auto-uzupełniania do głównych formularzy
document.getElementById('tx-desc').addEventListener('input', function(e) {
    handleAutoFill(e.target.value, document.getElementById('tx-contractor'), document.getElementById('tx-category'));
});

const recDesc = document.getElementById('rec-desc');
if (recDesc) {
    recDesc.addEventListener('input', function(e) {
        handleAutoFill(e.target.value, null, document.getElementById('rec-category'));
    });
}

document.getElementById('transaction-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const dateInput = document.getElementById('tx-date').value;
    const descInput = document.getElementById('tx-desc').value.trim();
    const rawAmount = parseFloat(document.getElementById('tx-amount').value);
    const categoryInput = document.getElementById('tx-category').value;
    const contractorInput = document.getElementById('tx-contractor').value;
    const accountInput = document.getElementById('tx-account').value;

    if (!dateInput || !descInput || isNaN(rawAmount) || rawAmount <= 0) {
        showToast('Wypełnij poprawnie wszystkie pola.', 'error');
        return;
    }
    if (!accountInput) {
        showToast('Proszę najpierw wybrać konto.', 'error');
        return;
    }

    const finalAmount = currentTxType === 'expense' ? -Math.abs(rawAmount) : Math.abs(rawAmount);

    const txData = {
        date: dateInput,
        desc: descInput,
        amount: finalAmount,
        category: categoryInput,
        contractor_id: contractorInput ? parseInt(contractorInput) : null,
        account_id: parseInt(accountInput)
    };

    try {
        const response = await fetch('/api/transactions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(txData)
        });
        
        if (response.ok) {
            const savedTx = await response.json();
            // Bezpiecznie używamy timestampu jako mock ID, dopóki baza go nie nada
            savedTx.id = savedTx.id || Date.now(); 
            transactions.push(savedTx);
            
            document.getElementById('tx-desc').value = '';
            document.getElementById('tx-amount').value = '';
            document.getElementById('tx-contractor').value = '';
            
            showToast('Transakcja została zapisana pomyślnie.');
            renderTransactions();
        } else {
            showToast('Błąd serwera podczas zapisywania transakcji.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem.', 'error');
    }
});

function startInlineEdit(id) {
    inlineEditingTxId = id;
    renderTransactions();
}

function cancelInlineEdit() {
    inlineEditingTxId = null;
    renderTransactions();
}

function saveInlineEdit(id) {
    const dateVal = document.getElementById(`edit-date-${id}`).value;
    const descVal = document.getElementById(`edit-desc-${id}`).value.trim();
    const rawAmount = parseFloat(document.getElementById(`edit-amount-${id}`).value);
    const categoryVal = document.getElementById(`edit-cat-${id}`).value;
    const contractorVal = document.getElementById(`edit-cont-${id}`).value;
    const isIncome = document.getElementById(`edit-type-${id}`).value === 'income';

    if (!dateVal || !descVal || isNaN(rawAmount) || rawAmount <= 0) {
        showToast('Wypełnij poprawnie wszystkie pola edycji.', 'error');
        return;
    }

    const tx = transactions.find(t => t.id === id);
    if (tx) {
        tx.date = dateVal;
        tx.desc = descVal;
        tx.amount = isIncome ? Math.abs(rawAmount) : -Math.abs(rawAmount);
        tx.category = categoryVal;
        tx.contractor_id = contractorVal ? parseInt(contractorVal) : null;
        
        // Usunięcie podziałów, bo zmieniono dane główne (uproszczenie logiki dla użytkownika)
        if (tx.splits) delete tx.splits; 
        
        showToast('Zmiany zostały zapisane.');
    }
    inlineEditingTxId = null;
    renderTransactions();
}

function renderTransactions() {
    const list = document.getElementById('transaction-list');
    const emptyState = document.getElementById('empty-state');
    list.innerHTML = '';
    
    // Pobierz transakcje z aktualnego miesiąca (zwykłe + cykliczne)
    const allTx = getFullTransactionsList(null, null, null); 
    const filtered = allTx.filter(t => isSameMonthAndYear(t.date, viewDate));
    filtered.sort((a, b) => {
        const dateDiff = new Date(b.date) - new Date(a.date);
        if (dateDiff !== 0) return dateDiff;
        // W przypadku tej samej daty, ułóż nowe pozycje (o wyższym ID) na samej górze
        const idA = typeof a.id === 'number' ? a.id : 0;
        const idB = typeof b.id === 'number' ? b.id : 0;
        return idB - idA;
    });

    // Nazwa miesiąca w nagłówku
    const monthNames = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"];
    document.getElementById('current-month-display').innerText = `${monthNames[viewDate.getMonth()]} ${viewDate.getFullYear()}`;

    if (filtered.length === 0) {
        emptyState.classList.remove('hidden');
        list.parentElement.classList.add('hidden');
    } else {
        emptyState.classList.add('hidden');
        list.parentElement.classList.remove('hidden');

        filtered.forEach(t => {
            const isSplit = t.splits && t.splits.length > 0;
            const row = document.createElement('tr');
            
            if (inlineEditingTxId === t.id && !t.isVirtual) {
                // TRYB EDYCJI
                const isExp = t.amount < 0;
                row.className = 'bg-blue-50/50';
                row.innerHTML = `
                    <td class="p-2 border-b border-blue-100">
                        <input type="date" id="edit-date-${t.id}" value="${t.date}" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        <input type="text" id="edit-desc-${t.id}" value="${t.desc}" oninput="handleAutoFill(this.value, document.getElementById('edit-cont-${t.id}'), document.getElementById('edit-cat-${t.id}'))" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        <select id="edit-cont-${t.id}" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                            <option value="">Brak kontrahenta</option>
                            ${getContractorOptionsHtml(t.contractor_id)}
                        </select>
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        ${isSplit ? 
                            `<span class="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded">Edycja podziału w oknie</span>
                             <input type="hidden" id="edit-cat-${t.id}" value="${t.category}">` 
                            : 
                            `<select id="edit-cat-${t.id}" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                                ${getCategoryOptionsHtml(t.category)}
                            </select>`
                        }
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        <div class="flex gap-1 mb-1">
                            <select id="edit-type-${t.id}" class="w-1/2 p-1.5 border border-blue-300 rounded outline-none text-xs bg-white">
                                <option value="expense" ${isExp ? 'selected' : ''}>Wyd.</option>
                                <option value="income" ${!isExp ? 'selected' : ''}>Przych.</option>
                            </select>
                            <input type="number" id="edit-amount-${t.id}" value="${Math.abs(t.amount).toFixed(2)}" step="0.01" min="0.01" ${isSplit ? 'readonly title="Kwota wynika z podziału"' : ''} class="w-1/2 p-1.5 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white ${isSplit ? 'bg-slate-100 text-slate-500' : ''}">
                        </div>
                    </td>
                    <td class="p-2 border-b border-blue-100 text-center">
                        <div class="flex justify-center items-center gap-1">
                            <button onclick="saveInlineEdit(${t.id})" title="Zapisz" class="p-1.5 text-emerald-600 hover:bg-emerald-100 rounded-md transition-colors bg-white border border-emerald-200">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                            </button>
                            <button onclick="cancelInlineEdit()" title="Anuluj" class="p-1.5 text-slate-500 hover:bg-slate-200 rounded-md transition-colors bg-white border border-slate-200">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                            </button>
                        </div>
                    </td>
                `;
            } else {
                // TRYB WIDOKU
                const isPositive = t.amount >= 0;
                const amountClass = isPositive ? 'text-emerald-600' : 'text-rose-600';
                const amountText = `${isPositive ? '+' : ''}${Math.abs(t.amount).toFixed(2)} PLN`;
                
                const isVirtual = t.isVirtual;
                const iconHtml = isVirtual 
                    ? `<svg class="w-4 h-4 text-indigo-500 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Transakcja zaplanowana (cykliczna)"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>`
                    : ``;
                
                row.className = `transition-colors group hover:bg-slate-50 ${isVirtual ? 'bg-indigo-50/30' : ''}`;
                row.innerHTML = `
                    <td class="p-4 border-b border-slate-100 text-sm text-slate-500 whitespace-nowrap">${t.date}</td>
                    <td class="p-4 border-b border-slate-100 font-medium text-slate-800">${iconHtml}${t.desc}</td>
                    <td class="p-4 border-b border-slate-100 text-slate-600 text-sm">
                        ${t.contractor_name || t.contractor || '-'}
                    </td>
                    <td class="p-4 border-b border-slate-100 text-slate-600 text-sm">
                        ${isSplit ? 
                            '<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-600 font-medium text-xs border border-indigo-100" title="Transakcja rozbita na pozycje"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg> Sprawdź szczegóły</span>' 
                            : 
                            t.category
                        }
                    </td>
                    <td class="p-4 border-b border-slate-100 font-bold ${amountClass} text-right whitespace-nowrap">${amountText}</td>
                    <td class="p-4 border-b border-slate-100 text-center">
                        ${isVirtual ? `
                            <span class="text-xs font-semibold text-indigo-500 bg-indigo-100 px-2 py-1 rounded-md inline-block">Zaplanowana</span>
                        ` : `
                        <div class="flex justify-center items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onclick="startInlineEdit(${t.id})" title="Edytuj" class="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors focus:outline-none">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                            </button>
                            <button onclick="openSplitModal(${t.id})" title="${isSplit ? 'Edytuj podział' : 'Rozbij transakcję'}" class="p-1.5 ${isSplit ? 'text-indigo-600 bg-indigo-50' : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'} rounded-md transition-colors focus:outline-none">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path></svg>
                            </button>
                            <button onclick="deleteTransaction(${t.id})" title="Usuń" class="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors focus:outline-none">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            </button>
                        </div>
                        `}
                    </td>
                `;
            }
            list.appendChild(row);
        });
    }
}

window.deleteTransaction = async function(id) {
    if (!confirm('Czy na pewno chcesz usunąć tę transakcję?')) return;
    
    try {
        const response = await fetch(`/api/transactions/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            transactions = transactions.filter(t => t.id !== id);
            renderTransactions();
            if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) renderSummary();
            showToast('Transakcja usunięta.', 'info');
        } else {
            showToast('Błąd podczas usuwania transakcji na serwerze.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem API.', 'error');
    }
}

// --- ROZBIJANIE TRANSAKCJI ---
let currentSplits = [];
let originalAmount = 0;

window.openSplitModal = function(id) {
    const tx = transactions.find(t => t.id === id);
    if (!tx) return;
    
    splitTxId = id;
    originalAmount = Math.abs(tx.amount);
    currentSplits = tx.splits ? JSON.parse(JSON.stringify(tx.splits)) : [];
    
    document.getElementById('split-original-desc').innerText = tx.desc;
    document.getElementById('split-modal').classList.remove('hidden');
    document.getElementById('split-modal').classList.add('flex');
    
    renderSplitRows();
}

window.closeSplitModal = function() {
    document.getElementById('split-modal').classList.add('hidden');
    document.getElementById('split-modal').classList.remove('flex');
    splitTxId = null;
    currentSplits = [];
}

window.addSplitRow = function() {
    const currentTotal = currentSplits.reduce((sum, s) => sum + s.amount, 0);
    let remaining = originalAmount - currentTotal;
    if (remaining < 0) remaining = 0;

    currentSplits.push({
        id: Date.now() + Math.random(),
        desc: '',
        amount: remaining > 0 ? parseFloat(remaining.toFixed(2)) : 0,
        category: categories[0].name
    });
    renderSplitRows();
}

window.removeSplitRow = function(splitId) {
    currentSplits = currentSplits.filter(s => s.id !== splitId);
    renderSplitRows();
}

function renderSplitRows() {
    const container = document.getElementById('split-rows');
    container.innerHTML = '';
    
    let currentTotal = 0;

    currentSplits.forEach((s, index) => {
        currentTotal += s.amount;
        
        const row = document.createElement('div');
        row.className = 'flex gap-2 items-center bg-slate-50 p-3 rounded-lg border border-slate-200';
        row.innerHTML = `
            <div class="flex-1">
                <input type="text" placeholder="Opis pozycji" value="${s.desc}" onchange="updateSplit(${s.id}, 'desc', this.value)" class="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
            </div>
            <div class="w-32">
                <input type="number" placeholder="Kwota" value="${s.amount}" step="0.01" min="0" onchange="updateSplit(${s.id}, 'amount', this.value)" class="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
            </div>
            <div class="w-40">
                <select onchange="updateSplit(${s.id}, 'category', this.value)" class="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white cursor-pointer">
                    ${getCategoryOptionsHtml(s.category)}
                </select>
            </div>
            <button onclick="removeSplitRow(${s.id})" class="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            </button>
        `;
        container.appendChild(row);
    });

    const remaining = originalAmount - currentTotal;
    const remEl = document.getElementById('split-remaining');
    remEl.innerText = `${remaining.toFixed(2)} PLN`;
    
    const saveBtn = document.getElementById('split-save-btn');
    if (remaining < -0.01) {
        remEl.className = 'text-xl font-bold text-rose-600';
        saveBtn.disabled = true;
    } else if (remaining < 0.01) {
        remEl.className = 'text-xl font-bold text-emerald-600';
        saveBtn.disabled = false;
    } else {
        remEl.className = 'text-xl font-bold text-blue-700';
        saveBtn.disabled = false;
    }
}

window.updateSplit = function(id, field, value) {
    const split = currentSplits.find(s => s.id === id);
    if (split) {
        if (field === 'amount') split.amount = parseFloat(value) || 0;
        else split[field] = value;
        renderSplitRows();
    }
}

window.saveSplitModal = async function() {
    const tx = transactions.find(t => t.id === splitTxId);
    if (!tx) return;

    const totalSplit = currentSplits.reduce((sum, s) => sum + s.amount, 0);
    
    if (totalSplit > Math.abs(tx.amount) + 0.01) {
        showToast('Kwota podziału przekracza oryginał!', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/transactions/${splitTxId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ splits: currentSplits })
        });
        
        if (response.ok) {
            tx.splits = currentSplits.length > 0 ? currentSplits : undefined;
            showToast('Podział został zapisany.');
            closeSplitModal();
            renderTransactions();
            if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) renderSummary();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisywania podziału.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem API.', 'error');
    }
}

// --- PODSUMOWANIE I FILTRY ---
window.applySummaryFilter = function(source) {
    const monthInput = document.getElementById('filter-month');
    const startInput = document.getElementById('filter-start');
    const endInput = document.getElementById('filter-end');

    if (source === 'month') {
        startInput.value = '';
        endInput.value = '';
    } else if (source === 'range') {
        monthInput.value = '';
    }
    renderSummary();
}

function renderSummary() {
    const monthFilter = document.getElementById('filter-month').value;
    const startFilter = document.getElementById('filter-start').value;
    const endFilter = document.getElementById('filter-end').value;

    // Wyświetlenie aktualnego okresu w nowej nawigacji
    const monthNames = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"];
    const summaryDisplay = document.getElementById('summary-month-display');
    if (summaryDisplay) {
        if (monthFilter) {
            const [y, m] = monthFilter.split('-');
            summaryDisplay.innerText = `${monthNames[parseInt(m)-1]} ${y}`;
            summaryDisplay.classList.add('text-blue-600');
        } else if (startFilter || endFilter) {
            summaryDisplay.innerText = `Wybrany zakres dat`;
            summaryDisplay.classList.add('text-blue-600');
        } else {
            summaryDisplay.innerText = `${monthNames[viewDate.getMonth()]} ${viewDate.getFullYear()}`;
            summaryDisplay.classList.remove('text-blue-600');
        }
    }

    const allTx = getFullTransactionsList(monthFilter, startFilter, endFilter);
    let filteredTx = allTx;

    if (monthFilter) {
        const [year, month] = monthFilter.split('-');
        filteredTx = allTx.filter(t => {
            const d = new Date(t.date);
            return d.getFullYear() == year && (d.getMonth() + 1) == month;
        });
    } else if (startFilter || endFilter) {
        filteredTx = allTx.filter(t => {
            let pass = true;
            if (startFilter && t.date < startFilter) pass = false;
            if (endFilter && t.date > endFilter) pass = false;
            return pass;
        });
    } else {
        filteredTx = allTx.filter(t => isSameMonthAndYear(t.date, viewDate));
    }

    let income = 0;
    let expense = 0;
    let catTotals = {};

    filteredTx.forEach(t => {
        if (t.splits && t.splits.length > 0) {
            let totalSplitAmt = 0;
            t.splits.forEach(s => {
                let actualAmount = t.amount < 0 ? -Math.abs(s.amount) : Math.abs(s.amount);
                totalSplitAmt += Math.abs(actualAmount);
                if (actualAmount > 0) income += actualAmount; else expense += Math.abs(actualAmount);
                catTotals[s.category] = (catTotals[s.category] || 0) + Math.abs(actualAmount);
            });
            
            let remaining = Math.abs(t.amount) - totalSplitAmt;
            if (remaining > 0.01) {
                let remActual = t.amount < 0 ? -remaining : remaining;
                if (remActual > 0) income += remActual; else expense += Math.abs(remActual);
                catTotals[t.category] = (catTotals[t.category] || 0) + remaining;
            }
        } else {
            if (t.amount > 0) income += t.amount; else expense += Math.abs(t.amount);
            catTotals[t.category] = (catTotals[t.category] || 0) + Math.abs(t.amount);
        }
    });

    document.getElementById('summary-income').innerText = `${income.toFixed(2)} PLN`;
    document.getElementById('summary-expense').innerText = `${expense.toFixed(2)} PLN`;
    
    const total = income - expense;
    const totalEl = document.getElementById('summary-total');
    totalEl.innerText = `${total >= 0 ? '+' : ''}${total.toFixed(2)} PLN`;
    totalEl.className = `text-2xl font-bold ${total >= 0 ? 'text-emerald-600' : 'text-rose-600'}`;

    const list = document.getElementById('summary-category-list');
    list.innerHTML = '';
    
    // Grupowanie na przychody i wydatki
    const incCats = Object.keys(catTotals).filter(cat => categories.find(c => c.name === cat)?.type === 'income');
    const expCats = Object.keys(catTotals).filter(cat => categories.find(c => c.name === cat)?.type === 'expense');
    
    // Renderuj Przychody
    if(incCats.length > 0) {
        list.innerHTML += `<tr><td colspan="3" class="bg-emerald-50 text-emerald-700 font-bold p-3 text-xs uppercase tracking-wider">Przychody</td></tr>`;
        incCats.sort((a, b) => catTotals[b] - catTotals[a]).forEach(cat => {
            const percentage = income > 0 ? Math.round((catTotals[cat] / income) * 100) : 0;
            list.innerHTML += buildSummaryRow(cat, catTotals[cat], percentage, 'emerald');
        });
    }

    // Renderuj Wydatki
    if(expCats.length > 0) {
        list.innerHTML += `<tr><td colspan="3" class="bg-rose-50 text-rose-700 font-bold p-3 text-xs uppercase tracking-wider mt-2">Wydatki</td></tr>`;
        expCats.sort((a, b) => catTotals[b] - catTotals[a]).forEach(cat => {
            const percentage = expense > 0 ? Math.round((catTotals[cat] / expense) * 100) : 0;
            list.innerHTML += buildSummaryRow(cat, catTotals[cat], percentage, 'rose');
        });
    }
}

function buildSummaryRow(catName, amount, percentage, colorPrefix) {
    return `
        <tr class="hover:bg-slate-50">
            <td class="p-4 border-b border-slate-100 font-medium text-slate-700">${catName}</td>
            <td class="p-4 border-b border-slate-100 font-bold text-right text-${colorPrefix}-600">${amount.toFixed(2)} PLN</td>
            <td class="p-4 border-b border-slate-100">
                <div class="flex items-center justify-end gap-2">
                    <span class="text-xs text-slate-500 w-8 text-right">${percentage}%</span>
                    <div class="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div class="h-full bg-${colorPrefix}-500 rounded-full" style="width: ${percentage}%"></div>
                    </div>
                </div>
            </td>
        </tr>
    `;
}

// --- POŁĄCZENIE Z BACKENDEM (FLASK) ---
async function fetchInitialData() {
    try {
        const response = await fetch('/api/init');
        if (!response.ok) {
            if (response.status === 401) {
                // Not logged in, do nothing. The page should be showing the login form.
                // Returning here prevents the rest of the function from running and trying to render empty data.
                return;
            }
            // For other server errors, try to parse the error and show it.
            const errorData = await response.json().catch(() => ({ error: 'Błąd pobierania danych z serwera.' }));
            showToast(errorData.error || 'Nie udało się pobrać danych z serwera.', 'error');
            return;
        }
        const data = await response.json();
        transactions = data.transactions || [];
        categories = data.categories || [];
        contractors = data.contractors || [];
        accounts = data.accounts || [];
        
        updateCategorySelects();
        updateContractorSelects();
        updateAccountSelects();
        renderCategories();
        renderContractors();
        renderAccounts();
        renderTransactions();
    } catch (error) {
        console.error('Błąd pobierania danych z API:', error);
        showToast('Nie udało się pobrać danych z serwera.', 'error');
    }
}

// --- INICJALIZACJA APLIKACJI ---
document.getElementById('tx-date').value = new Date().toISOString().split('T')[0];
fetchInitialData();
fetchPendingStaging(); // Inicjalne pobranie transakcji do weryfikacji dla licznika (badge)