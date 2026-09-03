// --- EDYCJA ZBIORCZA TRANSAKCJI ---
//
// Zaznaczenie żyje w pamięci przeglądarki i jest kasowane przy każdym
// przerysowaniu tabeli (zmiana miesiąca, filtr konta, odświeżenie danych).
// Powód: operacja zbiorcza ma dotyczyć tego, co użytkownik widzi. Zaznaczenie
// przeżywające zmianę miesiąca oznaczałoby usuwanie wierszy, których nie ma
// na ekranie.
//
// Obie operacje idą JEDNYM żądaniem na osobne trasy /api/transactions/bulk/*,
// a nie pętlą po pojedynczych endpointach — serwer domyka je jednym commitem,
// więc albo zmienia się cała paczka, albo nic.

const selectedTxIds = new Set();

/** Zaznacza/odznacza jeden wiersz. */
window.toggleTxSelection = function(id) {
    if (selectedTxIds.has(id)) selectedTxIds.delete(id);
    else selectedTxIds.add(id);
    updateBulkBar();
};

/** Zaznacz / odznacz wszystko, co widoczne (checkbox w nagłówku tabeli). */
window.toggleSelectAllTx = function(checked) {
    document.querySelectorAll('.tx-select-check').forEach(chk => {
        chk.checked = checked;
        const id = parseInt(chk.value);
        if (checked) selectedTxIds.add(id);
        else selectedTxIds.delete(id);
    });
    updateBulkBar();
};

/** Czyści zaznaczenie — wołane także przy każdym renderTransactions(). */
window.clearTxSelection = function() {
    selectedTxIds.clear();
    const all = document.getElementById('tx-select-all');
    if (all) { all.checked = false; all.indeterminate = false; }
    updateBulkBar();
};

/** Pokazuje pasek akcji i uzupełnia licznik oraz listę kategorii. */
function updateBulkBar() {
    const bar = document.getElementById('tx-bulk-bar');
    if (!bar) return;

    const n = selectedTxIds.size;
    bar.classList.toggle('hidden', n === 0);
    if (n === 0) return;

    const opsLabel = n === 1 ? 'transakcja'
        : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'transakcje' : 'transakcji');
    document.getElementById('tx-bulk-count').textContent = `Zaznaczono ${n} ${opsLabel}`;

    // Checkbox nagłówka: pełny przy komplecie, „częściowy" przy podzbiorze.
    const wszystkie = document.querySelectorAll('.tx-select-check').length;
    const all = document.getElementById('tx-select-all');
    if (all) {
        all.checked = n > 0 && n === wszystkie;
        all.indeterminate = n > 0 && n < wszystkie;
    }

    const select = document.getElementById('tx-bulk-category');
    if (select && !select.dataset.filled) {
        // Kategorie typu 'transfer' są pominięte: przelew wewnętrzny wymaga
        // wskazania konta docelowego, więc nie da się go nadać zbiorczo.
        select.innerHTML = '<option value="">— wybierz kategorię —</option>' +
            categories
                .filter(c => c.type !== 'transfer')
                .map(c => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`)
                .join('');
        select.dataset.filled = '1';
    }
}
window.updateBulkBar = updateBulkBar;

window.bulkChangeCategory = async function() {
    const select = document.getElementById('tx-bulk-category');
    const kategoria = select?.value;
    if (!kategoria) {
        showToast('Najpierw wybierz kategorię.', 'error');
        return;
    }
    const ids = [...selectedTxIds];
    if (ids.length === 0) return;

    try {
        const response = await fetch('/api/transactions/bulk/category', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids, category: kategoria })
        });
        const wynik = await response.json();

        if (!response.ok) {
            showToast(typeof wynik.error === 'string' ? wynik.error : 'Nie udało się zmienić kategorii.', 'error');
            return;
        }

        // Pominięte przelewy MUSZĄ być widoczne w komunikacie — inaczej
        // użytkownik zobaczy tylko część zmian i uzna, że coś się zepsuło.
        let msg = `Zmieniono kategorię: ${wynik.zmienione}.`;
        if (wynik.pominiete_przelewy > 0) {
            msg += ` Pominięto przelewy wewnętrzne: ${wynik.pominiete_przelewy}.`;
        }
        showToast(msg, 'success');
        clearTxSelection();
        fetchInitialData();
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem API.', 'error');
    }
};

window.bulkDeleteSelected = async function() {
    const ids = [...selectedTxIds];
    if (ids.length === 0) return;

    // Zaznaczona noga przelewu pociągnie za sobą drugą, także tę spoza
    // zaznaczenia. Liczymy je z góry, żeby ostrzec PRZED usunięciem, a nie
    // dopiero w podsumowaniu.
    const dodatkowe = new Set();
    ids.forEach(id => {
        const tx = transactions.find(t => t.id === id);
        if (tx?.linked_transaction_id && !selectedTxIds.has(tx.linked_transaction_id)) {
            dodatkowe.add(tx.linked_transaction_id);
        }
    });

    let msg = `Czy na pewno usunąć zaznaczone transakcje (${ids.length})?`;
    if (dodatkowe.size > 0) {
        msg = `UWAGA: wśród zaznaczonych są przelewy wewnętrzne.\n`
            + `Razem z nimi zniknie ${dodatkowe.size} powiązanych transakcji na drugim koncie,\n`
            + `których nie zaznaczyłeś — łącznie ${ids.length + dodatkowe.size}.\n\nKontynuować?`;
    }
    if (!confirm(msg)) return;

    try {
        const response = await fetch('/api/transactions/bulk/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        const wynik = await response.json();

        if (!response.ok) {
            showToast(typeof wynik.error === 'string' ? wynik.error : 'Nie udało się usunąć transakcji.', 'error');
            return;
        }

        let info = `Usunięto ${wynik.usuniete} transakcji.`;
        if (wynik.drugie_nogi > 0) {
            info += ` W tym ${wynik.drugie_nogi} drugich nóg przelewów.`;
        }
        showToast(info, 'info');
        clearTxSelection();
        fetchInitialData();
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z serwerem API.', 'error');
    }
};
