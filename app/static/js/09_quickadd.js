// --- SZYBKIE DODAWANIE W LOCIE ---
let currentQuickAddSelect = null;
let currentSuggestionStagingId = null;
let currentEditingContractorId = null;

function lookupExistingContractor() {
    const name = document.getElementById('quick-cont-name-inp').value.trim().toLowerCase();
    const found = name ? contractors.find(c => c.name.toLowerCase() === name) : null;
    const notice = document.getElementById('quick-cont-existing-notice');
    if (found) {
        document.getElementById('quick-cont-rules-inp').value = found.rules || '';
        const qCatSelect = document.getElementById('quick-cont-cat-select');
        if (qCatSelect && found.default_category_name) qCatSelect.value = found.default_category_name;
        currentEditingContractorId = found.id;
        if (notice) notice.classList.remove('hidden');
    } else {
        currentEditingContractorId = null;
        if (notice) notice.classList.add('hidden');
    }
}

document.getElementById('quick-cont-name-inp').addEventListener('input', lookupExistingContractor);

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

window.openQuickContractorModal = function(prefillName = '', suggestionStagingId = null) {
    document.getElementById('quick-cont-name-inp').value = prefillName;
    document.getElementById('quick-cont-rules-inp').value = '';
    currentSuggestionStagingId = suggestionStagingId;
    currentEditingContractorId = null;
    document.getElementById('quick-cont-existing-notice').classList.add('hidden');

    const qCatSelect = document.getElementById('quick-cont-cat-select');
    qCatSelect.innerHTML = `<option value="">Brak domyślnej kategorii</option>` + getCategoryOptionsHtml(null, false);

    document.getElementById('quick-contractor-modal').classList.remove('hidden');
    document.getElementById('quick-contractor-modal').classList.add('flex');
    if (prefillName) lookupExistingContractor();
};

window.closeQuickContractorModal = function() {
    document.getElementById('quick-contractor-modal').classList.add('hidden');
    document.getElementById('quick-contractor-modal').classList.remove('flex');
    if (currentQuickAddSelect && currentQuickAddSelect.value === '__NEW_CONTRACTOR__') {
        currentQuickAddSelect.value = '';
    }
    currentQuickAddSelect = null;
    currentSuggestionStagingId = null;
    currentEditingContractorId = null;
    document.getElementById('quick-cont-existing-notice').classList.add('hidden');
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

            if (selectId === 'quick-cont-cat-select') {
                const qCatSelect = document.getElementById('quick-cont-cat-select');
                qCatSelect.innerHTML = `<option value="">Brak domyślnej kategorii</option>` + getCategoryOptionsHtml(null, false);
                qCatSelect.value = saved.name;
            } else if (selectId) {
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
    const rawCategory = document.getElementById('quick-cont-cat-select').value;
    const category = (rawCategory && rawCategory !== '__NEW_CATEGORY__') ? rawCategory : '';

    const isUpdate = !!currentEditingContractorId;
    const method = isUpdate ? 'PUT' : 'POST';
    const url = isUpdate ? `/api/contractors/${currentEditingContractorId}` : '/api/contractors';

    try {
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, rules, category })
        });
        if (response.ok) {
            const saved = await response.json();

            if (isUpdate) {
                const idx = contractors.findIndex(c => c.id === saved.id);
                if (idx >= 0) contractors[idx] = saved;
            } else {
                contractors.push(saved);
            }

            if (currentSuggestionStagingId) {
                const item = pendingStaging.find(t => t.id === currentSuggestionStagingId);
                if (item) {
                    item.proposed_contractor_id = saved.id;
                    item.suggested_contractor_name = '';
                    if (saved.default_category_name) item.proposed_category = saved.default_category_name;
                }
            } else {
                const selectId = currentQuickAddSelect ? currentQuickAddSelect.id : null;
                if (selectId && selectId.startsWith('staging-cont-')) {
                    const stgId = parseInt(selectId.replace('staging-cont-', ''));
                    updateStagingLocalState(stgId, 'proposed_contractor_id', saved.id);
                }
                if (selectId) {
                    const el = document.getElementById(selectId);
                    if (el) el.value = saved.id;
                    const displayEl = document.getElementById(selectId + '-input');
                    if (displayEl) displayEl.value = saved.name;
                }
            }

            updateContractorSelects();
            renderContractors();
            renderStaging();

            closeQuickContractorModal();
            showToast(isUpdate ? `Zaktualizowano kontrahenta: ${name}` : `Dodano kontrahenta: ${name}`);
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd zapisu', 'error');
        }
    } catch(e) { showToast('Błąd połączenia', 'error'); }
});

