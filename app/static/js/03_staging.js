// --- LOGIKA STAGINGU (OCZEKUJĄCYCH TRANSAKCJI) ---
async function reanalyzeStaging() {
    try {
        const response = await fetch('/api/staging/reanalyze', { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            showToast(`Odświeżono mapowanie dla ${result.count} transakcji.`, 'success');
            await fetchPendingStaging();
        } else {
            showToast(result.error || 'Błąd podczas odświeżania mapowania.', 'error');
        }
    } catch (e) {
        showToast('Błąd połączenia z serwerem.', 'error');
    }
}

async function fetchPendingStaging() {
    try {
        const response = await fetch('/api/staging/pending');
        if (!response.ok) {
            // If 401, it just means the user is not logged in yet. Don't show an error.
            // For other errors, log it. The main fetchInitialData will show a toast.
            if (response.status !== 401) {
                console.error('Błąd pobierania transakcji ze stagingu:', await response.text());
            }
            return;
        }
        pendingStaging = await response.json();
        renderStaging();
    } catch (error) {
        console.error('Błąd pobierania transakcji ze stagingu:', error);
    }
}

function resolveStagingDestAccountId(t) {
    // Konto docelowe może pochodzić z lokalnego wyboru w tej sesji (_dest_account_id)
    // albo, dla wierszy już rozpoznanych automatycznie po numerze konta, z nazwy
    // istniejącego kontrahenta "Moje konto: {nazwa}" — ta sama konwencja co po
    // stronie serwera w _resolve_destination_account (budget_service.py).
    if (t._dest_account_id) return String(t._dest_account_id);
    if (t.proposed_contractor_id) {
        const cont = contractors.find(c => c.id == t.proposed_contractor_id);
        if (cont && cont.name.startsWith('Moje konto: ')) {
            const destAcc = accounts.find(a => a.name === cont.name.slice('Moje konto: '.length));
            if (destAcc) return String(destAcc.id);
        }
    }
    return '';
}

function getStagingStatus(t) {
    const cat = categories.find(c => c.name === t.proposed_category);
    const isTransfer = !!(cat && cat.type === 'transfer');
    const destResolved = isTransfer ? resolveStagingDestAccountId(t) : '';
    const hasSuggestion = !isTransfer && !!(t.suggested_contractor_name && !t.proposed_contractor_id);
    const isFullyMapped = isTransfer
        ? !!(t.proposed_category && destResolved)
        : !!(t.proposed_category && t.proposed_contractor_id);
    // Możliwy duplikat ocenia osobno statusPozycji — wiersz w pełni zmapowany też
    // może pokrywać się z transakcją wpisaną wcześniej ręcznie.
    return { hasSuggestion, isFullyMapped, isTransfer };
}

// Okno szukania duplikatu — ta sama wartość co _DUPLICATE_MATCH_WINDOW_DAYS
// w budget_service.py: podgląd ma pokazać historię z okna, w którym szuka serwer.
const DUPLIKAT_OKNO_DNI = 4;

function nazwaKonta(id) {
    const a = accounts.find(x => x.id == id) || inactiveAccounts.find(x => x.id == id);
    return a ? a.name : 'Konto nieznane';
}

// Konto po drugiej stronie przelewu: wybór z tej sesji albo kontrahent „Moje konto: X";
// gdy żadne nie wskazuje konta ze słownika — nazwa, którą podał serwer.
function nazwaDrugiegoKonta(t) {
    const id = resolveStagingDestAccountId(t);
    if (id) return nazwaKonta(id);
    const obce = t.transfer_own === 'from' ? t.transfer_to : t.transfer_from;
    return obce ? obce.name : '?';
}

// Lustro na koncie nogi przelewu nie jest duplikatem: zatwierdzenie tej nogi
// je zastąpi (#217), więc to nie ta sama operacja wpisana dwa razy.
function kandydaciDuplikatu(t) {
    const lista = t.duplicate_candidates || [];
    return getStagingStatus(t).isTransfer ? lista.filter(c => c.origin !== 'mirror') : lista;
}

// Przelewy i zwykłe operacje. Para to dwie nogi sparowane przez serwer w tej
// poczekalni (transfer_pair_id wskazują nawzajem) — jeden wiersz, wypływ pierwszy.
// Noga, której kategorię zmieniono w tej sesji na zwykłą, jest zwykłą operacją.
function podzielPoczekalnie(lista) {
    const czyPrzelew = t => getStagingStatus(t).isTransfer;
    const poId = new Map(lista.map(t => [t.id, t]));
    const uzyte = new Set();
    const przelewy = [], operacje = [];
    lista.forEach(t => {
        if (uzyte.has(t.id)) return;
        uzyte.add(t.id);
        if (!czyPrzelew(t)) { operacje.push(t); return; }
        const p = poId.get(t.transfer_pair_id);
        if (p && !uzyte.has(p.id) && p.transfer_pair_id === t.id && czyPrzelew(p) && !t._rozdziel && !p._rozdziel) {
            uzyte.add(p.id);
            przelewy.push(t.amount < 0 ? [t, p] : [p, t]);
        } else {
            przelewy.push([t]);
        }
    });
    return { przelewy, operacje };
}

// [[konto, wiersze], …] w kolejności słownika kont; wiersz bez znanego konta na końcu.
function grupujPoKontach(operacje) {
    const grupy = new Map();
    operacje.forEach(t => {
        const klucz = t.account_id ?? null;
        if (!grupy.has(klucz)) grupy.set(klucz, []);
        grupy.get(klucz).push(t);
    });
    const kolejnosc = k => {
        if (k === null) return Infinity;
        const i = accounts.findIndex(a => a.id == k);
        return i < 0 ? accounts.length : i;
    };
    return [...grupy.entries()].sort((a, b) => kolejnosc(a[0]) - kolejnosc(b[0]));
}

// 'dup' | 'todo' | 'ready' dla pozycji listy (operacja albo przelew z 1–2 nogami).
// Możliwy duplikat nie jest gotowy, dopóki użytkownik go nie rozstrzygnie —
// „Zatwierdź gotowe" go pomija.
function statusPozycji(nogi) {
    if (nogi.some(t => !t._nie_duplikat && kandydaciDuplikatu(t).length)) return 'dup';
    return nogi.every(t => getStagingStatus(t).isFullyMapped) ? 'ready' : 'todo';
}

// Liczniki filtrów liczą WIERSZE na ekranie (para = 1), licznik w menu — operacje
// (para = 2). Rozjazd jest zamierzony.
function licznikiFiltrow(przelewy, operacje) {
    const licz = { all: 0, ready: 0, todo: 0, dup: 0, transfer: przelewy.length };
    [...przelewy, ...operacje.map(t => [t])].forEach(nogi => {
        licz.all++;
        licz[statusPozycji(nogi)]++;
    });
    return licz;
}

function pasujeDoFiltra(nogi, czyPrzelew) {
    return stagingFilter === 'all' || (stagingFilter === 'transfer' && czyPrzelew) || statusPozycji(nogi) === stagingFilter;
}

// Pole konta po drugiej stronie: dla wypływu to konto docelowe, dla wpływu — źródłowe.
function etykietaKierunku(t) {
    return t.amount < 0 ? 'Na konto' : 'Z konta';
}

function trasaPrzelewu(nogi) {
    if (nogi.length === 2) return { z: nazwaKonta(nogi[0].account_id), na: nazwaKonta(nogi[1].account_id), wlasne: null };
    const t = nogi[0];
    const wlasne = nazwaKonta(t.account_id), inne = nazwaDrugiegoKonta(t);
    return t.amount < 0 ? { z: wlasne, na: inne, wlasne: 'z' } : { z: inne, na: wlasne, wlasne: 'na' };
}

// Każda noga w walucie swojego konta; wymiana walut pokazuje obie kwoty.
function kwotaPrzelewu(nogi) {
    const kw = t => `${formatKwota(Math.abs(t.amount))} ${walutaKonta(t.account_id)}`;
    if (nogi.length === 2 && walutaKonta(nogi[0].account_id) !== walutaKonta(nogi[1].account_id)) {
        return `${kw(nogi[0])} → ${kw(nogi[1])}`;
    }
    return kw(nogi[0]);
}

// Skąd weźmie się druga strona — słowami, według transfer_pair z serwera
// (gałęzie handle_internal_transfer, patrz _pair_staging_transfer_legs).
function opisDrugiejStrony(nogi) {
    if (nogi.length === 2) {
        return { klasa: 'ok', glowne: 'Obie operacje są w tym imporcie',
                 opis: 'Zatwierdzenie zaksięguje obie i połączy je w jeden przelew.' };
    }
    const t = nogi[0];
    const inne = nazwaDrugiegoKonta(t);
    // Stan z serwera dotyczy zapisanego konta — po zmianie w tej sesji jest nieaktualny.
    if (t._dest_account_id) {
        return { klasa: 'info', glowne: 'Zmieniono konto',
                 opis: `Aplikacja sprawdzi drugą stronę na koncie ${inne} przy zatwierdzeniu.` };
    }
    switch (t.transfer_pair) {
        case 'staging': return { klasa: 'ok', glowne: 'Druga strona jest w tym imporcie',
                                 opis: 'Zatwierdź obie operacje — połączą się w jeden przelew.' };
        case 'booked': return { klasa: 'ok', glowne: 'Druga strona jest już zaksięgowana',
                                opis: 'Zatwierdzenie połączy ją z tą operacją w jeden przelew.' };
        case 'mirror': return { klasa: 'info', glowne: 'Dopisze ją aplikacja',
                                opis: `${inne} nie dostaje wyciągów, więc ${t.amount < 0 ? 'wpływ' : 'wypływ'} pojawi się tam sam po zatwierdzeniu.` };
        case 'missing': return { klasa: 'bad', glowne: `Brak — zaimportuj wyciąg z konta ${inne}`,
                                 opis: `To konto dostaje własne wyciągi albo ma inną walutę, więc aplikacja nie dopisze tej operacji sama. Dopóki jej nie zaimportujesz, saldo konta ${inne} się nie zmieni.` };
        default: return { klasa: 'info', glowne: 'Aplikacja ustali przy zatwierdzeniu', opis: '' };
    }
}

// Historia konta wiersza z okna ±DUPLIKAT_OKNO_DNI — do porównania bez wychodzenia
// z importu. Kandydaci w kolejności z serwera (najbliższa data pierwsza).
function oknoDuplikatu(t) {
    const przesun = dni => {
        const d = new Date(`${t.date}T00:00:00`);
        d.setDate(d.getDate() + dni);
        return toLocalISODate(d);
    };
    const od = przesun(-DUPLIKAT_OKNO_DNI), doDnia = przesun(DUPLIKAT_OKNO_DNI);
    const wiersze = transactions
        .filter(h => h.account_id == t.account_id && h.date >= od && h.date <= doDnia)
        .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.id - b.id));
    return { od, do: doDnia, wiersze, kandydaci: kandydaciDuplikatu(t).map(c => c.id) };
}

const ORIGIN_LABELS = {
    manual: 'dodana ręcznie',
    import: 'z importu wyciągu',
    recurring: 'z transakcji cyklicznej',
    planned: 'z transakcji planowanej',
    mirror: 'lustro przelewu wewnętrznego',
    reconcile: 'uzgodnienie salda',
    excel: 'migracja z arkusza',
    unknown: 'pochodzenie nieznane',
};

// Stan widoku w tej sesji (nie trafia na serwer): otwarte „Zmień konto"
// i rozwinięte porównania możliwego duplikatu z wybranym kandydatem.
const stagingEdycjaKonta = new Set();
const stagingPodglad = new Set();
const stagingWybranyDuplikat = new Map();

const STATUS_PASEK = {
    ready: 'border-l-emerald-400', todo: 'border-l-amber-400', dup: 'border-l-orange-400', warn: 'border-l-rose-400',
};
const KLASY_TAGU = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider';
const KLASY_LINKU = 'text-xs text-blue-700 underline decoration-blue-300 underline-offset-2 hover:decoration-blue-700';
const KLASY_SELECTU = 'w-full p-1.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white cursor-pointer';

window.setStagingFilter = function(filter) {
    stagingFilter = filter;
    renderStaging();
};

window.toggleStagingSort = function(field) {
    if (stagingSort.field === field) {
        stagingSort.dir = stagingSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
        stagingSort.field = field;
        stagingSort.dir = field === 'date' ? 'desc' : 'asc';
    }
    renderStaging();
};

// Sortowanie w obrębie grupy; przelew sortuje się po pierwszej nodze.
function posortujPozycje(pozycje) {
    const klucz = nogi => {
        const t = nogi[0];
        if (stagingSort.field === 'title') return (t.title || '').toLowerCase();
        if (stagingSort.field === 'amount') return Math.abs(t.amount);
        return t.date;
    };
    return [...pozycje].sort((a, b) => {
        const [x, y] = [klucz(a), klucz(b)];
        if (x < y) return stagingSort.dir === 'asc' ? -1 : 1;
        if (x > y) return stagingSort.dir === 'asc' ? 1 : -1;
        return 0;
    });
}

function naglowekSort(field, label, klasy = '') {
    const ikona = stagingSort.field === field ? (stagingSort.dir === 'asc' ? '↑' : '↓') : '↕';
    return `<th class="p-3 font-semibold cursor-pointer select-none whitespace-nowrap ${klasy}" tabindex="0" onkeydown="klawiszJakKlik(event)" onclick="toggleStagingSort('${field}')">${label} <span class="ml-0.5 ${stagingSort.field === field ? 'text-slate-700' : 'text-slate-300'}">${ikona}</span></th>`;
}

function htmlTabeli(naglowki, wiersze) {
    return `<div class="overflow-x-auto border border-slate-200 rounded-xl">
        <table class="tabela-karty w-full text-left border-collapse sm:table-fixed sm:min-w-[860px]">
            <thead><tr class="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">${naglowki}</tr></thead>
            <tbody class="divide-y divide-slate-100">${wiersze}</tbody>
        </table>
    </div>`;
}

function htmlGrupy(tytul, podpis, opis, tabela) {
    return `<div class="space-y-2">
        <div class="flex flex-wrap items-baseline gap-x-3">
            <h3 class="font-semibold text-slate-800">${tytul}</h3>
            <span class="text-xs text-slate-500">${podpis}</span>
        </div>
        ${opis ? `<p class="text-xs text-slate-500">${opis}</p>` : ''}
        ${tabela}
    </div>`;
}

function renderStaging() {
    const list = document.getElementById('staging-list');
    const empty = document.getElementById('staging-empty');
    const badge = document.getElementById('staging-badge');
    const filtersRow = document.getElementById('staging-filters');
    const summary = document.getElementById('staging-summary');
    const approveBtn = document.getElementById('approve-all-btn');

    // Licznik w menu liczy operacje (para przelewu to dwie) — tyle wierszy zapisze się w historii.
    badge.innerText = pendingStaging.length;
    badge.classList.toggle('hidden', pendingStaging.length === 0);

    if (pendingStaging.length === 0) {
        list.innerHTML = '';
        filtersRow.classList.add('hidden');
        summary.textContent = 'Wszystko zatwierdzone.';
        approveBtn.disabled = true;
        approveBtn.textContent = 'Zatwierdź gotowe';
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');
    filtersRow.classList.remove('hidden');

    const { przelewy, operacje } = podzielPoczekalnie(pendingStaging);
    const licz = licznikiFiltrow(przelewy, operacje);
    const konta = new Set(pendingStaging.map(t => t.account_id).filter(id => id != null));
    const n = pendingStaging.length;
    summary.textContent = `Na zatwierdzenie ${odmiana(n, ['czeka', 'czekają', 'czeka'])} ${n} ${odmiana(n, ['operacja', 'operacje', 'operacji'])} z ${konta.size} ${konta.size === 1 ? 'konta' : 'kont'}.`;
    approveBtn.disabled = licz.ready === 0;
    approveBtn.textContent = `Zatwierdź gotowe (${licz.ready})`;

    [['all', 'sf-all'], ['ready', 'sf-ready'], ['todo', 'sf-todo'], ['dup', 'sf-duplicate'], ['transfer', 'sf-transfer']].forEach(([f, id]) => {
        document.getElementById(`sf-count-${f}`).textContent = licz[f];
        document.getElementById(id).className = stagingFilter === f
            ? 'text-xs px-3 py-1 rounded-full font-medium transition-colors bg-slate-700 text-white'
            : 'text-xs px-3 py-1 rounded-full font-medium transition-colors bg-slate-100 text-slate-600 hover:bg-slate-200';
    });

    let html = '';
    const widocznePrzelewy = posortujPozycje(przelewy.filter(nogi => pasujeDoFiltra(nogi, true)));
    if (widocznePrzelewy.length) {
        html += htmlGrupy('Przelewy między Twoimi kontami',
            `${widocznePrzelewy.length} ${odmiana(widocznePrzelewy.length, ['przelew', 'przelewy', 'przelewów'])}`,
            'Nie są ani wydatkiem, ani przychodem — przesuwają pieniądze między Twoimi kontami. Podkreślone konto to to, z którego wyciągu pochodzi operacja.',
            htmlTabeli(
                naglowekSort('date', 'Data', 'w-[11%]') + naglowekSort('title', 'Przelew') +
                '<th class="p-3 font-semibold w-[30%]">Druga strona</th>' +
                naglowekSort('amount', 'Kwota', 'w-[14%] text-right') + '<th class="p-3 w-[12%]"></th>',
                widocznePrzelewy.map(htmlPrzelewu).join('')));
    }

    grupujPoKontach(operacje).forEach(([kontoId, wiersze]) => {
        const widoczne = posortujPozycje(wiersze.map(t => [t]).filter(nogi => pasujeDoFiltra(nogi, false)));
        if (!widoczne.length) return;
        const konto = accounts.find(a => a.id == kontoId);
        const podpis = [konto && konto.bank_name, konto && skrotNumeru(konto.account_number),
                        `${widoczne.length} ${odmiana(widoczne.length, ['operacja', 'operacje', 'operacji'])}`].filter(Boolean).join(' · ');
        html += htmlGrupy(escapeHtml(kontoId == null ? 'Konto nieznane' : nazwaKonta(kontoId)), escapeHtml(podpis), '',
            htmlTabeli(
                naglowekSort('date', 'Data', 'w-[11%]') + naglowekSort('title', 'Z wyciągu') +
                '<th class="p-3 font-semibold w-[20%]">Kontrahent</th><th class="p-3 font-semibold w-[18%]">Kategoria</th>' +
                naglowekSort('amount', 'Kwota', 'w-[12%] text-right') + '<th class="p-3 w-[11%]"></th>',
                widoczne.map(([t]) => htmlOperacji(t)).join('')));
    });

    list.innerHTML = html || '<p class="p-8 text-center text-sm text-slate-500">Nic nie pasuje do wybranego filtru.</p>';
}

// 2 pierwsze + 4 ostatnie cyfry — jak _abbrev_account po stronie serwera.
function skrotNumeru(numer) {
    const n = (numer || '').replace(/[\s-]/g, '');
    return n.length >= 6 ? `${n.slice(0, 2)}…${n.slice(-4)}` : n;
}

function htmlPrzelewu(nogi) {
    const t = nogi[0];
    const para = nogi.length === 2;
    const status = statusPozycji(nogi);
    const opis = opisDrugiejStrony(nogi);
    const pasek = status === 'ready' && opis.klasa === 'bad' ? STATUS_PASEK.warn : STATUS_PASEK[status];
    const trasa = trasaPrzelewu(nogi);
    const konto = (nazwa, strona) => trasa.wlasne === strona
        ? `<span class="font-semibold underline decoration-sky-300" title="Konto, z którego wyciągu pochodzi ta operacja">${escapeHtml(nazwa)}</span>`
        : `<span>${escapeHtml(nazwa)}</span>`;

    // Kategoria przelewu tylko przy kilku kategoriach typu przelew — przy jednej nie ma czego wybierać.
    const katPrzelewu = categories.filter(c => c.type === 'transfer');
    const ids = nogi.map(n => n.id).join(',');
    const wyborKategorii = katPrzelewu.length > 1 ? `
        <select id="staging-cat-${t.id}" onchange="ustawKategoriePrzelewu([${ids}], this.value)" class="${KLASY_SELECTU} mt-1.5 max-w-xs">
            ${katPrzelewu.map(c => `<option value="${escapeHtml(c.name)}" ${c.name === t.proposed_category ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}
        </select>` : '';

    let akcjeNogi = '';
    if (para) {
        akcjeNogi = `<button type="button" onclick="rozdzielPare(${t.id}, ${nogi[1].id})" class="${KLASY_LINKU}">Rozdziel</button>`;
    } else if (stagingEdycjaKonta.has(t.id)) {
        akcjeNogi = `<label class="flex items-center gap-2 text-xs text-slate-600">${etykietaKierunku(t)}:
            <select onchange="ustawKontoPrzelewu(${t.id}, this.value)" class="${KLASY_SELECTU} max-w-[14rem]">
                <option value="">Wybierz konto…</option>
                ${getDestAccountOptionsHtml(t.account_id, resolveStagingDestAccountId(t))}
            </select></label>`;
    } else {
        akcjeNogi = `<button type="button" onclick="zmienKontoPrzelewu(${t.id})" class="${KLASY_LINKU}">Zmień konto</button>
            <button type="button" onclick="toNiePrzelew(${t.id})" class="${KLASY_LINKU}">To nie przelew</button>`;
    }

    const podKwota = para ? 'para z tego importu'
        : `${t.amount < 0 ? '−' : '+'}${formatKwota(Math.abs(t.amount))} ${t.amount < 0 ? 'z' : 'na'} ${nazwaKonta(t.account_id)}`;
    const kropka = { ok: 'bg-emerald-500', info: 'bg-sky-500', bad: 'bg-rose-500' }[opis.klasa];

    return `<tr class="hover:bg-slate-50 transition-colors">
        <td data-label="Data" class="p-3 border-l-4 ${pasek} text-sm text-slate-500 whitespace-nowrap align-top">${t.date}</td>
        <td data-label="Przelew" class="p-3 align-top break-words">
            <div class="flex flex-wrap items-center gap-1.5 text-sm text-slate-800">${konto(trasa.z, 'z')}<span class="text-slate-400">→</span>${konto(trasa.na, 'na')}</div>
            <div class="text-xs text-slate-500 mt-0.5">„${escapeHtml(t.title)}” · tytuł z banku</div>
            ${status === 'dup' ? htmlKandydatowPrzelewu(nogi) : ''}
            ${wyborKategorii}
            <div class="flex flex-wrap gap-3 mt-1.5">${akcjeNogi}</div>
        </td>
        <td data-label="Druga strona" class="p-3 align-top">
            <div class="flex items-start gap-2 text-sm">
                <span class="mt-1.5 w-2 h-2 rounded-full shrink-0 ${kropka}"></span>
                <div><div class="font-medium ${opis.klasa === 'bad' ? 'text-rose-700' : 'text-slate-800'}">${escapeHtml(opis.glowne)}</div>
                ${opis.opis ? `<div class="text-xs text-slate-500 mt-0.5">${escapeHtml(opis.opis)}</div>` : ''}</div>
            </div>
        </td>
        <td data-label="Kwota" class="p-3 align-top text-right whitespace-nowrap">
            <div class="font-bold text-slate-700">${escapeHtml(kwotaPrzelewu(nogi))}</div>
            <div class="text-xs text-slate-500 mt-0.5">${escapeHtml(podKwota)}</div>
        </td>
        <td data-label="Akcja" class="p-3 align-top text-center">
            <button onclick="${para ? `zatwierdzObie(${t.id}, ${nogi[1].id})` : `approveStaging(${t.id})`}" ${status === 'todo' ? 'disabled title="Wybierz konto po drugiej stronie"' : ''}
                class="px-3 py-2 text-sm font-medium rounded-lg shadow-sm whitespace-nowrap w-full ${status === 'todo' ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-sky-600 hover:bg-sky-700 text-white'}">${para ? 'Zatwierdź obie' : 'Zatwierdź'}</button>
        </td>
    </tr>`;
}

// Noga przelewu z kandydatem na duplikat (poza lustrem, które zatwierdzenie zastępuje)
// — rzadkie, więc bez osobnego podglądu: lista kandydatów i odrzucenie jak przy operacji.
function htmlKandydatowPrzelewu(nogi) {
    return nogi.filter(t => !t._nie_duplikat && kandydaciDuplikatu(t).length).map(t => `
        <div class="mt-1.5 p-2 bg-orange-50 border border-orange-200 rounded-lg text-xs">
            <div class="text-orange-800 font-medium">Ta operacja może już być w historii konta ${escapeHtml(nazwaKonta(t.account_id))}:</div>
            ${kandydaciDuplikatu(t).map(c => `<div class="text-slate-700">${c.date} · ${escapeHtml(c.title)} <span class="text-slate-500">(${escapeHtml(ORIGIN_LABELS[c.origin] || c.origin)})</span></div>`).join('')}
            <div class="flex flex-wrap gap-3 mt-1">
                <button type="button" onclick="dismissStagingDuplicate(${t.id})" class="${KLASY_LINKU}">To ta sama — odrzuć wiersz z wyciągu</button>
                <button type="button" onclick="toInnaOperacja(${t.id})" class="${KLASY_LINKU}">To inna operacja — zostaw</button>
            </div>
        </div>`).join('');
}

function htmlOperacji(t) {
    const status = statusPozycji([t]);
    const { hasSuggestion } = getStagingStatus(t);
    const tag = {
        ready: ['bg-emerald-100 text-emerald-700', 'Gotowe'],
        todo: ['bg-amber-100 text-amber-700', !t.proposed_contractor_id && !t.proposed_category ? 'Uzupełnij kontrahenta i kategorię'
                                              : !t.proposed_category ? 'Uzupełnij kategorię' : 'Uzupełnij kontrahenta'],
        dup: ['bg-orange-100 text-orange-700', 'Możliwy duplikat'],
    }[status];
    const kandydaci = kandydaciDuplikatu(t);
    const otwarty = stagingPodglad.has(t.id);
    const porownaj = status === 'dup' ? `<button type="button" onclick="przelaczPodglad(${t.id})" aria-expanded="${otwarty}" class="${KLASY_LINKU} ml-2">${otwarty ? 'Ukryj porównanie' : `Porównaj z historią (${kandydaci.length})`}</button>` : '';

    const kwotaKlasa = t.amount >= 0 ? 'text-emerald-600' : 'text-rose-600';
    const wiersz = `<tr class="hover:bg-slate-50 transition-colors">
        <td data-label="Data" class="p-3 border-l-4 ${STATUS_PASEK[status]} text-sm text-slate-500 whitespace-nowrap align-top">${t.date}</td>
        <td data-label="Z wyciągu" class="p-3 align-top break-words">
            <div class="text-sm font-medium text-slate-800">${escapeHtml(t.title)}</div>
            ${t.contractor ? `<div class="text-xs text-slate-500 mt-0.5 break-all">${escapeHtml(t.contractor)}</div>` : ''}
            <div class="mt-1"><span class="${KLASY_TAGU} ${tag[0]}">${tag[1]}</span>${porownaj}</div>
        </td>
        <td data-label="Kontrahent" class="p-3 align-top">
            ${hasSuggestion ? `
            <div class="flex items-center gap-1 mb-1.5 p-1.5 bg-amber-50 border border-amber-200 rounded-lg">
                <span class="text-xs text-amber-700 font-medium shrink-0">Nowy:</span>
                <input type="text" id="suggested-name-${t.id}" value="${escapeHtml(t.suggested_contractor_name)}" aria-label="Nazwa nowego kontrahenta" class="flex-1 text-xs p-1 border border-amber-300 rounded focus:ring-1 focus:ring-amber-400 outline-none min-w-0">
                <button onclick="acceptSuggestedContractor(${t.id})" class="shrink-0 text-xs bg-amber-500 hover:bg-amber-600 text-white px-2 py-1 rounded font-medium transition-colors">Dodaj</button>
            </div>` : ''}
            <select id="staging-cont-${t.id}" onchange="updateStagingLocalState(${t.id}, 'proposed_contractor_id', this.value)" class="${KLASY_SELECTU}">
                <option value="">Wybierz kontrahenta…</option>
                ${getContractorOptionsHtml(t.proposed_contractor_id)}
            </select>
        </td>
        <td data-label="Kategoria" class="p-3 align-top">
            <select id="staging-cat-${t.id}" onchange="updateStagingLocalState(${t.id}, 'proposed_category', this.value)" class="${KLASY_SELECTU}">
                <option value="">Wybierz kategorię…</option>
                ${getCategoryOptionsHtml(t.proposed_category)}
            </select>
        </td>
        <td data-label="Kwota" class="p-3 align-top font-bold ${kwotaKlasa} text-right whitespace-nowrap">${t.amount >= 0 ? '+' : ''}${formatKwota(t.amount)} ${walutaKonta(t.account_id)}</td>
        <td data-label="Akcja" class="p-3 align-top text-center">
            <button onclick="approveStaging(${t.id})" ${status === 'todo' ? 'disabled title="Uzupełnij kontrahenta i kategorię, aby zatwierdzić"' : ''}
                class="px-3 py-2 text-sm font-medium rounded-lg shadow-sm whitespace-nowrap w-full ${status === 'todo' ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-700 text-white'}">Zatwierdź</button>
        </td>
    </tr>`;
    return status === 'dup' && otwarty ? wiersz + htmlPodgladuDuplikatu(t) : wiersz;
}

// Porównanie możliwego duplikatu z historią bez wychodzenia z importu: pola obok
// siebie i historia konta z okna ±DUPLIKAT_OKNO_DNI (dane z globalnego `transactions`).
function htmlPodgladuDuplikatu(t) {
    const okno = oknoDuplikatu(t);
    const kandydaci = kandydaciDuplikatu(t);
    const wybranyId = okno.kandydaci.includes(stagingWybranyDuplikat.get(t.id)) ? stagingWybranyDuplikat.get(t.id) : okno.kandydaci[0];
    const c = kandydaci.find(k => k.id === wybranyId);
    const h = transactions.find(x => x.id === wybranyId) || {};
    const kw = (v, konto) => `${v >= 0 ? '+' : '−'}${formatKwota(Math.abs(v))} ${walutaKonta(konto)}`;
    const kontrahent = (contractors.find(k => k.id == t.proposed_contractor_id) || {}).name;
    const kolumna = (tytul, pola) => `<div><div class="text-xs font-semibold text-slate-700 mb-1">${tytul}</div>
        <dl class="grid grid-cols-[6rem_1fr] gap-x-2 gap-y-0.5 text-xs">${pola.map(([k, v]) =>
            `<dt class="text-slate-500">${k}</dt><dd class="text-slate-800 break-words">${escapeHtml(v || '—')}</dd>`).join('')}</dl></div>`;

    const historia = okno.wiersze.map(x => {
        const kand = okno.kandydaci.includes(x.id);
        return `<tr class="${kand ? 'bg-orange-50' : ''}">
            <td class="py-1 px-2 w-6">${kand ? `<input type="radio" name="dup-${t.id}" ${x.id === wybranyId ? 'checked' : ''} onchange="wybierzDuplikat(${t.id}, ${x.id})" aria-label="Porównaj z: ${x.date} ${escapeHtml(x.desc || '')}">` : ''}</td>
            <td class="py-1 px-2 whitespace-nowrap text-slate-500">${x.date}</td>
            <td class="py-1 px-2">${escapeHtml(x.desc || '')}</td>
            <td class="py-1 px-2 text-slate-500">${escapeHtml(x.contractor_name || '')}</td>
            <td class="py-1 px-2 text-slate-500">${escapeHtml(x.category || '')}</td>
            <td class="py-1 px-2 text-right whitespace-nowrap ${x.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${kw(x.amount, x.account_id)}</td>
        </tr>`;
    }).join('');

    return `<tr><td colspan="6" class="p-3 bg-orange-50/40">
        <div class="border border-orange-200 rounded-xl bg-white p-4 space-y-4">
            <div class="grid sm:grid-cols-2 gap-4">
                ${kolumna('Z wyciągu', [['Data', t.date], ['Kwota', kw(t.amount, t.account_id)], ['Tytuł', t.title], ['Z banku', t.contractor],
                                        ['Kontrahent', kontrahent], ['Kategoria', t.proposed_category]])}
                ${kolumna('Już w historii', [['Data', c ? `${c.date} (${c.days_diff ? `${c.days_diff} ${odmiana(c.days_diff, ['dzień', 'dni', 'dni'])} różnicy` : 'ten sam dzień'})` : ''],
                                             ['Kwota', kw(t.amount, t.account_id)], ['Tytuł', h.desc || (c && c.title)],
                                             ['Kontrahent', h.contractor_name || (c && c.contractor)], ['Kategoria', h.category || (c && c.category)],
                                             ['Komentarz', h.comment], ['Skąd', c && (ORIGIN_LABELS[c.origin] || c.origin)]])}
            </div>
            <div>
                <p class="text-xs text-slate-600 mb-1">Na koncie ${escapeHtml(nazwaKonta(t.account_id))} w dniach ${okno.od} – ${okno.do} są już te operacje. Wyróżnione kwotą pasują do wiersza z wyciągu — wybierz, z którą porównać.</p>
                <table class="w-full text-xs">${historia}</table>
            </div>
            <div class="flex flex-wrap items-center gap-4">
                <button type="button" onclick="dismissStagingDuplicate(${t.id})" class="text-xs bg-orange-500 hover:bg-orange-600 text-white px-3 py-1.5 rounded-lg font-medium transition-colors">To ta sama — odrzuć wiersz z wyciągu</button>
                <button type="button" onclick="toInnaOperacja(${t.id})" class="${KLASY_LINKU}">To inna operacja — zostaw</button>
            </div>
        </div>
    </td></tr>`;
}

window.updateStagingLocalState = function(id, field, value) {
    const item = pendingStaging.find(t => t.id === id);
    if (item && value !== '__NEW_CATEGORY__' && value !== '__NEW_CONTRACTOR__') {
        item[field] = value;
        renderStaging();
    }
}

window.zmienKontoPrzelewu = function(id) {
    stagingEdycjaKonta.add(id);
    renderStaging();
};

window.ustawKontoPrzelewu = function(id, kontoId) {
    stagingEdycjaKonta.delete(id);
    updateStagingLocalState(id, '_dest_account_id', kontoId);
};

window.ustawKategoriePrzelewu = function(ids, nazwa) {
    ids.forEach(id => {
        const t = pendingStaging.find(x => x.id === id);
        if (t) t.proposed_category = nazwa;
    });
    renderStaging();
};

window.rozdzielPare = function(a, b) {
    pendingStaging.filter(t => t.id === a || t.id === b).forEach(t => { t._rozdziel = true; });
    renderStaging();
};

// Operacja błędnie uznana za przelew: wraca do zwykłych operacji swojego konta.
// Czyści też kontrahenta — „Moje konto: X" przy wydatku albo przychodzie nie ma sensu.
// Tylko stan w przeglądarce; serwer dostaje wynik dopiero przy zatwierdzeniu.
window.toNiePrzelew = function(id) {
    const t = pendingStaging.find(x => x.id === id);
    if (!t) return;
    t.proposed_category = '';
    t.proposed_contractor_id = '';
    t._dest_account_id = '';
    stagingEdycjaKonta.delete(id);
    renderStaging();
    showToast(`„${t.title}” przeniesione do operacji konta ${nazwaKonta(t.account_id)} — wybierz kontrahenta i kategorię.`, 'info');
};

window.przelaczPodglad = function(id) {
    if (stagingPodglad.has(id)) stagingPodglad.delete(id); else stagingPodglad.add(id);
    renderStaging();
};

window.wybierzDuplikat = function(id, txId) {
    stagingWybranyDuplikat.set(id, txId);
    renderStaging();
};

// Tylko w tej sesji — serwer przy kolejnym pobraniu poczekalni znów wskaże kandydata.
window.toInnaOperacja = function(id) {
    const t = pendingStaging.find(x => x.id === id);
    if (t) t._nie_duplikat = true;
    stagingPodglad.delete(id);
    renderStaging();
};

window.acceptSuggestedContractor = function(stg_id) {
    const input = document.getElementById(`suggested-name-${stg_id}`);
    const name = input ? input.value.trim() : '';
    if (!name) {
        showToast('Podaj nazwę kontrahenta.', 'error');
        return;
    }
    openQuickContractorModal(name, stg_id);
}

window.dismissStagingDuplicate = async function(id) {
    const t = pendingStaging.find(x => x.id === id);
    if (!t) return;
    const kandydaci = kandydaciDuplikatu(t).map(c => c.id);
    const txId = kandydaci.includes(stagingWybranyDuplikat.get(id)) ? stagingWybranyDuplikat.get(id) : kandydaci[0];
    if (!txId) return;
    if (!confirm('Odrzucić ten wiersz importu jako duplikat wskazanej transakcji? Istniejąca transakcja i saldo konta pozostaną bez zmian.')) return;

    try {
        const response = await fetch(`/api/staging/${id}/duplicate-of`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transaction_id: txId })
        });
        if (response.ok) {
            showToast('Wiersz odrzucony jako duplikat.', 'info');
            pendingStaging = pendingStaging.filter(x => x.id !== id);
            stagingPodglad.delete(id);
            renderStaging();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd odrzucania duplikatu.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z API.', 'error');
    }
}

// Zatwierdza jeden wiersz według stanu z tej sesji (listy wyboru zapisują go w
// pendingStaging). Rzuca Error z komunikatem dla użytkownika.
async function zatwierdzWiersz(t) {
    if (!t.proposed_category) throw new Error('Wybierz kategorię przed zatwierdzeniem.');
    let contractor_id;
    if (getStagingStatus(t).isTransfer) {
        const dest = resolveStagingDestAccountId(t);
        if (!dest) throw new Error('Wybierz konto po drugiej stronie przelewu.');
        contractor_id = await resolveOrCreateTransferContractorId(dest);
    } else {
        if (!t.proposed_contractor_id) throw new Error('Wybierz kontrahenta przed zatwierdzeniem.');
        contractor_id = parseInt(t.proposed_contractor_id, 10);
    }
    const res = await fetch(`/api/staging/${t.id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: t.proposed_category, contractor_id })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.error === 'string' ? err.error : 'Błąd zatwierdzania transakcji.');
    }
}

// Zatwierdzony wiersz znika lokalnie (bez pobierania poczekalni — inaczej przepadłyby
// zmiany na pozostałych wierszach). Partner z pary ma już drugą stronę w historii.
function usunZatwierdzony(id) {
    const t = pendingStaging.find(x => x.id === id);
    const partner = t && pendingStaging.find(x => x.id === t.transfer_pair_id);
    if (partner) {
        partner.transfer_pair = 'booked';
        partner.transfer_pair_id = null;
    }
    pendingStaging = pendingStaging.filter(x => x.id !== id);
}

window.approveStaging = async function(id) {
    const t = pendingStaging.find(x => x.id === id);
    if (!t) return;
    try {
        await zatwierdzWiersz(t);
        showToast('Transakcja zatwierdzona!');
        usunZatwierdzony(id);
        renderStaging();
        fetchInitialData({ skipStagingRefresh: true });
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Para po kolei: druga noga widzi pierwszą jako zaksięgowaną i łączy się z nią.
// Przy błędzie drugiej zostaje ona na liście jako „druga strona już zaksięgowana".
window.zatwierdzObie = async function(a, b) {
    let ok = 0;
    for (const id of [a, b]) {
        const t = pendingStaging.find(x => x.id === id);
        try {
            await zatwierdzWiersz(t);
            usunZatwierdzony(id);
            ok++;
        } catch (err) {
            showToast(err.message, 'error');
            break;
        }
    }
    if (ok === 2) showToast('Przelew zatwierdzony — obie operacje.');
    renderStaging();
    if (ok) fetchInitialData({ skipStagingRefresh: true });
}

window.approveAllStaging = async function() {
    const { przelewy, operacje } = podzielPoczekalnie(pendingStaging);
    const gotowe = [...przelewy, ...operacje.map(t => [t])].filter(nogi => statusPozycji(nogi) === 'ready').flat();

    if (gotowe.length === 0) {
        showToast('Brak gotowych operacji. Możliwe duplikaty i wiersze do uzupełnienia czekają na Twoją decyzję.', 'info');
        return;
    }
    if (!confirm(`Zatwierdzić ${gotowe.length} ${odmiana(gotowe.length, ['gotową operację', 'gotowe operacje', 'gotowych operacji'])}? Możliwe duplikaty i wiersze do uzupełnienia zostaną w poczekalni.`)) return;

    const progressBar   = document.getElementById('staging-progress-bar');
    const progressFill  = document.getElementById('staging-progress-fill');
    const progressText  = document.getElementById('staging-progress-text');
    const approveBtn    = document.getElementById('approve-all-btn');

    progressFill.style.width = '0%';
    progressText.textContent = `0 / ${gotowe.length}`;
    progressBar.classList.remove('hidden');
    approveBtn.disabled = true;
    approveBtn.textContent = 'Zatwierdzanie…';

    let successCount = 0;
    let errorCount = 0;
    for (let i = 0; i < gotowe.length; i++) {
        try {
            await zatwierdzWiersz(gotowe[i]);
            successCount++;
        } catch (_) { errorCount++; }
        progressFill.style.width = `${Math.round(((i + 1) / gotowe.length) * 100)}%`;
        progressText.textContent = `${i + 1} / ${gotowe.length}`;
    }

    showToast(errorCount === 0
        ? `Zatwierdzono ${successCount} ${odmiana(successCount, ['operację', 'operacje', 'operacji'])}!`
        : `Zatwierdzono ${successCount}, błędy: ${errorCount}.`, errorCount === 0 ? 'success' : 'error');
    setTimeout(() => { progressBar.classList.add('hidden'); }, 1200);

    // Pobranie od nowa: po hurtowym zatwierdzeniu stany par i duplikatów liczy serwer.
    await fetchPendingStaging();
    if (successCount > 0) fetchInitialData({ skipStagingRefresh: true });
}

window.clearStaging = async function() {
    if (!confirm('Czy na pewno chcesz odrzucić WSZYSTKIE oczekujące transakcje? Tej operacji nie można cofnąć.')) return;

    try {
        const response = await fetch('/api/staging/pending', {
            method: 'DELETE'
        });

        if (response.ok) {
            const result = await response.json();
            showToast(result.message, 'info');
            pendingStaging = [];
            renderStaging();
        } else {
            const err = await response.json();
            showToast(err.error || 'Błąd podczas odrzucania transakcji.', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('Błąd połączenia z API.', 'error');
    }
}
