// --- IMPORT TRANSAKCJI ---
const openImportModalBtn = document.getElementById('openImportModalBtn');
const closeImportModalBtn = document.getElementById('closeImportModalBtn');
const closeImportModalBtnAlt = document.getElementById('closeImportModalBtnAlt');
const importModal = document.getElementById('import-modal');
const importForm = document.getElementById('importForm');
const fileInput = document.getElementById('csvFileInput');
const folderInput = document.getElementById('folderInput');
const pickFolderBtn = document.getElementById('pickFolderBtn');
const pickedFilesInfo = document.getElementById('pickedFilesInfo');
const importResults = document.getElementById('import-results');
const importErrorMsg = document.getElementById('importError');
const importBtnText = document.getElementById('importBtnText');
const importBtnLoader = document.getElementById('importBtnLoader');
const submitImportBtn = document.getElementById('submitImportBtn');

const IMPORT_EXTENSIONS = ['.csv', '.html', '.htm', '.pdf'];
// Pliki wybrane przez picker folderu (fileInput ma własny stan w DOM)
let folderPickedFiles = null;

function _supportedFile(f) {
    const n = f.name.toLowerCase();
    return IMPORT_EXTENSIONS.some(ext => n.endsWith(ext));
}

function _selectedImportFiles() {
    if (folderPickedFiles && folderPickedFiles.length) return folderPickedFiles;
    return Array.from(fileInput.files).filter(_supportedFile);
}

pickFolderBtn.addEventListener('click', () => folderInput.click());

folderInput.addEventListener('change', () => {
    folderPickedFiles = Array.from(folderInput.files).filter(_supportedFile);
    fileInput.value = '';
    pickedFilesInfo.textContent = folderPickedFiles.length
        ? `Wybrano ${folderPickedFiles.length} plików z folderu`
        : 'Folder nie zawiera obsługiwanych plików';
});

fileInput.addEventListener('change', () => {
    folderPickedFiles = null;
    const n = fileInput.files.length;
    pickedFilesInfo.textContent = n > 1 ? `Wybrano ${n} plików` : '';
});

function openImportModal() {
    importModal.classList.remove('hidden');
    importModal.classList.add('flex');
    importErrorMsg.classList.add('hidden');
    importResults.classList.add('hidden');
    importResults.innerHTML = '';
    pickedFilesInfo.textContent = '';
    folderPickedFiles = null;
    fileInput.value = '';
    folderInput.value = '';
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

    const files = _selectedImportFiles();
    if (files.length === 0) {
        showImportError('Proszę wybrać plik(i) lub folder z wyciągami.');
        return;
    }
    if (files.length === 1) {
        await importSingleFile(files[0]);
    } else {
        await importManyFiles(files);
    }
});

async function importSingleFile(file) {
    const accId = document.getElementById('import-account-select').value;
    const bank = document.getElementById('import-bank-select').value || 'auto';

    const formData = new FormData();
    formData.append('file', file);
    if (accId) formData.append('account_id', accId);

    setImportLoadingState(true);
    try {
        const response = await fetch(`/api/import/${bank}`, { method: 'POST', body: formData });
        const result = await response.json();

        if (response.ok) {
            let msg = result.message;
            if (result.detected) {
                msg += ` Wykryto: ${result.detected.bank.toUpperCase()} (${result.detected.format.toUpperCase()}).`;
            }
            if (result.resolved_account) {
                msg += ` Konto: ${result.resolved_account.name}.`;
            }
            if (result.csv_accounts && result.csv_accounts.length > 0) {
                const matched = result.csv_accounts.filter(a => a.matched).map(a => a.account_name);
                const unknown = result.csv_accounts.filter(a => !a.matched).map(a => a.csv_name);
                if (matched.length) msg += ` Wykryte konta: ${matched.join(', ')}.`;
                if (unknown.length) msg += ` Nieznane konta (pominięte): ${unknown.join(', ')}.`;
            }
            if (result.skipped_count) msg += ` Pominięto ${result.skipped_count} transakcji z innych kont.`;
            if (result.overlap_warning) {
                showToast(`Sukces! ${msg}`, 'success');
                showToast(result.overlap_warning, 'info');
            } else {
                showToast(`Sukces! ${msg}`, 'success');
            }
            closeImportModal();
            fetchPendingStaging();
        } else {
            showImportError(result.error || 'Wystąpił błąd serwera podczas importu pliku.');
        }
    } catch (error) {
        showImportError('Błąd połączenia z serwerem. Sprawdź, czy aplikacja jest uruchomiona.');
    } finally {
        setImportLoadingState(false);
    }
}

async function importManyFiles(files) {
    // Wiele plików: zawsze auto-detekcja, konto rozpoznawane po IBAN z wyciągu
    // po stronie serwera (wybór z dropdowna jest ignorowany — patrz opis w modalu).
    importResults.innerHTML = '';
    importResults.classList.remove('hidden');
    setImportLoadingState(true);

    let okCount = 0, errCount = 0;
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        importBtnText.textContent = `Importowanie… ${i + 1}/${files.length}`;

        const row = document.createElement('div');
        row.className = 'flex items-center justify-between gap-2 px-3 py-2';
        row.innerHTML = `<span class="truncate text-slate-700">${escapeHtml(file.name)}</span><span class="shrink-0 text-slate-400">…</span>`;
        importResults.appendChild(row);
        const statusEl = row.lastElementChild;

        try {
            const fd = new FormData();
            fd.append('file', file);
            const resp = await fetch('/api/import/auto', { method: 'POST', body: fd });
            const result = await resp.json();
            if (resp.ok) {
                okCount++;
                const det = result.detected ? `${result.detected.bank.toUpperCase()}/${result.detected.format.toUpperCase()}` : '';
                const acc = result.resolved_account ? ` → ${result.resolved_account.name}` : '';
                statusEl.className = 'shrink-0 text-emerald-600 text-xs font-medium';
                statusEl.textContent = `✓ ${result.count} tx ${det}${acc}`;
                if (result.overlap_warning) {
                    statusEl.className = 'shrink-0 text-amber-600 text-xs font-medium';
                    statusEl.textContent = `⚠ ${result.count} tx ${det}${acc}`;
                    statusEl.title = result.overlap_warning;
                }
            } else {
                errCount++;
                statusEl.className = 'shrink-0 text-rose-600 text-xs font-medium max-w-[55%] text-right';
                statusEl.textContent = `✗ ${result.error || 'błąd'}`;
                statusEl.title = result.error || '';
            }
        } catch (_) {
            errCount++;
            statusEl.className = 'shrink-0 text-rose-600 text-xs font-medium';
            statusEl.textContent = '✗ błąd połączenia';
        }
    }

    setImportLoadingState(false);
    showToast(errCount === 0
        ? `Zaimportowano ${okCount} plików.`
        : `Zaimportowano ${okCount}, błędy: ${errCount} — szczegóły na liście.`,
        errCount === 0 ? 'success' : 'error');
    fetchPendingStaging();
    fetchInitialData({ skipStagingRefresh: true });
}

const toggleImportHistoryBtn = document.getElementById('toggleImportHistoryBtn');
const importHistoryBox = document.getElementById('import-history');
const importHistoryChevron = document.getElementById('importHistoryChevron');

toggleImportHistoryBtn.addEventListener('click', async () => {
    const willShow = importHistoryBox.classList.contains('hidden');
    importHistoryBox.classList.toggle('hidden', !willShow);
    importHistoryChevron.style.transform = willShow ? 'rotate(90deg)' : '';
    if (willShow) await renderImportHistory();
});

async function renderImportHistory() {
    importHistoryBox.innerHTML = '<div class="px-3 py-2 text-slate-400">Wczytywanie…</div>';
    try {
        const resp = await fetch('/api/import/history');
        if (!resp.ok) throw new Error('fetch failed');
        const rows = await resp.json();
        if (rows.length === 0) {
            importHistoryBox.innerHTML = '<div class="px-3 py-2 text-slate-400">Brak zaimportowanych wyciągów.</div>';
            return;
        }
        importHistoryBox.innerHTML = rows.map(r => {
            const okres = (r.period_start && r.period_end)
                ? `${r.period_start} – ${r.period_end}`
                : 'brak zakresu';
            const konto = r.account_name || 'konto nieznane';
            return `<div class="px-3 py-2">
                <div class="flex items-center justify-between gap-2">
                    <span class="font-medium text-slate-700 truncate">${escapeHtml(konto)}</span>
                    <span class="shrink-0 text-slate-500">${r.transaction_count} tx</span>
                </div>
                <div class="flex items-center justify-between gap-2 mt-0.5 text-slate-500">
                    <span class="truncate" title="${escapeHtml(r.filename)}">${escapeHtml(r.filename)}</span>
                    <span class="shrink-0 uppercase text-[10px] tracking-wide text-slate-400">${escapeHtml(r.bank)}/${escapeHtml(r.file_format)}</span>
                </div>
                <div class="text-slate-400 mt-0.5">${okres} · wgrano ${r.imported_at || ''}</div>
            </div>`;
        }).join('');
    } catch (e) {
        importHistoryBox.innerHTML = '<div class="px-3 py-2 text-rose-500">Nie udało się wczytać historii.</div>';
    }
}

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

