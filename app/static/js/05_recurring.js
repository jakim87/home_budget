// --- LOGIKA TRANSAKCJI CYKLICZNYCH (GENEROWANIE WIRTUALNYCH) ---
async function fetchRecurringTransactions() {
    try {
        const response = await fetch('/api/recurring-transactions/');
        if (response.ok) {
            recurringTransactions = await response.json();
            renderRecurringList();
        } else {
            console.error("Błąd pobierania transakcji cyklicznych");
        }
    } catch (e) {
        console.error("Błąd połączenia przy pobieraniu transakcji cyklicznych", e);
    }
}

async function fetchPlannedTransactions() {
    try {
        const response = await fetch('/api/planned-transactions/');
        if (response.ok) {
            plannedTransactions = await response.json();
            renderPlannedList();
        } else {
            console.error("Błąd pobierania transakcji zaplanowanych");
        }
    } catch (e) {
        console.error("Błąd połączenia przy pobieraniu transakcji zaplanowanych", e);
    }
}

async function fetchRecurringPreview(year, month) {
    try {
        const res = await fetch(`/api/recurring-transactions/preview?year=${year}&month=${month}`);
        if (!res.ok) return;
        virtualTransactions = await res.json();
    } catch (e) {
        virtualTransactions = [];
    }
}

function generateVirtualTransactions(targetYear, targetMonth, startLimit, endLimit) { // Ta funkcja pozostaje, ale teraz operuje na danych z backendu
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
        const rtStart = new Date(rt.start_date);
        const rtEnd = rt.end_date ? new Date(rt.end_date) : new Date(2100, 11, 31);
        
        if (rtEnd < periodStart || rtStart > periodEnd) return;

        // Używamy next_run_date z backendu jako punktu startowego do generowania
        let curr = new Date(rt.next_run_date);

        // Generujemy wirtualne transakcje do przodu, aż do końca okresu
        while (curr <= periodEnd && curr <= rtEnd) {
            if (curr >= periodStart) {
                virtualTx.push(createVirtualTxObject(rt, curr));
            }
            // Obliczanie następnej daty na podstawie częstotliwości
            if (rt.frequency === 'monthly') {
                curr.setMonth(curr.getMonth() + rt.interval);
            } else if (rt.frequency === 'daily') {
                curr.setDate(curr.getDate() + rt.interval);
            } else if (rt.frequency === 'weekly') {
                curr.setDate(curr.getDate() + (7 * rt.interval));
            } else if (rt.frequency === 'yearly') {
                curr.setFullYear(curr.getFullYear() + rt.interval);
            } else {
                break; // Nieznana częstotliwość, przerwij pętlę
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
        desc: `${rt.title}`,
        amount: parseFloat(rt.amount),
        category: categories.find(c => c.id === rt.category_id)?.name || 'Brak',
        contractor_id: rt.contractor_id,
        contractor_name: contractors.find(c => c.id === rt.contractor_id)?.name || 'Brak',
        account_id: rt.account_id,
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

    let filteredVirtuals;
    if (startFilter || endFilter) {
        const periodStart = startFilter ? new Date(startFilter) : new Date(2000, 0, 1);
        const periodEnd = endFilter ? new Date(endFilter) : new Date(2100, 11, 31);
        filteredVirtuals = virtualTransactions.filter(t => {
            const d = new Date(t.date);
            return d >= periodStart && d <= periodEnd;
        });
    } else {
        filteredVirtuals = virtualTransactions.filter(t => isSameMonthAndYear(t.date, new Date(year, month)));
    }

    let combined = [...transactions, ...filteredVirtuals];
    if (globalAccountFilter) {
        combined = combined.filter(t => t.account_id == globalAccountFilter);
    }
    return combined;
}

// --- OKNO TRANSAKCJI CYKLICZNYCH ---
window.openRecurringModal = function() {
    fetchRecurringTransactions(); // Pobierz najnowsze dane z backendu
    fetchPlannedTransactions();
    updateCategorySelects();
    document.getElementById('rec-start-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('recurring-modal').classList.remove('hidden');
    document.getElementById('recurring-modal').classList.add('flex');
};

window.closeRecurringModal = function() {
    document.getElementById('recurring-modal').classList.add('hidden');
    document.getElementById('recurring-modal').classList.remove('flex');
    document.getElementById('planned-form').reset(); // Reset planned form
    document.getElementById('recurring-form').reset(); // Reset recurring form
    document.getElementById('rec-start-date').value = new Date().toISOString().split('T')[0]; // Reset recurring start date
    toggleRecEndDate(); // Reset recurring end date toggle
    toggleRecFreqInputs(); // Reset recurring frequency inputs
};

window.toggleRecEndDate = function() {
    const isIndefinite = document.getElementById('rec-indefinite').checked;
    document.getElementById('rec-end-date').disabled = isIndefinite;
    if (isIndefinite) document.getElementById('rec-end-date').value = '';
};

window.toggleRecFreqInputs = function() {
    const type = document.getElementById('rec-freq-type').value;
    document.getElementById('rec-opts-monthly').classList.toggle('hidden', type !== 'monthly');
    document.getElementById('rec-opts-monthly').classList.toggle('flex', type === 'monthly');
    document.getElementById('rec-opts-daily').classList.toggle('hidden', type !== 'daily');
    document.getElementById('rec-opts-daily').classList.toggle('flex', type === 'daily');
    document.getElementById('rec-opts-weekly').classList.toggle('hidden', type !== 'weekly');
    document.getElementById('rec-opts-weekly').classList.toggle('flex', type === 'weekly');
};



let _endRecurringId = null;

window.openEndRecurringModal = function(id, currentEndDate) {
    _endRecurringId = id;
    const input = document.getElementById('end-recurring-date');
    input.value = currentEndDate || '';
    const modal = document.getElementById('end-recurring-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
};

window.closeEndRecurringModal = function() {
    const modal = document.getElementById('end-recurring-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    _endRecurringId = null;
};

window.submitEndRecurring = async function() {
    if (!_endRecurringId) return;
    const endDate = document.getElementById('end-recurring-date').value;
    if (!endDate) {
        showToast('Wybierz datę zakończenia cyklu.', 'error');
        return;
    }
    try {
        const response = await fetch(`/api/recurring-transactions/${_endRecurringId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ end_date: endDate })
        });
        if (response.ok) {
            showToast('Data zakończenia cyklu została ustawiona.', 'success');
            closeEndRecurringModal();
            await fetchRecurringTransactions();
            await fetchRecurringPreview(viewDate.getFullYear(), viewDate.getMonth() + 1);
            renderTransactions();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisu.', 'error');
        }
    } catch (e) { showToast('Błąd połączenia z API.', 'error'); }
};

window.deletePlanned = async function(id) {
    if (!confirm('Czy na pewno chcesz usunąć tę zaplanowaną transakcję?')) return;

    try {
        const response = await fetch(`/api/planned-transactions/${id}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Zaplanowana transakcja usunięta.', 'info');
            await fetchPlannedTransactions();
            renderTransactions();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd usuwania.', 'error');
        }
    } catch (e) { showToast('Błąd połączenia z API.', 'error'); }
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
            const cat = categories.find(c => c.id === rt.category_id);
            let freqText = '';
            if (rt.frequency === 'monthly') freqText = `Co ${rt.interval} mies. (dzień: ${rt.day_of_month})`;
            else if (rt.frequency === 'daily') freqText = `Co ${rt.interval} dni`;
            else if (rt.frequency === 'weekly') freqText = `Co ${rt.interval} tyg. (dzień tyg: ${rt.day_of_week})`;
            else if (rt.frequency === 'yearly') freqText = `Co ${rt.interval} lat`;
            const endText = rt.end_date ? `Do ${rt.end_date}` : 'Bezterminowo';
            const nextRunFormatted = rt.next_run_date
                ? rt.next_run_date.split('-').reverse().join('.')
                : '—';

            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50 transition-colors group';
            row.innerHTML = `
                <td class="p-3 border-b border-slate-100">
                    <div class="font-medium text-slate-800">${rt.title}</div>
                    <div class="text-xs text-slate-500">${cat ? cat.name : 'Brak kategorii'}</div>
                </td>
                <td class="p-3 border-b border-slate-100 text-sm">
                    <div class="text-indigo-600 font-medium">${freqText}</div>
                    <div class="text-xs text-slate-500">Od ${rt.start_date} | ${endText}</div>
                </td>
                <td class="p-3 border-b border-slate-100 text-sm text-slate-700">
                    ${nextRunFormatted}
                </td>
                <td class="p-3 border-b border-slate-100 font-bold text-right ${isExp ? 'text-rose-600' : 'text-emerald-600'}">
                    ${isExp ? '' : '+'}${parseFloat(rt.amount).toFixed(2)} PLN
                </td>
                <td class="p-3 border-b border-slate-100 text-center">
                    <button onclick="openEndRecurringModal(${rt.id}, '${rt.end_date || ''}')" class="text-slate-400 hover:text-amber-600 p-1.5 rounded-md hover:bg-amber-50 transition-colors opacity-0 group-hover:opacity-100" title="Ustaw datę zakończenia">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2 2 4-4"></path></svg>
                    </button>
                </td>
            `;
            list.appendChild(row);
        });
    }
}

function renderPlannedList() {
    const list = document.getElementById('planned-list');
    const empty = document.getElementById('planned-empty');
    list.innerHTML = '';

    if (plannedTransactions.length === 0) {
        empty.classList.remove('hidden');
        list.parentElement.classList.add('hidden');
    } else {
        empty.classList.add('hidden');
        list.parentElement.classList.remove('hidden');

        plannedTransactions.forEach(pt => {
            const isExp = pt.amount < 0;
            const cat = categories.find(c => c.id === pt.category_id);
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50 transition-colors group';
            row.innerHTML = `
                <td class="p-3 border-b border-slate-100">
                    <div class="font-medium text-slate-800">${pt.title}</div>
                    <div class="text-xs text-slate-500">${cat ? cat.name : 'Brak kategorii'}</div>
                </td>
                <td class="p-3 border-b border-slate-100 text-sm">
                    <div class="text-blue-600 font-medium">Dnia: ${pt.execution_date}</div>
                </td>
                <td class="p-3 border-b border-slate-100 font-bold text-right ${isExp ? 'text-rose-600' : 'text-emerald-600'}">
                    ${isExp ? '' : '+'}${parseFloat(pt.amount).toFixed(2)} PLN
                </td>
                <td class="p-3 border-b border-slate-100 text-center">
                    <button onclick="deletePlanned(${pt.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100" title="Usuń plan">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            `;
            list.appendChild(row);
        });
    }
}

document.getElementById('recurring-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const desc = document.getElementById('rec-desc').value.trim();
    const rawAmount = parseFloat(document.getElementById('rec-amount').value);
    const categoryId = document.getElementById('rec-category').value;
    const contractorId = document.getElementById('rec-contractor').value;
    const startDate = document.getElementById('rec-start-date').value;
    const isIndefinite = document.getElementById('rec-indefinite').checked;
    const endDate = isIndefinite ? null : document.getElementById('rec-end-date').value;
    const accountInput = document.getElementById('rec-account').value;

    if (!desc || isNaN(rawAmount) || rawAmount <= 0 || !startDate || !accountInput || !categoryId) {
        showToast('Wypełnij poprawnie wszystkie pola (w tym konto).', 'error'); return;
    }
    if (!isIndefinite && !endDate) {
        showToast('Podaj datę zakończenia.', 'error'); return;
    }
    if (!isIndefinite && new Date(startDate) > new Date(endDate)) {
        showToast('Data zakończenia nie może być wcześniejsza niż rozpoczęcia.', 'error'); return;
    }

    const finalAmount = getSignFromCategoryId(categoryId) * Math.abs(rawAmount);

    const payload = {
        title: desc,
        amount: finalAmount.toFixed(2),
        account_id: parseInt(accountInput),
        category_id: categoryId ? parseInt(categoryId) : null,
        contractor_id: contractorId ? parseInt(contractorId) : null,
        start_date: startDate,
        end_date: endDate,
        frequency: document.getElementById('rec-freq-type').value,
        interval: 1, // Domyślnie, można rozbudować UI
        day_of_month: null,
        day_of_week: null
    };

    if (payload.frequency === 'monthly' || payload.frequency === 'yearly') {
        payload.day_of_month = parseInt(document.getElementById('rec-day-of-month').value);
        payload.interval = parseInt(document.getElementById('rec-interval-monthly').value);
    } else if (payload.frequency === 'daily') {
        payload.interval = parseInt(document.getElementById('rec-interval-daily').value);
    } else if (payload.frequency === 'weekly') {
        payload.day_of_week = parseInt(document.getElementById('rec-day-of-week').value);
        // Można dodać pole interwału dla tygodni, jeśli potrzebne
    }

    try {
        const response = await fetch('/api/recurring-transactions/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showToast('Transakcja cykliczna została dodana.', 'success');
            document.getElementById('recurring-form').reset();
            document.getElementById('rec-start-date').value = startDate;
            toggleRecEndDate(); toggleRecFreqInputs();
            await fetchRecurringTransactions();
            await fetchRecurringPreview(viewDate.getFullYear(), viewDate.getMonth() + 1);
            renderTransactions();
            if (!document.getElementById('tab-summary').classList.contains('tab-hidden')) renderSummary();
        } else {
            const err = await response.json();
            showToast(err.error?.body?.[0] || err.error || 'Błąd zapisu.', 'error');
        }
    } catch (e) {
        showToast('Błąd połączenia z API.', 'error');
    }
});

document.getElementById('planned-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const desc = document.getElementById('planned-desc').value.trim();
    const rawAmount = parseFloat(document.getElementById('planned-amount').value);
    const categoryId = document.getElementById('planned-category').value;
    const contractorId = document.getElementById('planned-contractor').value; // New
    const executionDate = document.getElementById('planned-exec-date').value;
    const accountInput = document.getElementById('planned-account').value;

    if (!desc || isNaN(rawAmount) || rawAmount <= 0 || !executionDate || !accountInput || !categoryId) {
        showToast('Wypełnij poprawnie wszystkie pola dla zaplanowanej transakcji.', 'error'); return;
    }

    const finalAmount = getSignFromCategoryId(categoryId) * Math.abs(rawAmount);

    const payload = {
        title: desc,
        amount: finalAmount.toFixed(2),
        account_id: parseInt(accountInput),
        category_id: parseInt(categoryId),
        contractor_id: contractorId ? parseInt(contractorId) : null, // New
        execution_date: executionDate,
    };

    try {
        const response = await fetch('/api/planned-transactions/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            showToast('Zaplanowano transakcję.', 'success');
            await fetchPlannedTransactions();
            renderTransactions();
        } else {
            const err = await response.json();
            showToast(err.error?.body?.[0] || err.error || 'Błąd zapisu.', 'error');
        }
    } catch (e) { showToast('Błąd połączenia z API.', 'error'); }
});

