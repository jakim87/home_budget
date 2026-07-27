// --- LOGIKA STAGINGU (OCZEKUJĄCYCH TRANSAKCJI) ---
async function reanalyzeStaging() {
    try {
        const response = await fetch('/api/staging/reanalyze', { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            showToast(`Odświeżono mapowanie dla ${result.count} transakcji.`, 'success');
            await fetchPendingStaging();
        } else {
            showToast(result.error || 'Błąd podczas odświeżania mapowania.', 'error');
        }
    } catch (e) {
        showToast('Błąd połączenia z serwerem.', 'error');
    }
}

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

function resolveStagingDestAccountId(t) {
    // Konto docelowe może pochodzić z lokalnego wyboru w tej sesji (_dest_account_id)
    // albo, dla wierszy już rozpoznanych automatycznie po numerze konta, z nazwy
    // istniejącego kontrahenta "Moje konto: {nazwa}" — ta sama konwencja co po
    // stronie serwera w _resolve_destination_account (budget_service.py).
    if (t._dest_account_id) return String(t._dest_account_id);
    if (t.proposed_contractor_id) {
        const cont = contractors.find(c => c.id == t.proposed_contractor_id);
        if (cont && cont.name.startsWith('Moje konto: ')) {
            const destAcc = accounts.find(a => a.name === cont.name.slice('Moje konto: '.length));
            if (destAcc) return String(destAcc.id);
        }
    }
    return '';
}

function getStagingStatus(t) {
    const cat = categories.find(c => c.name === t.proposed_category);
    const isTransfer = !!(cat && cat.type === 'transfer');
    const destResolved = isTransfer ? resolveStagingDestAccountId(t) : '';
    const hasSuggestion = !isTransfer && !!(t.suggested_contractor_name && !t.proposed_contractor_id);
    const isFullyMapped = isTransfer
        ? !!(t.proposed_category && destResolved)
        : !!(t.proposed_category && t.proposed_contractor_id);
    const isPartiallyMapped = !hasSuggestion && !isFullyMapped && !!(t.proposed_category || t.proposed_contractor_id || destResolved);
    const isUnmapped = !hasSuggestion && !isFullyMapped && !isPartiallyMapped;
    return { hasSuggestion, isFullyMapped, isPartiallyMapped, isUnmapped, isTransfer };
}

window.setStagingFilter = function(filter) {
    stagingFilter = filter;
    renderStaging();
};

window.toggleStagingSort = function(field) {
    if (stagingSort.field === field) {
        stagingSort.dir = stagingSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
        stagingSort.field = field;
        stagingSort.dir = field === 'date' ? 'desc' : 'asc';
    }
    renderStaging();
};

function renderStaging() {
    const list = document.getElementById('staging-list');
    const empty = document.getElementById('staging-empty');
    const badge = document.getElementById('staging-badge');
    const filtersRow = document.getElementById('staging-filters');

    list.innerHTML = '';

    if (pendingStaging.length === 0) {
        badge.classList.add('hidden');
        if (filtersRow) filtersRow.classList.add('hidden');
        const emptyP = empty.querySelector('p');
        if (emptyP) emptyP.textContent = 'Brak transakcji do weryfikacji.';
        empty.classList.remove('hidden');
        list.parentElement.classList.add('hidden');
        return;
    }

    badge.innerText = pendingStaging.length;
    badge.classList.remove('hidden');
    if (filtersRow) filtersRow.classList.remove('hidden');

    // Zlicz statusy z pełnej listy
    const counts = { all: pendingStaging.length, mapped: 0, suggestion: 0, partial: 0, unmapped: 0 };
    pendingStaging.forEach(t => {
        const { hasSuggestion, isFullyMapped, isPartiallyMapped } = getStagingStatus(t);
        if (isFullyMapped) counts.mapped++;
        else if (hasSuggestion) counts.suggestion++;
        else if (isPartiallyMapped) counts.partial++;
        else counts.unmapped++;
    });

    // Auto-przełącz na 'mapped' gdy aktywny filtr nic nie pokaże, ale są zmapowane transakcje.
    // Zapobiega sytuacji gdy przycisk pokazuje "(X)" a lista jest pusta.
    if (counts.mapped > 0 && stagingFilter !== 'all' && stagingFilter !== 'mapped') {
        const filterStillHasItems = pendingStaging.some(t => {
            const s = getStagingStatus(t);
            if (stagingFilter === 'suggestion') return s.hasSuggestion;
            if (stagingFilter === 'partial')    return s.isPartiallyMapped;
            if (stagingFilter === 'unmapped')   return s.isUnmapped;
            return false;
        });
        if (!filterStillHasItems) stagingFilter = 'mapped';
    }

    // Aktualizuj przyciski filtrów
    ['all', 'mapped', 'suggestion', 'partial', 'unmapped'].forEach(f => {
        const countEl = document.getElementById(`sf-count-${f}`);
        if (countEl) countEl.textContent = counts[f];
        const btn = document.getElementById(`sf-${f}`);
        if (btn) {
            btn.className = stagingFilter === f
                ? 'text-xs px-3 py-1 rounded-full font-medium transition-colors bg-slate-700 text-white'
                : 'text-xs px-3 py-1 rounded-full font-medium transition-colors bg-slate-100 text-slate-600 hover:bg-slate-200';
        }
    });

    // Aktualizuj ikony sortowania
    ['date', 'title', 'amount'].forEach(f => {
        const el = document.getElementById(`sort-icon-${f}`);
        if (!el) return;
        el.textContent = stagingSort.field === f ? (stagingSort.dir === 'asc' ? '↑' : '↓') : '↕';
        el.className = `ml-0.5 ${stagingSort.field === f ? 'text-slate-700' : 'text-slate-300'}`;
    });

    // Aktualizuj licznik zmapowanych (zawsze z pełnej listy)
    const approveBtn = document.getElementById('approve-all-btn');
    if (approveBtn) approveBtn.textContent = `Zatwierdź zmapowane (${counts.mapped})`;

    // Filtruj
    let displayList = stagingFilter === 'all' ? pendingStaging : pendingStaging.filter(t => {
        const { hasSuggestion, isFullyMapped, isPartiallyMapped, isUnmapped } = getStagingStatus(t);
        if (stagingFilter === 'mapped') return isFullyMapped;
        if (stagingFilter === 'suggestion') return hasSuggestion;
        if (stagingFilter === 'partial') return isPartiallyMapped;
        if (stagingFilter === 'unmapped') return isUnmapped;
        return true;
    });

    // Sortuj
    displayList = [...displayList].sort((a, b) => {
        let valA, valB;
        if (stagingSort.field === 'date') { valA = a.date; valB = b.date; }
        else if (stagingSort.field === 'title') { valA = (a.title || '').toLowerCase(); valB = (b.title || '').toLowerCase(); }
        else if (stagingSort.field === 'amount') { valA = a.amount; valB = b.amount; }
        else { valA = a.date; valB = b.date; }
        if (valA < valB) return stagingSort.dir === 'asc' ? -1 : 1;
        if (valA > valB) return stagingSort.dir === 'asc' ? 1 : -1;
        return 0;
    });

    if (displayList.length === 0) {
        const emptyP = empty.querySelector('p');
        if (emptyP) emptyP.textContent = 'Brak transakcji dla wybranego filtru.';
        empty.classList.remove('hidden');
        list.parentElement.classList.add('hidden');
        return;
    }

    empty.classList.add('hidden');
    list.parentElement.classList.remove('hidden');

    displayList.forEach(t => {
        const isPositive = t.amount >= 0;
        const amountClass = isPositive ? 'text-emerald-600' : 'text-rose-600';
        const amountText = `${isPositive ? '+' : ''}${t.amount.toFixed(2)} PLN`;

        const { hasSuggestion, isFullyMapped, isPartiallyMapped, isTransfer } = getStagingStatus(t);

        let rowBg = 'hover:bg-slate-50';
        let badgeHtml = '';
        let btnClass = 'bg-slate-200 text-slate-400 cursor-not-allowed';
        let btnDisabled = true;

        if (isFullyMapped) {
            if (isTransfer) {
                rowBg = 'bg-sky-50/40 hover:bg-sky-100/50';
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-100 text-sky-700 uppercase tracking-wider" title="Transakcja rozpoznana jako przelew wewnętrzny">Przelew</span>`;
                btnClass = 'bg-sky-600 hover:bg-sky-700 focus:ring-sky-500';
            } else {
                rowBg = 'bg-emerald-50/40 hover:bg-emerald-100/50';
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700 uppercase tracking-wider" title="Transakcja w pełni zmapowana">Zmapowano</span>`;
                btnClass = 'bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500';
            }
            btnDisabled = false;
        } else if (hasSuggestion) {
            rowBg = 'bg-amber-50/40 hover:bg-amber-100/50';
            badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700 uppercase tracking-wider" title="Automatyczna sugestia kontrahenta — wymaga akceptacji">Auto-sugestia</span>`;
        } else if (isPartiallyMapped) {
            rowBg = 'bg-blue-50/30 hover:bg-blue-100/50';
            badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700 uppercase tracking-wider" title="Znaleziono częściowe dopasowanie">Częściowo</span>`;
        }

        const row = document.createElement('tr');
        row.className = `${rowBg} transition-colors`;
        row.innerHTML = `
            <td class="p-3 border-b border-slate-100 text-sm text-slate-500 whitespace-nowrap">${t.date}</td>
            <td class="p-3 border-b border-slate-100 font-medium text-slate-800 break-words">
                <div class="flex flex-wrap items-center gap-1.5 mb-0.5">
                    <span>${t.title}</span>
                    ${badgeHtml}
                </div>
                ${t.contractor ? `<div class="text-xs text-slate-500 font-normal mt-0.5 break-all">${t.contractor}</div>` : ''}
                ${t.transfer_from ? `<div class="flex items-center gap-1 mt-1 text-xs text-sky-700 font-medium">
                    <span>Z: ${t.transfer_from.name}${t.transfer_from.abbrev ? ` <span class="text-sky-500 font-normal">(${t.transfer_from.abbrev})</span>` : ''}</span>
                    <span class="text-sky-400">→</span>
                    <span>Na: ${t.transfer_to.name}${t.transfer_to.abbrev ? ` <span class="text-sky-500 font-normal">(${t.transfer_to.abbrev})</span>` : ''}</span>
                </div>` : ''}
            </td>
            <td class="p-3 border-b border-slate-100">
                ${hasSuggestion ? `
                <div class="flex items-center gap-1 mb-2 p-1.5 bg-amber-50 border border-amber-200 rounded-lg">
                    <span class="text-xs text-amber-700 font-medium shrink-0">Sugestia:</span>
                    <input type="text" id="suggested-name-${t.id}" value="${t.suggested_contractor_name}" class="flex-1 text-xs p-1 border border-amber-300 rounded focus:ring-1 focus:ring-amber-400 outline-none min-w-0">
                    <button onclick="acceptSuggestedContractor(${t.id})" class="shrink-0 text-xs bg-amber-500 hover:bg-amber-600 text-white px-2 py-1 rounded font-medium transition-colors whitespace-nowrap">Akceptuj</button>
                </div>` : ''}
                ${isTransfer ? `
                <select id="staging-dest-${t.id}" onchange="updateStagingLocalState(${t.id}, '_dest_account_id', this.value)" class="w-full p-1.5 border border-sky-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none text-sm bg-white cursor-pointer mb-1.5">
                    <option value="">Wybierz konto docelowe...</option>
                    ${getDestAccountOptionsHtml(t.account_id, resolveStagingDestAccountId(t))}
                </select>` : `
                <select id="staging-cont-${t.id}" onchange="updateStagingLocalState(${t.id}, 'proposed_contractor_id', this.value)" class="w-full p-1.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white cursor-pointer mb-1.5">
                    <option value="">Wybierz kontrahenta...</option>
                    ${getContractorOptionsHtml(t.proposed_contractor_id)}
                </select>`}
                <select id="staging-cat-${t.id}" onchange="updateStagingLocalState(${t.id}, 'proposed_category', this.value)" class="w-full p-1.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white cursor-pointer">
                    <option value="">Wybierz kategorię...</option>
                    ${getCategoryOptionsHtml(t.proposed_category)}
                </select>
            </td>
            <td class="p-3 border-b border-slate-100 font-bold ${amountClass} text-right whitespace-nowrap">${amountText}</td>
            <td class="p-3 border-b border-slate-100 text-center">
                <button onclick="approveStaging(${t.id})" ${btnDisabled ? `disabled title="${isTransfer ? 'Uzupełnij kategorię i konto docelowe, aby zatwierdzić' : 'Uzupełnij kategorię i kontrahenta, aby zatwierdzić'}"` : ''} class="px-3 py-2 ${btnClass} text-sm font-medium rounded-lg transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 whitespace-nowrap w-full ${btnDisabled ? '' : 'text-white'}">
                    Zatwierdź
                </button>
            </td>
        `;
        list.appendChild(row);
    });
}

window.updateStagingLocalState = function(id, field, value) {
    const item = pendingStaging.find(t => t.id === id);
    if (item && value !== '__NEW_CATEGORY__' && value !== '__NEW_CONTRACTOR__') {
        item[field] = value;
        renderStaging();
    }
}

window.acceptSuggestedContractor = function(stg_id) {
    const input = document.getElementById(`suggested-name-${stg_id}`);
    const name = input ? input.value.trim() : '';
    if (!name) {
        showToast('Podaj nazwę kontrahenta.', 'error');
        return;
    }
    openQuickContractorModal(name, stg_id);
}

window.approveStaging = async function(id) {
    const catSelect = document.getElementById(`staging-cat-${id}`);
    const category = catSelect.value;
    const cat = categories.find(c => c.name === category);
    const isTransfer = cat && cat.type === 'transfer';

    if (!category) {
        showToast('Błąd: wybierz kategorię przed zatwierdzeniem.', 'error');
        return;
    }

    let contractor_id;
    if (isTransfer) {
        const destSelect = document.getElementById(`staging-dest-${id}`);
        const destAccId = destSelect ? destSelect.value : '';
        if (!destAccId) {
            showToast('Wybierz konto docelowe przelewu.', 'error');
            return;
        }
        try {
            contractor_id = await resolveOrCreateTransferContractorId(destAccId);
        } catch (err) {
            showToast(err.message, 'error');
            return;
        }
    } else {
        const contSelect = document.getElementById(`staging-cont-${id}`);
        if (!contSelect.value) {
            showToast('Błąd: wybierz kontrahenta przed zatwierdzeniem.', 'error');
            return;
        }
        contractor_id = parseInt(contSelect.value, 10);
    }

    try {
        const response = await fetch(`/api/staging/${id}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: category, contractor_id: contractor_id })
        });
        
        if (response.ok) {
            showToast('Transakcja zatwierdzona!');
            // Usuń z lokalnej listy i odśwież widok — nie fetch z serwera, żeby nie stracić zmian na pozostałych wierszach
            pendingStaging = pendingStaging.filter(t => t.id !== id);
            renderStaging();
            // Odśwież transakcje/konta, ale bez nadpisywania pendingStaging z serwera
            fetchInitialData({ skipStagingRefresh: true });
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
    const mapped = pendingStaging.filter(t => getStagingStatus(t).isFullyMapped);

    if (mapped.length === 0) {
        showToast('Brak w pełni zmapowanych transakcji (posiadających kategorię i kontrahenta).', 'info');
        return;
    }

    if (!confirm(`Czy na pewno chcesz zatwierdzić ${mapped.length} zmapowanych transakcji?`)) return;

    const progressBar   = document.getElementById('staging-progress-bar');
    const progressFill  = document.getElementById('staging-progress-fill');
    const progressText  = document.getElementById('staging-progress-text');
    const approveBtn    = document.getElementById('approve-all-btn');

    // Pokaż pasek postępu i zablokuj przycisk
    progressFill.style.width = '0%';
    progressText.textContent = `0 / ${mapped.length}`;
    progressBar.classList.remove('hidden');
    if (approveBtn) {
        approveBtn.disabled = true;
        approveBtn.innerHTML = `<svg class="animate-spin inline h-3 w-3 mr-1 -mt-0.5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>Zatwierdzanie…`;
    }

    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < mapped.length; i++) {
        const t = mapped[i];
        try {
            const status = getStagingStatus(t);
            const contractor_id = status.isTransfer
                ? await resolveOrCreateTransferContractorId(resolveStagingDestAccountId(t))
                : parseInt(t.proposed_contractor_id, 10);
            const res = await fetch(`/api/staging/${t.id}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: t.proposed_category, contractor_id: contractor_id })
            });
            if (res.ok) successCount++;
            else errorCount++;
        } catch (_) { errorCount++; }

        // Aktualizuj pasek po każdej transakcji
        const pct = Math.round(((i + 1) / mapped.length) * 100);
        progressFill.style.width = `${pct}%`;
        progressText.textContent = `${i + 1} / ${mapped.length}`;
    }

    // Przywróć przycisk
    if (approveBtn) {
        approveBtn.disabled = false;
        approveBtn.textContent = 'Zatwierdź zmapowane';
    }

    const msg = errorCount === 0
        ? `Zatwierdzono ${successCount} transakcji!`
        : `Zatwierdzono ${successCount}, błędy: ${errorCount}.`;
    showToast(msg, errorCount === 0 ? 'success' : 'error');

    // Ukryj pasek po chwili (widoczne 100% przez 1.2 s)
    setTimeout(() => { progressBar.classList.add('hidden'); }, 1200);

    if (successCount > 0) {
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

