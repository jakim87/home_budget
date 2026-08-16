// --- TRANSAKCJE ---

// Podpięcie Auto-uzupełniania do głównych formularzy
document.getElementById('tx-desc').addEventListener('input', function(e) {
    handleAutoFill(e.target.value, document.getElementById('tx-contractor'), document.getElementById('tx-category'));
});

const recDesc = document.getElementById('rec-desc');
if (recDesc) {
    recDesc.addEventListener('input', function(e) {
        handleAutoFill(e.target.value, document.getElementById('rec-contractor'), document.getElementById('rec-category'));
    });
}

document.getElementById('tx-category').addEventListener('change', function() {
    // Ręczny wybór kategorii ma pierwszeństwo — auto-uzupełnianie go nie nadpisuje.
    this.dataset.userSet = '1';
    const catName = this.value;
    const cat = categories.find(c => c.name === catName);
    const isTransfer = cat && cat.type === 'transfer';
    document.getElementById('tx-contractor-wrapper').classList.toggle('hidden', isTransfer);
    document.getElementById('tx-dest-account-wrapper').classList.toggle('hidden', !isTransfer);
    if (isTransfer) {
        updateDestAccountOptions();
    } else {
        document.getElementById('tx-dest-account').value = '';
    }
});

document.getElementById('tx-account').addEventListener('change', function() {
    if (!document.getElementById('tx-dest-account-wrapper').classList.contains('hidden')) {
        updateDestAccountOptions();
    }
});

document.getElementById('transaction-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const dateInput = document.getElementById('tx-date').value;
    const descInput = document.getElementById('tx-desc').value.trim();
    const rawAmount = parseFloat(document.getElementById('tx-amount').value);
    const categoryInput = document.getElementById('tx-category').value;
    const accountInput = document.getElementById('tx-account').value;
    const commentInput = document.getElementById('tx-comment').value.trim();

    if (!dateInput || isNaN(rawAmount) || rawAmount <= 0) {
        showToast('Wypełnij poprawnie wszystkie pola.', 'error');
        return;
    }
    if (!accountInput) {
        showToast('Proszę najpierw wybrać konto.', 'error');
        return;
    }

    const cat = categories.find(c => c.name === categoryInput);
    const isTransfer = cat && cat.type === 'transfer';
    let contractorId = null;

    if (isTransfer) {
        const destAccId = document.getElementById('tx-dest-account').value;
        if (!destAccId) {
            showToast('Wybierz konto docelowe przelewu.', 'error');
            return;
        }
        try {
            contractorId = await resolveOrCreateTransferContractorId(destAccId);
        } catch (err) {
            showToast(err.message, 'error');
            return;
        }
    } else {
        const rawContractor = document.getElementById('tx-contractor').value;
        contractorId = rawContractor ? parseInt(rawContractor) : null;
    }

    const finalAmount = getSignFromCategoryName(categoryInput) * Math.abs(rawAmount);

    const txData = {
        date: dateInput,
        desc: descInput,
        amount: finalAmount,
        category: categoryInput,
        contractor_id: contractorId,
        account_id: parseInt(accountInput),
        comment: commentInput || null
    };

    try {
        const response = await fetch('/api/transactions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(txData)
        });
        
        if (response.ok) {
            document.getElementById('tx-desc').value = '';
            document.getElementById('tx-amount').value = '';
            document.getElementById('tx-contractor').value = '';
            document.getElementById('tx-contractor-input').value = '';
            document.getElementById('tx-comment').value = '';
            delete document.getElementById('tx-category').dataset.userSet;
            // Konto zostaje takie, jakie wybrał użytkownik — kolejne transakcje zwykle
            // idą na to samo konto. Nie nadpisujemy go kontem z „Widoku konta".

            showToast('Transakcja została zapisana pomyślnie.');
            fetchInitialData(); // Pobiera na nowo dane by odświeżyć globalne saldo
        } else {
            showToast('Błąd serwera podczas zapisywania transakcji.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem.', 'error');
    }
});

window.toggleComment = function(uid, event) {
    // Wywołanie z klawiatury: reagujemy tylko na Enter i Spację, jak natywny <button>.
    if (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
    }
    const s = document.getElementById(uid + '-s');
    const f = document.getElementById(uid + '-f');
    if (!s || !f) return;
    s.classList.toggle('hidden');
    f.classList.toggle('hidden');
};

function startInlineEdit(id) {
    inlineEditingTxId = id;
    renderTransactions();
}

function cancelInlineEdit() {
    inlineEditingTxId = null;
    renderTransactions();
}

async function saveInlineEdit(id) {
    const dateVal = document.getElementById(`edit-date-${id}`).value;
    const descVal = document.getElementById(`edit-desc-${id}`).value.trim();
    const rawAmount = parseFloat(document.getElementById(`edit-amount-${id}`).value);
    const categoryVal = document.getElementById(`edit-cat-${id}`).value;
    const contractorVal = document.getElementById(`edit-cont-${id}`).value;
    if (!dateVal || isNaN(rawAmount) || rawAmount <= 0) {
        showToast('Wypełnij poprawnie wszystkie pola edycji.', 'error');
        return;
    }

    const tx = transactions.find(t => t.id === id);
    if (!tx) return;

    const commentVal = document.getElementById(`edit-comment-${id}`)?.value.trim() || '';

    const updatedTx = {
        date: dateVal,
        desc: descVal,
        amount: getSignFromCategoryName(categoryVal) * Math.abs(rawAmount),
        category: categoryVal,
        contractor_id: contractorVal ? parseInt(contractorVal) : null,
        comment: commentVal || null
    };

    try {
        const response = await fetch(`/api/transactions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedTx)
        });

        if (response.ok) {
            showToast('Zmiany zostały zapisane.');
            inlineEditingTxId = null;
            fetchInitialData();
        } else {
            showToast('Błąd zapisywania edycji na serwerze.', 'error');
        }
    } catch(e) {
        showToast('Błąd połączenia z serwerem.', 'error');
    }
}

function renderTransactions() {
    const list = document.getElementById('transaction-list');
    const emptyState = document.getElementById('empty-state');
    list.innerHTML = '';
    
    // Pobierz transakcje z aktualnego miesiąca (zwykłe + cykliczne)
    const allTx = getFullTransactionsList(null, null, null); 
    const filtered = allTx.filter(t => isSameMonthAndYear(t.date, viewDate));
    filtered.sort((a, b) => {
        if (a.date !== b.date) {
            return b.date.localeCompare(a.date);
        }
        // W przypadku tej samej daty, ułóż nowe pozycje (o wyższym ID) na samej górze
        const idA = typeof a.id === 'number' ? a.id : 0;
        const idB = typeof b.id === 'number' ? b.id : 0;
        return idB - idA;
    });

    // Kolumna „Konto" ma sens tylko przy widoku „Wszystkie konta" — przy wybranym
    // pojedynczym koncie cała tabela dotyczy tego jednego konta.
    const showAccountColumn = !globalAccountFilter;
    document.getElementById('th-tx-account').classList.toggle('hidden', !showAccountColumn);

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
            const accountCellHtml = showAccountColumn
                ? `<td class="p-4 border-b border-slate-100 text-sm text-slate-600 break-words whitespace-normal">${escapeHtml(accountLabelById(t.account_id))}</td>`
                : '';

            if (inlineEditingTxId === t.id && !t.isVirtual) {
                // TRYB EDYCJI
                row.className = 'bg-blue-50/50';
                row.innerHTML = `
                    <td class="p-2 border-b border-blue-100">
                        <input type="date" id="edit-date-${t.id}" value="${t.date}" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                    </td>
                    ${showAccountColumn ? `<td class="p-2 border-b border-blue-100 text-sm text-slate-500">${escapeHtml(accountLabelById(t.account_id))}</td>` : ''}
                    <td class="p-2 border-b border-blue-100">
                        <select id="edit-cont-${t.id}" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                            <option value="">Brak kontrahenta</option>
                            ${getContractorOptionsHtml(t.contractor_id)}
                        </select>
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        ${isSplit ?
                            `<span class="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded">Edycja podziału w oknie</span>
                             <input type="hidden" id="edit-cat-${t.id}" value="${escapeHtml(t.category)}">`
                            :
                            `<select id="edit-cat-${t.id}" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                                ${getCategoryOptionsHtml(t.category, false)}
                            </select>`
                        }
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        <input type="text" id="edit-desc-${t.id}" value="${escapeHtml(t.desc)}" oninput="handleAutoFill(this.value, document.getElementById('edit-cont-${t.id}'), document.getElementById('edit-cat-${t.id}'))" class="w-full p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white">
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        <input type="text" id="edit-comment-${t.id}" value="${escapeHtml(t.comment || '')}" maxlength="255" placeholder="Komentarz..." class="w-full p-1.5 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-xs bg-white">
                    </td>
                    <td class="p-2 border-b border-blue-100">
                        <input type="number" id="edit-amount-${t.id}" value="${Math.abs(t.amount).toFixed(2)}" step="0.01" min="0.01" ${isSplit ? 'readonly title="Kwota wynika z podziału"' : ''} class="w-full p-1.5 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white ${isSplit ? 'bg-slate-100 text-slate-500' : ''}">
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
                const catObj = categories.find(c => c.name === t.category);
                const isTransfer = catObj && catObj.type === 'transfer';
                
                let amountClass = 'text-slate-800';
                if (isTransfer) {
                    amountClass = 'text-sky-600';
                } else {
                    amountClass = isPositive ? 'text-emerald-600' : 'text-rose-600';
                }
                const amountText = `${isPositive ? '+' : ''}${t.amount.toFixed(2)} PLN`;
                
                const isVirtual = t.isVirtual;
                const iconHtml = isVirtual 
                    ? `<svg class="w-4 h-4 text-indigo-500 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Transakcja zaplanowana (cykliczna)"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>`
                    : ``;
                
                const commentHtml = (() => {
                    const c = t.comment || '';
                    if (!c) return `<span class="text-slate-300 text-xs">—</span>`;
                    const maxLen = 40;
                    if (c.length <= maxLen) return `<span class="text-slate-600 text-xs">${escapeHtml(c)}</span>`;
                    const uid = `cmt-${t.id}`;
                    const toggleAttrs = `role="button" tabindex="0" onclick="toggleComment('${uid}')" onkeydown="toggleComment('${uid}', event)"`;
                    return `<span id="${uid}-s" class="text-slate-600 text-xs cursor-pointer hover:text-blue-600" ${toggleAttrs}>${escapeHtml(c.substring(0, maxLen))}&hellip; <span class="text-blue-500 font-medium">[rozwiń]</span></span><span id="${uid}-f" class="hidden text-slate-600 text-xs">${escapeHtml(c)} <span class="text-blue-500 font-medium cursor-pointer" ${toggleAttrs}>[zwiń]</span></span>`;
                })();

                row.className = `transition-colors group hover:bg-slate-50 ${isVirtual ? 'bg-indigo-50/30' : ''}`;
                row.innerHTML = `
                    <td class="p-4 border-b border-slate-100 text-sm text-slate-500 whitespace-nowrap">${t.date}</td>
                    ${accountCellHtml}
                    <td class="p-4 border-b border-slate-100 text-slate-600 text-sm break-words whitespace-normal min-w-[120px]">
                        ${iconHtml}${escapeHtml(t.contractor_name || t.contractor || '-')}
                    </td>
                    <td class="p-4 border-b border-slate-100 text-slate-600 text-sm break-words whitespace-normal min-w-[120px]">
                        ${isSplit ?
                            '<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-600 font-medium text-xs border border-indigo-100" title="Transakcja rozbita na pozycje"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg> Sprawdź szczegóły</span>'
                            :
                            escapeHtml(t.category)
                        }
                    </td>
                    <td class="p-4 border-b border-slate-100 font-medium text-slate-800 break-words whitespace-normal min-w-[200px]">${escapeHtml(t.desc)}${t.transfer_unmatched ? ` <span class="ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700 uppercase tracking-wider align-middle" title="Przelew wewnętrzny bez drugiej strony — powiąże się automatycznie po zaimportowaniu wyciągu drugiego konta">Do zmapowania</span>` : ''}</td>
                    <td class="p-4 border-b border-slate-100 text-sm">${commentHtml}</td>
                    <td class="p-4 border-b border-slate-100 font-bold ${amountClass} text-right whitespace-nowrap">${amountText}</td>
                    <td class="p-4 border-b border-slate-100 text-center">
                        ${isVirtual ? `
                            <span class="text-xs font-semibold text-indigo-500 bg-indigo-100 px-2 py-1 rounded-md inline-block">Zaplanowana</span>
                        ` : `
                        <div class="flex justify-center items-center gap-1">
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

// Nazwa konta po ID — szuka wśród aktywnych i archiwalnych (do opisu w ostrzeżeniach).
function accountLabelById(accId) {
    const acc = accounts.find(a => a.id == accId) || inactiveAccounts.find(a => a.id == accId);
    return acc ? acc.name : `konto #${accId}`;
}

window.deleteTransaction = async function(id) {
    const tx = transactions.find(t => t.id === id);

    // Przelew wewnętrzny (transakcja lustrzana) = dwie powiązane nogi. Usunięcie
    // jednej usuwa OBIE — ostrzegamy i pokazujemy dokładnie, które transakcje znikną.
    let confirmMsg = 'Czy na pewno chcesz usunąć tę transakcję?';
    if (tx && tx.linked_transaction_id) {
        const mirror = transactions.find(t => t.id === tx.linked_transaction_id);
        const fmt = t => `• ${t.date}  ${t.desc}  ${Number(t.amount).toFixed(2)} PLN  (${accountLabelById(t.account_id)})`;
        const legs = [tx, mirror].filter(Boolean).map(fmt).join('\n');
        confirmMsg = 'UWAGA: to jest przelew wewnętrzny (transakcja lustrzana).\n'
            + 'Usunięcie usunie OBIE powiązane transakcje:\n\n'
            + legs + '\n\nKontynuować?';
    }
    if (!confirm(confirmMsg)) return;

    try {
        const response = await fetch(`/api/transactions/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('Transakcja usunięta.', 'info');
            fetchInitialData();
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
                    ${getCategoryOptionsHtml(s.category, false)}
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
            showToast('Podział został zapisany.');
            closeSplitModal();
            fetchInitialData();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisywania podziału.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem API.', 'error');
    }
}

