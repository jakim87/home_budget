// --- KONTRAHENCI (SŁOWNIK) ---
function renderContractors() {
    const list = document.getElementById('contractor-list');
    const szukaj = document.getElementById('cont-search');
    const wynik = filtrujKontrahentow(contractors, szukaj ? szukaj.value : '');
    const licznik = document.getElementById('cont-search-count');
    if (licznik) licznik.textContent = wynik.length === contractors.length ? `${contractors.length}` : `${wynik.length} z ${contractors.length}`;
    list.innerHTML = '';
    if (wynik.length === 0) {
        list.innerHTML = '<li class="py-6 text-center text-sm text-slate-400">Brak kontrahentów pasujących do wyszukiwania.</li>';
        return;
    }
    const opcje = categories.map(k => `<option value="${escapeHtml(k.name)}">${escapeHtml(k.name)}</option>`).join('');
    wynik.forEach(c => {
        const li = document.createElement('li');
        li.className = 'py-3 px-3 flex flex-wrap justify-between items-center gap-2 group';
        li.innerHTML = `
            <div class="min-w-0">
                <span class="font-medium text-slate-700 block">${escapeHtml(c.name)}</span>
                <span class="text-xs text-slate-400 block break-all">Reguły: ${escapeHtml(c.rules || '-')}</span>
            </div>
            <div class="flex gap-1 items-center">
                <select onchange="zmienKategorieKontrahenta(${c.id}, this)" class="text-xs p-1.5 border border-slate-200 rounded-md bg-white max-w-[9rem] cursor-pointer" title="Domyślna kategoria kontrahenta" aria-label="Domyślna kategoria: ${escapeHtml(c.name)}">
                    <option value="">Brak kategorii</option>${opcje}
                </select>
                <button onclick="pokazKontrahentaWeWnioskach(${c.id})" class="text-slate-400 hover:text-emerald-700 p-1.5 rounded-md hover:bg-emerald-50 transition-colors" title="Pokaż we Wnioskach (ostatnie 12 miesięcy)">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                </button>
                <button onclick="editContractor(${c.id})" class="text-slate-400 hover:text-blue-600 p-1.5 rounded-md hover:bg-blue-50 transition-colors opacity-0 group-hover:opacity-100" title="Edytuj kontrahenta">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                </button>
                <button onclick="deleteContractor(${c.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-md hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100" title="Usuń kontrahenta">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
        `;
        li.querySelector('select').value = c.default_category_name || '';
        list.appendChild(li);
    });
}

// Zmiana domyślnej kategorii z listy. Stare transakcje kontrahenta zmienia dopiero zgoda
// użytkownika — przez tę samą trasę co edycja zbiorcza (przelewy wewnętrzne pomija).
window.zmienKategorieKontrahenta = async function(id, selectEl) {
    const c = contractors.find(x => x.id === id);
    if (!c) return;
    const kategoria = selectEl.value;
    const wczesniej = c.default_category_name || '';
    if (kategoria === wczesniej) return;
    try {
        const res = await fetch(`/api/contractors/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: c.name, rules: c.rules || '', category: kategoria })
        });
        if (!res.ok) throw new Error();
        contractors[contractors.findIndex(x => x.id === id)] = await res.json();
    } catch (e) {
        selectEl.value = wczesniej;
        showToast('Nie udało się zmienić kategorii kontrahenta.', 'error');
        return;
    }
    showToast('Zmieniono domyślną kategorię kontrahenta.');
    const stare = kategoria ? transactions.filter(t => t.contractor_id === id && t.category !== kategoria) : [];
    if (stare.length && confirm(`Zmienić też kategorię istniejących transakcji tego kontrahenta (${stare.length}) na „${kategoria}”?\nPrzelewy wewnętrzne zostaną pominięte.`)) {
        await przepiszKategorieTransakcji(stare.map(t => t.id), kategoria);
    }
    renderContractors();
    updateContractorSelects();
};

// Porcje po 500 (limit trasy). Przerwana w środku zostawia część zmienioną — ponowna zmiana
// kategorii kontrahenta dokończy resztę, bo transakcje już zmienione są pomijane.
async function przepiszKategorieTransakcji(ids, kategoria) {
    let zmienione = 0, pominiete = 0;
    try {
        for (let i = 0; i < ids.length; i += 500) {
            const res = await fetch('/api/transactions/bulk/category', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids.slice(i, i + 500), category: kategoria })
            });
            const wynik = await res.json();
            if (!res.ok) throw new Error(typeof wynik.error === 'string' ? wynik.error : '');
            zmienione += wynik.zmienione; pominiete += wynik.pominiete_przelewy || 0;
        }
    } catch (e) {
        showToast(`Zmieniono ${zmienione} z ${ids.length} transakcji${e.message ? ': ' + e.message : '.'}`, 'error');
        await fetchInitialData();
        return;
    }
    showToast(`Zmieniono kategorię transakcji: ${zmienione}.` + (pominiete ? ` Pominięto przelewy wewnętrzne: ${pominiete}.` : ''));
    await fetchInitialData();
}

window.pokazKontrahentaWeWnioskach = function(id) { wnPokazKontrahenta(id); };

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
    const rawCategory = document.getElementById('cont-cat').value;
    const category = (rawCategory && rawCategory !== '__NEW_CATEGORY__') ? rawCategory : '';
    
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
// Jedno dopasowanie kontrahenta do tekstu dla wszystkich formularzy (edycja wiersza,
// cykliczne, szybki wpis): nazwa (min. 3 znaki, żeby uniknąć losowych trafień) albo
// reguła (min. 2) zawarta w tekście; pierwsze trafienie w kolejności słownika.
// Bez rozróżniania wielkości liter i polskich znaków.
function dopasujKontrahenta(tekst) {
    if (!tekst || tekst.length < 2) return null;
    const t = normalizujTekst(tekst);
    return contractors.find(c =>
        (c.name && c.name.length >= 3 && t.includes(normalizujTekst(c.name)))
        || (c.rules || '').split(',').map(r => normalizujTekst(r.trim())).some(r => r.length >= 2 && t.includes(r))
    ) || null;
}

window.handleAutoFill = function(textValue, contSelectEl, catSelectEl) {
    const c = dopasujKontrahenta(textValue);
    if (!c) return;
    if (contSelectEl && contSelectEl.value != c.id) {
        contSelectEl.value = c.id;
        const displayEl = document.getElementById(contSelectEl.id + '-input');
        if (displayEl) displayEl.value = c.name;
    }
    // Select kategorii operuje nazwami, nie ID. Ręczny wybór użytkownika
    // w formularzu transakcji (dataset.userSet) ma pierwszeństwo.
    if (catSelectEl && c.default_category_name && !catSelectEl.dataset.userSet
        && catSelectEl.value != c.default_category_name) {
        catSelectEl.value = c.default_category_name;
    }
}

