// --- IMPORT WYCIĄGÓW ---
// Wgrywanie na stronie zakładki Import (bez osobnego okna). Każdy plik trafia do
// poczekalni poniżej; wynik pokazujemy przy pliku, nie tylko w komunikacie.
const fileInput = document.getElementById('csvFileInput');
const folderInput = document.getElementById('folderInput');
const pickFilesBtn = document.getElementById('pickFilesBtn');
const importDropzone = document.getElementById('import-dropzone');
const importProgress = document.getElementById('import-progress');
const importResults = document.getElementById('import-results');
const importErrorMsg = document.getElementById('importError');

const IMPORT_EXTENSIONS = ['.csv', '.html', '.htm', '.pdf'];
let importTrwa = false;

function _supportedFile(f) {
    const n = f.name.toLowerCase();
    return IMPORT_EXTENSIONS.some(ext => n.endsWith(ext));
}

pickFilesBtn.addEventListener('click', () => fileInput.click());
document.getElementById('pickFolderBtn').addEventListener('click', () => folderInput.click());

[fileInput, folderInput].forEach(input => input.addEventListener('change', () => {
    importujPliki(Array.from(input.files));
    input.value = '';  // ten sam plik wybrany ponownie też ma wywołać „change"
}));

['dragenter', 'dragover'].forEach(ev => importDropzone.addEventListener(ev, e => {
    e.preventDefault();
    importDropzone.classList.add('border-blue-400', 'bg-blue-50');
}));
['dragleave', 'drop'].forEach(ev => importDropzone.addEventListener(ev, e => {
    e.preventDefault();
    importDropzone.classList.remove('border-blue-400', 'bg-blue-50');
}));
importDropzone.addEventListener('drop', e => importujPliki(Array.from(e.dataTransfer.files)));

async function importujPliki(wybrane) {
    if (importTrwa) return;
    importErrorMsg.classList.add('hidden');
    const files = wybrane.filter(_supportedFile);
    if (files.length === 0) {
        showImportError(wybrane.length
            ? 'Żaden z plików nie jest wyciągiem w obsługiwanym formacie (.csv, .html, .pdf).'
            : 'Wybierz plik(i) z wyciągami.');
        return;
    }

    // Ustawienia ręczne działają tylko przy jednym pliku: przy kilku konto rozpoznaje
    // się po numerze rachunku, a plik bez numeru zapyta o konto na liście wyników.
    const jeden = files.length === 1;
    const bank = jeden ? (document.getElementById('import-bank-select').value || 'auto') : 'auto';
    const konto = jeden ? document.getElementById('import-account-select').value : '';

    importTrwa = true;
    pickFilesBtn.disabled = true;
    importResults.innerHTML = '';
    importResults.classList.remove('hidden');
    let ok = 0;
    for (let i = 0; i < files.length; i++) {
        importProgress.textContent = `Importowanie… ${i + 1}/${files.length}`;
        importProgress.classList.remove('hidden');
        const wiersz = document.createElement('div');
        importResults.appendChild(wiersz);
        if (await wgrajPlik(files[i], bank, konto, wiersz)) ok++;
    }
    importProgress.classList.add('hidden');
    pickFilesBtn.disabled = false;
    importTrwa = false;

    const bledy = files.length - ok;
    showToast(bledy === 0
        ? `Zaimportowano ${ok} ${odmiana(ok, ['plik', 'pliki', 'plików'])} — operacje czekają poniżej.`
        : `Zaimportowano ${ok}, błędy: ${bledy} — szczegóły na liście.`,
        bledy === 0 ? 'success' : 'error');
    if (ok) odswiezPoImporcie();
}

function odswiezPoImporcie() {
    fetchPendingStaging();
    // Import mógł założyć kontrahenta przelewu („Moje konto: X”) — bez odświeżenia
    // zatwierdzanie szukałoby go w starej liście.
    fetchInitialData({ skipStagingRefresh: true });
}

// Wgrywa jeden plik i opisuje wynik w `wiersz`. Zwraca true przy sukcesie.
async function wgrajPlik(file, bank, konto, wiersz) {
    wiersz.className = 'flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-2';
    wiersz.innerHTML = `<span class="truncate text-slate-700 font-medium">${escapeHtml(file.name)}</span><span class="text-slate-400">…</span>`;
    const status = wiersz.lastElementChild;

    const fd = new FormData();
    fd.append('file', file);
    if (konto) fd.append('account_id', konto);
    try {
        const resp = await fetch(`/api/import/${bank}`, { method: 'POST', body: fd });
        const r = await resp.json();
        if (resp.ok) {
            status.className = `text-xs font-medium text-right ${r.overlap_warning ? 'text-amber-600' : 'text-emerald-600'}`;
            status.textContent = opisWynikuImportu(r);
            if (r.overlap_warning) status.title = r.overlap_warning;
            return true;
        }
        status.className = 'text-rose-600 text-xs font-medium text-right';
        status.textContent = `✗ ${r.error || 'błąd'}`;
        // Plik bez numeru rachunku: przy kilku plikach naraz to jedyne miejsce,
        // w którym da się wskazać jego konto.
        if (r.needs_account) dodajWyborKonta(file, bank, wiersz);
    } catch (_) {
        status.className = 'text-rose-600 text-xs font-medium';
        status.textContent = '✗ błąd połączenia';
    }
    return false;
}

// „→ Moje ING i Wakacje · 13 operacji, 2 z kont spoza aplikacji pominięte"
function opisWynikuImportu(r) {
    const konta = r.resolved_account ? [r.resolved_account.name]
        : (r.csv_accounts || []).filter(a => a.matched).map(a => a.account_name);
    let opis = `${r.overlap_warning ? '⚠' : '✓'} ${konta.length ? `→ ${konta.join(' i ')} · ` : ''}${r.count} ${odmiana(r.count, ['operacja', 'operacje', 'operacji'])}`;
    if (r.skipped_count) opis += `, ${r.skipped_count} z kont spoza aplikacji pominięte`;
    return opis;
}

function dodajWyborKonta(file, bank, wiersz) {
    const box = document.createElement('div');
    box.className = 'w-full flex flex-wrap items-center gap-2';
    box.innerHTML = `
        <label class="text-xs text-slate-600">Konto tego pliku:
            <select class="ml-1 p-1 border border-slate-300 rounded text-xs bg-white">
                <option value="">Wybierz konto…</option>
                ${accounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)}${a.bank_name ? ` (${escapeHtml(a.bank_name)})` : ''}</option>`).join('')}
            </select>
        </label>
        <button type="button" class="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium">Wgraj ponownie</button>`;
    const select = box.querySelector('select');
    box.querySelector('button').addEventListener('click', async () => {
        if (!select.value) {
            showToast('Wybierz konto, na które ma trafić ten plik.', 'error');
            return;
        }
        if (await wgrajPlik(file, bank, select.value, wiersz)) odswiezPoImporcie();
    });
    wiersz.appendChild(box);
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

