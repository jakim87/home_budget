// --- COMBOBOX KONTRAHENTA (FORMULARZ TRANSAKCJI) ---
function initContractorCombobox() {
    const input = document.getElementById('tx-contractor-input');
    const hidden = document.getElementById('tx-contractor');
    const dropdown = document.getElementById('tx-contractor-dropdown');
    if (!input || !hidden || !dropdown) return;

    function buildDropdown(filter) {
        const q = (filter || '').toLowerCase();
        const matched = q
            ? contractors.filter(c => c.name.toLowerCase().includes(q))
            : contractors;

        let html = '';
        if (!q) {
            html += `<li data-id="" data-name="" class="px-3 py-2 hover:bg-slate-100 cursor-pointer text-slate-400 italic">Brak kontrahenta</li>`;
        }
        matched.forEach(c => {
            const escaped = c.name.replace(/"/g, '&quot;');
            html += `<li data-id="${c.id}" data-name="${escaped}" class="px-3 py-2 hover:bg-blue-50 cursor-pointer text-slate-700">${c.name}</li>`;
        });
        if (matched.length === 0 && q) {
            html += `<li class="px-3 py-2 text-slate-400 italic select-none">Brak wyników</li>`;
        }
        html += `<li data-id="__NEW__" class="px-3 py-2 hover:bg-emerald-50 cursor-pointer text-emerald-700 font-medium border-t border-slate-100 mt-1">➕ Dodaj nowego kontrahenta</li>`;
        dropdown.innerHTML = html;
        dropdown.classList.remove('hidden');
    }

    input.addEventListener('focus', () => buildDropdown(input.value));
    input.addEventListener('input', () => buildDropdown(input.value));
    input.addEventListener('blur', () => setTimeout(() => dropdown.classList.add('hidden'), 150));

    dropdown.addEventListener('mousedown', function(e) {
        e.preventDefault();
        const li = e.target.closest('li[data-id]');
        if (!li) return;
        const id = li.dataset.id;
        if (id === '__NEW__') {
            currentQuickAddSelect = { id: 'tx-contractor' };
            openQuickContractorModal();
            dropdown.classList.add('hidden');
        } else {
            hidden.value = id;
            input.value = li.dataset.name || '';
            dropdown.classList.add('hidden');
        }
    });
}

