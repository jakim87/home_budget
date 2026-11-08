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
    importResults.innerHTML = '<div id="import-paczka" class="px-3 py-2 bg-slate-50 text-xs"></div>';
    importResults.classList.remove('hidden');
    paczkaImportu = files.map(f => ({ nazwa: f.name, ok: null }));
    kontaBezWyciaguPaczki = [];
    let ok = 0;
    for (let i = 0; i < files.length; i++) {
        importProgress.textContent = `Importowanie… ${i + 1}/${files.length}`;
        importProgress.classList.remove('hidden');
        const wiersz = document.createElement('div');
        importResults.appendChild(wiersz);
        if (await wgrajPlik(files[i], bank, konto, wiersz, paczkaImportu[i])) ok++;
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
    await odswiezKontaBezWyciagu();
}

// Wyniki bieżącej paczki (po jednym na plik, w kolejności wgrywania) — z nich
// powstaje podsumowanie nad listą. „Wgraj ponownie" uzupełnia wpis swojego pliku.
let paczkaImportu = [];
let kontaBezWyciaguPaczki = [];

function odswiezPoImporcie() {
    fetchPendingStaging();
    // Import mógł założyć kontrahenta przelewu („Moje konto: X”) — bez odświeżenia
    // zatwierdzanie szukałoby go w starej liście.
    fetchInitialData({ skipStagingRefresh: true });
}

// Wgrywa jeden plik i opisuje wynik w `wiersz`. Zwraca true przy sukcesie.
async function wgrajPlik(file, bank, konto, wiersz, wynik) {
    wiersz.className = 'px-3 py-2';
    wiersz.innerHTML = `<div class="flex items-center justify-between gap-3"><span class="truncate text-slate-700 font-medium">${escapeHtml(file.name)}</span><span class="text-slate-400">…</span></div>`;

    const fd = new FormData();
    fd.append('file', file);
    if (konto) fd.append('account_id', konto);
    let r;
    try {
        const resp = await fetch(`/api/import/${bank}`, { method: 'POST', body: fd });
        r = { ...(await resp.json()), ok: resp.ok };
    } catch (_) {
        r = { ok: false, error: 'błąd połączenia' };
    }
    Object.assign(wynik, { ok: r.ok, summary: r.summary || null });
    wiersz.innerHTML = kartaPlikuHtml(file.name, r, godzinaTeraz());
    // Plik bez numeru rachunku: przy kilku plikach naraz to jedyne miejsce,
    // w którym da się wskazać jego konto.
    if (!r.ok && r.needs_account) dodajWyborKonta(file, bank, wiersz, wynik);
    renderPodsumowaniePaczki();
    return r.ok;
}

function godzinaTeraz() {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

const NAZWY_BANKOW = { ing: 'ING', mbank: 'mBank', pekao: 'Pekao', millennium: 'Millennium', revolut: 'Revolut' };

// „2026-10-01" → „01.10.2026"
function dataPL(iso) {
    return iso ? iso.split('-').reverse().join('.') : '';
}

// „01.10–31.10.2026"; ten sam dzień raz, różne lata w pełnej postaci.
function zakresPL(od, doDnia) {
    if (!od) return 'brak dat';
    if (od === doDnia) return dataPL(od);
    return od.slice(0, 4) === doDnia.slice(0, 4)
        ? `${dataPL(od).slice(0, 5)}–${dataPL(doDnia)}`
        : `${dataPL(od)}–${dataPL(doDnia)}`;
}

// Karta jednego pliku: nazwa, bank/format, godzina, konta jedno pod drugim,
// liczby z pliku i ostrzeżenie o nakładaniu się okresów.
function kartaPlikuHtml(nazwa, r, czas) {
    const s = r.summary;
    const etykieta = [s ? `${NAZWY_BANKOW[s.bank] || s.bank} · ${String(s.format).toUpperCase()}` : '', czas]
        .filter(Boolean).join(' · ');
    const naglowek = `<div class="flex items-center justify-between gap-3">
        <span class="truncate font-medium text-slate-700" title="${escapeHtml(nazwa)}"><span class="${r.ok ? 'text-emerald-600' : 'text-rose-600'}">${r.ok ? '✓' : '✗'}</span> ${escapeHtml(nazwa)}</span>
        <span class="shrink-0 text-[11px] text-slate-500">${escapeHtml(etykieta)}</span>
    </div>`;
    if (!r.ok || !s) {
        return naglowek + (r.ok ? '' : `<div class="text-xs text-rose-600 mt-1">${escapeHtml(r.error || 'błąd')}</div>`);
    }

    const konta = s.accounts.map(a => `<div class="flex items-baseline gap-3 text-xs">
            <span class="flex-1 min-w-0 truncate text-slate-700">${escapeHtml(a.account_id ? nazwaKonta(a.account_id) : 'Konto nieznane')}</span>
            <span class="shrink-0 text-slate-500">${zakresPL(a.from, a.to)}</span>
            <span class="shrink-0 w-24 text-right text-slate-500">${a.count} ${odmiana(a.count, ['operacja', 'operacje', 'operacji'])}</span>
        </div>`).join('');
    const liczby = [`w pliku ${s.rows_in_file}`, `nowych ${s.saved}`];
    if (s.duplicates) liczby.push(`duplikaty ${s.duplicates}`);
    if (s.skipped_foreign) liczby.push(`spoza aplikacji ${s.skipped_foreign}`);
    const ostrzezenie = r.overlap_warning
        ? `<div class="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 mt-1">⚠ ${escapeHtml(r.overlap_warning)}</div>` : '';
    return naglowek + `<div class="mt-1 space-y-0.5">${konta}</div>
        <div class="text-[11px] text-slate-500 mt-1">${liczby.join(' · ')}</div>${ostrzezenie}`;
}

// Liczby nad listą wyników: ile plików weszło, ile kont, jaki łączny zakres.
function podsumujPaczke(wyniki) {
    const udane = wyniki.filter(w => w.ok && w.summary);
    const konta = new Set();
    let od = null, doDnia = null, nowe = 0;
    for (const w of udane) {
        nowe += w.summary.saved;
        for (const a of w.summary.accounts) {
            if (a.account_id) konta.add(a.account_id);
            if (a.from && (!od || a.from < od)) od = a.from;
            if (a.to && (!doDnia || a.to > doDnia)) doDnia = a.to;
        }
    }
    return { pliki: wyniki.length, wgrane: udane.length, bledy: wyniki.filter(w => w.ok === false).length,
             konta, od, doDnia, nowe };
}

// Konta, które zwykle dostają wyciągi (mają wpis w historii importów), a nie było
// ich w tej paczce. Tylko informacja — brak wyciągu niczego nie blokuje.
function kontaBezWyciagu(historia, kontaWPaczce) {
    const ostatni = new Map();
    for (const h of historia) {
        if (!h.account_id || kontaWPaczce.has(h.account_id)) continue;
        if (!accounts.some(a => a.id === h.account_id)) continue;
        const prev = ostatni.get(h.account_id) || '';
        if (!ostatni.has(h.account_id) || (h.period_end || '') > prev) ostatni.set(h.account_id, h.period_end);
    }
    return [...ostatni]
        .map(([id, doDnia]) => ({ account_id: id, nazwa: nazwaKonta(id), doDnia }))
        .sort((a, b) => a.nazwa.localeCompare(b.nazwa, 'pl'));
}

async function odswiezKontaBezWyciagu() {
    try {
        const resp = await fetch('/api/import/history');
        if (resp.ok) kontaBezWyciaguPaczki = kontaBezWyciagu(await resp.json(), podsumujPaczke(paczkaImportu).konta);
    } catch (_) {
        // To tylko podpowiedź — bez historii po prostu jej nie pokazujemy.
    }
    renderPodsumowaniePaczki();
}

function renderPodsumowaniePaczki() {
    const box = document.getElementById('import-paczka');
    if (!box) return;
    const p = podsumujPaczke(paczkaImportu);
    const czesci = [`Wgrano ${p.wgrane} z ${p.pliki} ${odmiana(p.pliki, ['wyciągu', 'wyciągów', 'wyciągów'])}`];
    if (p.konta.size) czesci.push(`${p.konta.size} ${odmiana(p.konta.size, ['konto', 'konta', 'kont'])}`);
    if (p.od) czesci.push(zakresPL(p.od, p.doDnia));
    czesci.push(`${p.nowe} ${odmiana(p.nowe, ['nowa operacja', 'nowe operacje', 'nowych operacji'])}`);
    let html = `<div class="font-medium text-slate-700">${czesci.join(' · ')}</div>`;
    if (p.bledy) {
        html += `<div class="text-rose-600 mt-0.5">Nie wszystkie wyciągi są wgrane: ${p.bledy} ${odmiana(p.bledy, ['plik wymaga', 'pliki wymagają', 'plików wymaga'])} poprawki (szczegóły poniżej). Pozostałe są już w poczekalni.</div>`;
    }
    if (kontaBezWyciaguPaczki.length) {
        const lista = kontaBezWyciaguPaczki.map(k =>
            `${escapeHtml(k.nazwa)}${k.doDnia ? ` (ostatni do ${dataPL(k.doDnia)})` : ''}`).join(', ');
        html += `<div class="text-slate-500 mt-0.5">Brak wyciągu w tej paczce: ${lista}. Możesz go wgrać później — nie blokuje to zatwierdzania pozostałych.</div>`;
    }
    box.innerHTML = html;
}

function dodajWyborKonta(file, bank, wiersz, wynik) {
    const box = document.createElement('div');
    box.className = 'w-full flex flex-wrap items-center gap-2 mt-1';
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
        if (await wgrajPlik(file, bank, select.value, wiersz, wynik)) {
            odswiezPoImporcie();
            await odswiezKontaBezWyciagu();
        }
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

