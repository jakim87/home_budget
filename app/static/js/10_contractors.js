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
                const displayEl = document.getElementById(contSelectEl.id + '-input');
                if (displayEl) displayEl.value = c.name;
            }
            if (catSelectEl && c.default_category_id && catSelectEl.value != c.default_category_id) {
                catSelectEl.value = c.default_category_id;
            }
            return; // Zatrzymujemy szukanie na pierwszym dopasowaniu
        }
    }
}

