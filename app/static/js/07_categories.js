// --- KATEGORIE ---
function getCategoryOptionsHtml(selectedValue = null, byId = false) {
    const expCategories = categories.filter(c => c.type === 'expense');
    const incCategories = categories.filter(c => c.type === 'income');
    const transferCategories = categories.filter(c => c.type === 'transfer');
    const valueAttr = byId ? 'id' : 'name';
    
    let html = `<optgroup label="Wydatki">`;
    expCategories.filter(c => !c.is_system_category).forEach(c => { // Filtrujemy kategorie systemowe
        const sel = (byId ? c.id == selectedValue : c.name === selectedValue) ? 'selected' : '';
        html += `<option value="${escapeHtml(c[valueAttr])}" ${sel}>${escapeHtml(c.name)}</option>`;
    });
    html += `</optgroup><optgroup label="Przychody">`;
    incCategories.filter(c => !c.is_system_category).forEach(c => {
        const sel = (byId ? c.id == selectedValue : c.name === selectedValue) ? 'selected' : '';
        html += `<option value="${escapeHtml(c[valueAttr])}" ${sel}>${escapeHtml(c.name)}</option>`;
    });
    html += `</optgroup>`; // domknij grupę „Przychody" — <optgroup> nie może być zagnieżdżony; bez tego „Transfery" i „Dodaj kategorię" wchłaniały się w „Przychody"
    if (transferCategories.length > 0) {
        html += `<optgroup label="Transfery">`;
        transferCategories.forEach(c => {
            const sel = (byId ? c.id == selectedValue : c.name === selectedValue) ? 'selected' : '';
            html += `<option value="${escapeHtml(c[valueAttr])}" ${sel}>${escapeHtml(c.name)}</option>`;
        });
        html += `</optgroup>`;
    }
    if (!byId) {
        // Gdy nie ma ani jednej kategorii do pokazania, „➕ Dodaj nową kategorię..."
        // byłaby JEDYNĄ opcją — przeglądarka zaznacza ją od razu, więc kliknięcie w nią
        // nie generuje zdarzenia `change` i modal się nie otwiera. Użytkownik, który
        // skasował wszystkie kategorie, nie mógłby dodać pierwszej z formularza
        // transakcji. Placeholder przejmuje domyślne zaznaczenie i odblokowuje wybór.
        // Selecty z własnym placeholderem (rec-category, planned-category, staging)
        // tego problemu nie mają — stąd warunek zamiast bezwarunkowego dopisania.
        const visibleCount = expCategories.filter(c => !c.is_system_category).length
            + incCategories.filter(c => !c.is_system_category).length
            + transferCategories.length;
        if (visibleCount === 0) {
            html = `<option value="">Brak kategorii — dodaj pierwszą</option>` + html;
        }
        html += `<option value="__NEW_CATEGORY__" class="font-bold text-blue-600">➕ Dodaj nową kategorię...</option>`;
    }
    return html;
}

function getSignFromCategoryName(name) {
    const cat = categories.find(c => c.name === name);
    return (cat && cat.type === 'income') ? 1 : -1;
}

function getSignFromCategoryId(id) {
    const cat = categories.find(c => c.id == id);
    return (cat && cat.type === 'income') ? 1 : -1;
}

function updateDestAccountOptions() {
    const sourceAccId = document.getElementById('tx-account').value;
    const destSelect = document.getElementById('tx-dest-account');
    const prevVal = destSelect.value;
    destSelect.innerHTML = '<option value="">Wybierz konto docelowe...</option>' + getDestAccountOptionsHtml(sourceAccId, prevVal);
}

function getDestAccountOptionsHtml(sourceAccountId, selectedId = null) {
    let html = '';
    accounts.filter(a => String(a.id) !== String(sourceAccountId)).forEach(a => {
        const sel = String(a.id) === String(selectedId) ? 'selected' : '';
        html += `<option value="${a.id}" ${sel}>${a.name}</option>`;
    });
    return html;
}

async function resolveOrCreateTransferContractorId(destAccId) {
    const destAcc = accounts.find(a => a.id == destAccId);
    if (!destAcc) throw new Error('Nie znaleziono konta docelowego.');
    const contName = 'Moje konto: ' + destAcc.name;
    let cont = contractors.find(c => c.name === contName);
    if (!cont) {
        const r = await fetch('/api/contractors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: contName, rules: '', category: null })
        });
        if (!r.ok) throw new Error('Błąd podczas tworzenia kontrahenta przelewu.');
        cont = await r.json();
        contractors.push(cont);
    }
    return cont.id;
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
    const plannedSelect = document.getElementById('planned-category');
    const contCatSelect = document.getElementById('cont-cat');
    
    const currentFormVal = formSelect.value;
    formSelect.innerHTML = getCategoryOptionsHtml(currentFormVal, false);

    if(recSelect) {
        const currentRecVal = recSelect.value;
        recSelect.innerHTML = `<option value="">Wybierz kategorię...</option>` + getCategoryOptionsHtml(currentRecVal, true);
    }

    if(plannedSelect) {
        const currentPlannedVal = plannedSelect.value;
        plannedSelect.innerHTML = `<option value="">Wybierz kategorię...</option>` + getCategoryOptionsHtml(currentPlannedVal, true);
    }
    if(contCatSelect) {
        const currentContCat = contCatSelect.value;
        contCatSelect.innerHTML = `<option value="">Brak domyślnej kategorii</option>` + getCategoryOptionsHtml(currentContCat, false);
    }
    
    // renderTransactions(); // Refresh inline selects - This is redundant and called later in fetchInitialData
}

function updateContractorSelects() {
    const recCont = document.getElementById('rec-contractor');
    if(recCont) {
        const curr = recCont.value;
        recCont.innerHTML = `<option value="">Brak kontrahenta</option>` + getContractorOptionsHtml(curr);
    }
    
    const plannedCont = document.getElementById('planned-contractor'); // New
    if(plannedCont) {
        const curr = plannedCont.value;
        plannedCont.innerHTML = `<option value="">Brak kontrahenta</option>` + getContractorOptionsHtml(curr);
    }
    // renderTransactions(); // This is redundant and called later in fetchInitialData
}

// Konto podpowiadane w formularzu transakcji: to z „Widoku konta", o ile jest
// aktywne i wybrane pojedynczo — inaczej konto domyślne.
window.preferredFormAccountId = function() {
    const fromFilter = globalAccountFilter && accounts.find(a => a.id == globalAccountFilter);
    if (fromFilter) return fromFilter.id;
    const defaultAcc = accounts.find(a => a.is_default) || (accounts.length > 0 ? accounts[0] : null);
    return defaultAcc ? defaultAcc.id : null;
}

// Wypełnia listę kont, ZACHOWUJĄC dotychczasowy wybór. Podmiana <option> kasuje
// zaznaczenie, a updateAccountSelects() biegnie po każdej mutacji (fetchInitialData) —
// bez zapamiętania wyboru formularz wracałby do „Wybierz konto..." po każdym zapisie.
// Konto podpowiadamy tylko przy pierwszym wypełnieniu: jeśli użytkownik świadomie
// wybierze pustą pozycję, kolejne odświeżenie nie ma mu jej nadpisywać.
function fillAccountSelect(elementId, optionsHtml, fallbackAccountId) {
    const sel = document.getElementById(elementId);
    if (!sel) return;

    const previous = sel.value;
    sel.innerHTML = optionsHtml;

    if (previous) {
        // Konto usunięte lub dezaktywowane nie ma już swojej <option> — przypisanie
        // po cichu nie zadziała i lista wróci do pustej pozycji. To poprawne.
        sel.value = previous;
    } else if (fallbackAccountId && !sel.dataset.initialized) {
        sel.value = fallbackAccountId;
        sel.dataset.initialized = 'true';
    }
}

function updateAccountSelects() {
    const defaultAcc = accounts.find(a => a.is_default) || (accounts.length > 0 ? accounts[0] : null);
    let html = '<option value="">Wybierz konto...</option>';
    accounts.forEach(a => html += `<option value="${a.id}">${a.name} ${a.bank_name ? `(${a.bank_name})` : ''} ${a.is_default ? '(Główne)' : ''}</option>`);

    fillAccountSelect('tx-account', html, preferredFormAccountId());
    fillAccountSelect('import-account-select', html, defaultAcc ? defaultAcc.id : null);
    fillAccountSelect('rec-account', html, defaultAcc ? defaultAcc.id : null);
    fillAccountSelect('planned-account', html, defaultAcc ? defaultAcc.id : null);

    const globalAcc = document.getElementById('global-account-filter');
    if (globalAcc) {
        let gHtml = '<option value="">Wszystkie konta</option>';
        accounts.forEach(a => gHtml += `<option value="${a.id}">${a.name} ${a.bank_name ? `(${a.bank_name})` : ''} (${a.balance.toFixed(2)} PLN)</option>`);
        // Konta nieaktywne w osobnej grupie — pozwala podejrzeć ich historię transakcji.
        if (inactiveAccounts && inactiveAccounts.length > 0) {
            gHtml += '<optgroup label="Konta nieaktywne">';
            inactiveAccounts.forEach(a => gHtml += `<option value="${a.id}">${a.name} ${a.bank_name ? `(${a.bank_name})` : ''} (nieaktywne)</option>`);
            gHtml += '</optgroup>';
        }
        globalAcc.innerHTML = gHtml;
        globalAcc.value = globalAccountFilter;

        if (!globalAccountFilter && defaultAcc && !globalAcc.dataset.initialized) {
            globalAccountFilter = defaultAcc.id.toString();
            globalAcc.value = globalAccountFilter;
            globalAcc.dataset.initialized = 'true';
        }
    }
}

function renderCategories() {
    const list = document.getElementById('category-list');
    list.innerHTML = '';
    
    categories.forEach(c => {
        const isUsed = transactions.some(t => t.category === c.name || (t.splits && t.splits.some(s => s.category === c.name)));
        let typeLabel;
        if (c.type === 'expense') {
            typeLabel = '<span class="text-rose-500 bg-rose-50 px-2 py-0.5 rounded text-xs font-medium">Wydatek</span>';
        } else if (c.type === 'income') {
            typeLabel = '<span class="text-emerald-500 bg-emerald-50 px-2 py-0.5 rounded text-xs font-medium">Przychód</span>';
        } else { // transfer
            typeLabel = '<span class="text-sky-500 bg-sky-50 px-2 py-0.5 rounded text-xs font-medium">Przelew</span>';
        }
        
        const li = document.createElement('li');
        li.className = 'py-3 px-3 flex justify-between items-center group';
        li.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="font-medium text-slate-700">${escapeHtml(c.name)}</span>
                ${typeLabel}
            </div>
            <button onclick="deleteCategory(${escapeHtml(JSON.stringify(c.name))})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100 ${isUsed ? 'hidden' : ''}" title="Usuń kategorię">
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

