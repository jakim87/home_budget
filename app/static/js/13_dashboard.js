// --- DASHBOARD ---
// Zawsze cały majątek — Dashboard nie ma filtra kont. Zawężanie do konta robi
// „Widok konta" na pozostałych zakładkach.
let dashWidok = 'razem';          // wykres majątku: 'razem' | 'typy'
let dashZakres = '12';            // ostatnie '6' | '12' miesięcy albo 'all'; domyślnie rok
let dashWybranyMiesiac = null;    // 'RRRR-MM' wybrany kliknięciem w wykres; null = bieżący

// Kolejność = kolejność warstw (od dołu) i wierszy tabeli udziałów. Kredyt na końcu:
// jedyny typ, który z założenia jest pod zerem.
const TYPY_KONT = [
    { klucz: 'ROR', etykieta: 'Rachunki bieżące (ROR)', kolor: PALETA.lupek },
    { klucz: 'KO', etykieta: 'Oszczędnościowe (KO)', kolor: PALETA.szalwia },
    { klucz: 'Rach. Maklerski', etykieta: 'Rachunek maklerski', kolor: PALETA.miod },
    { klucz: 'IKZE', etykieta: 'IKZE', kolor: PALETA.sliwka },
    { klucz: 'Bez typu', etykieta: 'Bez typu (np. gotówka)', kolor: PALETA.popiel },
    { klucz: 'Kredyt', etykieta: 'Kredyty i karty', kolor: PALETA.umbra },
];

const MIESIACE_DOPELNIACZ = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];
const MIESIACE_MIANOWNIK = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
const MIESIACE_KROTKO = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];

function przesunMiesiac(ym, oIle) {
    const [y, m] = ym.split('-').map(Number);
    const d = new Date(y, m - 1 + oIle, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
const dzisiejszyMiesiac = () => toLocalISODate(new Date()).slice(0, 7);
const koniecMiesiaca = ym => `${MIESIACE_DOPELNIACZ[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}`;
const nazwaMiesiaca = ym => `${MIESIACE_MIANOWNIK[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}`;
const etykietaMiesiaca = ym => `${MIESIACE_KROTKO[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}`;

window.setNetWorthView = function(widok) {
    dashWidok = widok;
    renderNetWorthHistoryChart();
};

window.setNetWorthRange = function(zakres) {
    dashZakres = zakres;
    renderDashboard();
};

window.wybierzMiesiacDashboardu = function(ym) {
    dashWybranyMiesiac = ym;
    renderDashboard();
};

// Przycisk przełącznika w stylu istniejących (aktywny: wypełniony, reszta: szary).
function oznaczPrzelacznik(id, aktywny) {
    const el = document.getElementById(id);
    if (!el) return;
    el.setAttribute('aria-pressed', String(aktywny));
    el.className = aktywny
        ? 'px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white font-medium transition-colors'
        : 'px-3 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-600 font-medium hover:bg-slate-200 transition-colors';
}

function renderDashboard() {
    // Net Worth
    const { suma: netWorth, brak } = sumaSaldPLN(accounts);
    const netWorthEl = document.getElementById('dashboard-net-worth');
    if (netWorthEl) {
        netWorthEl.textContent = `${formatKwota(netWorth)} PLN`;
    }
    const noteEl = document.getElementById('dashboard-net-worth-note');
    if (noteEl) {
        const walutowe = accounts.some(a => a.currency && a.currency !== 'PLN');
        const dataKursu = Object.values(currencies)[0]?.date;
        noteEl.textContent = brak.length
            ? `Bez kont w: ${brak.join(', ')} — brak kursu NBP`
            : (walutowe && dataKursu ? `Konta walutowe przeliczone po kursie NBP z ${dataKursu}` : '');
        noteEl.classList.toggle('hidden', !noteEl.textContent);
    }

    computeNetWorthSeries();
    if (dashWybranyMiesiac && !netWorthSeriesFull.some(p => p.month === dashWybranyMiesiac)) {
        dashWybranyMiesiac = null;  // miesiąc zniknął z historii (np. po usunięciu transakcji)
    }
    renderZmianyMajatku(netWorth);
    renderNetWorthHistoryChart();
    renderObrotyKategorii();
    renderStrukturaMajatku();
    renderWyborMiesiaca();
    // renderDashboardChart() nie stoi tu celowo — jej canvas jest w zakładce Podsumowanie
    // i renderuje go renderSummary() (12_summary.js), żeby nie rysować wykresu do ukrytego
    // (display:none) kontenera o zerowej szerokości.
}

// --- MAJĄTEK W CZASIE ---
// Net worth to suma prefiksowa transakcji w czasie (stan, nie strumień).
// Liczymy ją RAZ (jeden przebieg po już załadowanych `transactions`) —
// wybór zakresu w UI to potem tylko wycinanie gotowej tablicy, bez nowego zapytania.
// Każdy punkt: { month, value, typy: {typ: PLN}, konta: {typ: liczba kont z transakcją do końca miesiąca} }.
let netWorthSeriesFull = [];
let netWorthChart = null;

function computeNetWorthSeries() {
    const sorted = transactions
        .filter(t => t.date)
        .sort((a, b) => (a.date < b.date ? -1 : (a.date > b.date ? 1 : 0)));
    if (sorted.length === 0) { netWorthSeriesFull = []; return; }

    const firstYM = sorted[0].date.slice(0, 7);
    const todayYM = dzisiejszyMiesiac();
    const lastTxYM = sorted[sorted.length - 1].date.slice(0, 7);
    const lastYM = lastTxYM > todayYM ? lastTxYM : todayYM;

    // Konta zamknięte też — ich historia nadal składa się na majątek z przeszłości.
    const kontoById = {};
    [...accounts, ...inactiveAccounts].forEach(a => { kontoById[a.id] = a; });

    // Saldo narasta osobno w każdym typie i walucie, a dopiero na koniec miesiąca jest
    // wyceniane po ówczesnym kursie — konto EUR bez ruchu i tak zmienia wartość w PLN.
    let idx = 0;
    const narastajaco = {};   // typ -> waluta -> suma
    const kontaTypu = {};     // typ -> Set(id konta)
    const series = [];
    for (let ym = firstYM; ym <= lastYM; ym = przesunMiesiac(ym, 1)) {
        const [yy, mm] = ym.split('-').map(Number);
        const monthEndStr = `${ym}-${String(new Date(yy, mm, 0).getDate()).padStart(2, '0')}`;
        while (idx < sorted.length && sorted[idx].date <= monthEndStr) {
            const t = sorted[idx];
            const konto = kontoById[t.account_id];
            const typ = (konto && konto.account_type) || 'Bez typu';
            const waluta = (konto && konto.currency) || 'PLN';
            narastajaco[typ] = narastajaco[typ] || {};
            narastajaco[typ][waluta] = (narastajaco[typ][waluta] || 0) + t.amount;
            (kontaTypu[typ] = kontaTypu[typ] || new Set()).add(t.account_id);
            idx++;
        }
        const typy = {};
        let value = 0;
        for (const [typ, waluty] of Object.entries(narastajaco)) {
            for (const [waluta, suma] of Object.entries(waluty)) {
                const kurs = kursPLN(waluta, ym);
                if (kurs === null) continue;
                typy[typ] = (typy[typ] || 0) + suma * kurs;
                value += suma * kurs;
            }
        }
        const konta = Object.fromEntries(Object.entries(kontaTypu).map(([typ, s]) => [typ, s.size]));
        series.push({ month: ym, value, typy, konta });
    }
    netWorthSeriesFull = series;
}

// Porównanie dzisiejszego majątku z końcem poprzedniego miesiąca i z końcem tego samego
// miesiąca rok wcześniej. Procent tylko od dodatniej bazy — od ujemnej nic nie znaczy.
// Brak punktu w historii = null („brak danych"), nigdy porównanie z zerem.
function zmianyMajatku(seria, teraz, dzisYM) {
    const porownaj = ym => {
        const p = seria.find(x => x.month === ym);
        if (!p) return null;
        const zmiana = Math.round((teraz - p.value) * 100) / 100 || 0;  // do grosza; -0 → 0
        return { miesiac: ym, wartosc: p.value, zmiana, procent: p.value > 0 ? zmiana / p.value : null };
    };
    return { miesiac: porownaj(przesunMiesiac(dzisYM, -1)), rok: porownaj(przesunMiesiac(dzisYM, -12)) };
}

function renderZmianyMajatku(netWorth) {
    const z = zmianyMajatku(netWorthSeriesFull, netWorth, dzisiejszyMiesiac());
    [['mc', z.miesiac], ['rok', z.rok]].forEach(([klucz, p]) => {
        const kiedy = document.getElementById(`dashboard-delta-${klucz}-kiedy`);
        const wartosc = document.getElementById(`dashboard-delta-${klucz}-wartosc`);
        const zmiana = document.getElementById(`dashboard-delta-${klucz}-zmiana`);
        if (!kiedy || !wartosc || !zmiana) return;
        kiedy.textContent = p ? `koniec ${koniecMiesiaca(p.miesiac)}` : 'brak danych';
        wartosc.textContent = p ? `${formatKwota(p.wartosc)} PLN` : '—';
        if (!p) { zmiana.textContent = ''; return; }
        if (p.zmiana === 0) { zmiana.textContent = 'bez zmian'; zmiana.className = 'text-xs font-medium text-slate-500'; return; }
        const procent = p.procent === null ? '' : ` (${p.procent >= 0 ? '+' : '−'}${Math.abs(p.procent * 100).toFixed(1).replace('.', ',')}%)`;
        zmiana.textContent = `${p.zmiana >= 0 ? '▲ +' : '▼ −'}${formatKwota(Math.abs(p.zmiana))} PLN${procent}`;
        zmiana.className = `text-xs font-medium whitespace-nowrap ${p.zmiana >= 0 ? 'text-emerald-600' : 'text-rose-600'}`;
    });
}

// Warstwy wykresu „Wg typu kont": dodatnie salda piętrzą się w górę od zera, ujemne w dół.
// Typ z saldem 0 zostaje na swoim miejscu w stosie (zerowa grubość) — wbudowane piętrzenie
// Chart.js sprowadzało go do osi i jego warstwa przecinała warstwy leżące niżej.
// Zwraca dla każdego klucza górną krawędź w stosie dodatnim i dolną w ujemnym.
function ulozWarstwy(wartosci, klucze) {
    const gora = klucze.map(() => []);
    const dol = klucze.map(() => []);
    wartosci.forEach((typy, j) => {
        let g = 0, d = 0;
        klucze.forEach((k, i) => {
            const v = typy[k] || 0;
            g += Math.max(v, 0);
            d += Math.min(v, 0);
            gora[i][j] = g;
            dol[i][j] = d;
        });
    });
    return { gora, dol };
}

function widocznaSeria() {
    if (dashZakres === 'all') return netWorthSeriesFull;
    return netWorthSeriesFull.slice(-Number(dashZakres));
}

function renderNetWorthHistoryChart() {
    oznaczPrzelacznik('networth-view-razem', dashWidok === 'razem');
    oznaczPrzelacznik('networth-view-typy', dashWidok === 'typy');
    ['6', '12', 'all'].forEach(z => oznaczPrzelacznik(`networth-range-${z}`, dashZakres === z));
    const info = document.getElementById('networth-info');
    if (info) {
        info.textContent = dashWidok === 'typy'
            ? 'Salda na koniec miesiąca w podziale na typ konta, przeliczone na PLN po kursie NBP z końca miesiąca. Linia majątku netto biegnie poniżej szczytu warstw o kwotę zobowiązań (kredyty i karty, pod zerem). Kliknij miesiąc, żeby zobaczyć udział majątku z jego końca.'
            : 'Suma sald wszystkich kont na koniec każdego miesiąca, przeliczona na PLN po kursie NBP z końca miesiąca. Kliknij miesiąc, żeby zobaczyć udział majątku z jego końca.';
    }

    const ctx = document.getElementById('networth-history-chart');
    if (!ctx) return;
    if (netWorthChart) { netWorthChart.destroy(); netWorthChart = null; }
    const punkty = widocznaSeria();
    if (punkty.length === 0) return;

    const miesiace = punkty.map(p => p.month);
    const linia = {
        label: 'Majątek netto',
        data: punkty.map(p => p.value),
        borderColor: dashWidok === 'typy' ? '#201f1d' : PALETA.ochra,
        backgroundColor: PALETA.ochra + '1F',
        fill: dashWidok === 'razem' ? 'origin' : false,
        cubicInterpolationMode: 'monotone',
        borderWidth: 2,
        pointRadius: miesiace.map(m => (m === dashWybranyMiesiac ? 5 : 0)),
        pointBackgroundColor: dashWidok === 'typy' ? '#201f1d' : PALETA.ochra,
        pointHoverRadius: 4,
        order: -1,   // linia na wierzchu warstw
    };

    let datasets = [linia];
    if (dashWidok === 'typy') {
        const typy = TYPY_KONT.filter(t => punkty.some(p => p.konta[t.klucz]));
        const { gora, dol } = ulozWarstwy(punkty.map(p => p.typy), typy.map(t => t.klucz));
        const warstwa = (t, data, fill, wDymku) => ({
            label: t.etykieta, typ: t.klucz, wDymku, ukryjWLegendzie: !wDymku,
            data, fill, cubicInterpolationMode: 'monotone',
            borderColor: t.kolor, backgroundColor: t.kolor + 'BF', borderWidth: 1, pointRadius: 0, pointHoverRadius: 0,
        });
        // Stos dodatni, potem ujemny — fill '-1' wypełnia do poprzedniej krawędzi tego samego stosu.
        const dodatnie = typy.map((t, i) => warstwa(t, gora[i], i === 0 ? 'origin' : '-1', true));
        const zUjemnymi = typy.map((t, i) => [t, i]).filter(([, i]) => dol[i].some((v, j) => v < (i === 0 ? 0 : dol[i - 1][j])));
        const ujemne = zUjemnymi.map(([t, i], n) => warstwa(t, dol[i], n === 0 ? 'origin' : '-1', false));
        datasets = [...dodatnie, ...ujemne, linia];
    }

    netWorthChart = new Chart(ctx, {
        type: 'line',
        data: { labels: miesiace.map(etykietaMiesiaca), datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            onClick: (evt, _el, chart) => {
                const trafienie = chart.getElementsAtEventForMode(evt, 'index', { intersect: false }, false)[0];
                if (!trafienie) return;
                const ym = miesiace[trafienie.index];
                // Po obsłudze zdarzenia: przerysowanie niszczy wykres, który je właśnie obsługuje.
                setTimeout(() => wybierzMiesiacDashboardu(ym === dashWybranyMiesiac ? null : ym));
            },
            plugins: {
                legend: {
                    display: dashWidok === 'typy',
                    position: 'bottom',
                    labels: { boxWidth: 12, filter: (item, data) => !data.datasets[item.datasetIndex].ukryjWLegendzie },
                },
                tooltip: {
                    // Typ pokazujemy raz i tylko w miesiącach, w których miał już jakieś konto.
                    filter: item => dashWidok === 'razem' || (item.dataset.wDymku && punkty[item.dataIndex].konta[item.dataset.typ] > 0),
                    callbacks: {
                        label: c => dashWidok === 'razem'
                            ? `Majątek netto: ${formatKwota(c.parsed.y)} PLN`
                            : `${c.dataset.label}: ${formatKwota(punkty[c.dataIndex].typy[c.dataset.typ] || 0)} PLN`,
                        footer: items => {
                            const p = items.length ? punkty[items[0].dataIndex] : null;
                            if (!p) return '';
                            return dashWidok === 'typy'
                                ? [`Majątek netto: ${formatKwota(p.value)} PLN`, 'Kliknij, aby wybrać miesiąc']
                                : 'Kliknij, aby wybrać miesiąc';
                        },
                    },
                },
            },
            scales: {
                y: {
                    ticks: {
                        callback: v => `${Number(v).toLocaleString('pl-PL', { useGrouping: 'always' })} PLN`
                    }
                }
            }
        }
    });
}

// --- UDZIAŁ MAJĄTKU WG TYPU KONT ---
// Udział liczony w aktywach (suma dodatnich sald typów); zobowiązania mają udział ujemny.
function strukturaMajatku(punkt) {
    const aktywa = Object.values(punkt.typy).reduce((s, v) => s + Math.max(v, 0), 0);
    return TYPY_KONT
        .filter(t => punkt.konta[t.klucz])
        .map(t => {
            const saldo = punkt.typy[t.klucz] || 0;
            return { typ: t.klucz, konta: punkt.konta[t.klucz], saldo, udzial: aktywa ? saldo / aktywa : 0 };
        });
}

// Punkt struktury: miesiąc wybrany na wykresie albo bieżący (seria może sięgać w przyszłość
// przez transakcje z datą przyszłą — „dziś" to bieżący miesiąc, nie ostatni punkt).
function punktStruktury() {
    const ym = dashWybranyMiesiac || dzisiejszyMiesiac();
    return netWorthSeriesFull.find(p => p.month === ym)
        || [...netWorthSeriesFull].reverse().find(p => p.month <= ym)
        || null;
}

function renderStrukturaMajatku() {
    const pasek = document.getElementById('dashboard-struktura-pasek');
    const body = document.getElementById('dashboard-struktura-body');
    const miesiacEl = document.getElementById('dashboard-struktura-miesiac');
    if (!pasek || !body || !miesiacEl) return;
    const punkt = punktStruktury();
    if (!punkt) {
        miesiacEl.textContent = '—';
        pasek.innerHTML = '';
        body.innerHTML = '<tr><td colspan="4" class="p-3 text-sm text-slate-500">Brak transakcji — udział pojawi się po dodaniu pierwszej.</td></tr>';
        return;
    }
    miesiacEl.textContent = koniecMiesiaca(punkt.month) + (dashWybranyMiesiac ? ' (miesiąc wybrany na wykresie)' : '');
    const wiersze = strukturaMajatku(punkt);
    const kolor = typ => TYPY_KONT.find(t => t.klucz === typ).kolor;
    const etykieta = typ => TYPY_KONT.find(t => t.klucz === typ).etykieta;
    const procent = u => `${u < 0 ? '−' : ''}${Math.abs(u * 100).toFixed(1).replace('.', ',')}%`;

    pasek.innerHTML = wiersze.filter(w => w.udzial > 0).map(w =>
        `<div style="width:${(w.udzial * 100).toFixed(2)}%;background:${kolor(w.typ)}" title="${escapeHtml(etykieta(w.typ))}: ${procent(w.udzial)}"></div>`
    ).join('');
    body.innerHTML = wiersze.map(w => `
        <tr>
            <td class="py-2 pr-3 border-b border-slate-100"><span class="inline-flex items-center gap-2"><span class="inline-block w-2.5 h-2.5 rounded-sm shrink-0" style="background:${kolor(w.typ)}"></span>${escapeHtml(etykieta(w.typ))}</span></td>
            <td class="py-2 pr-3 border-b border-slate-100 text-right tabular-nums hidden sm:table-cell">${w.konta}</td>
            <td class="py-2 pr-3 border-b border-slate-100 text-right tabular-nums whitespace-nowrap ${w.saldo < 0 ? 'text-rose-600' : ''}">${formatKwota(w.saldo)} PLN</td>
            <td class="py-2 border-b border-slate-100 text-right tabular-nums whitespace-nowrap">${procent(w.udzial)}</td>
        </tr>`).join('');
}

// --- PRZYCHODY I WYDATKI WG KATEGORII ---
const dashKategorie = new Set();   // id kategorii z filtra wykresu; pusty = wszystkie przychody i wydatki
let obrotyChart = null;

// Sumy przychodów i wydatków per miesiąc liczone DOKŁADNIE jak w Raportach (applyRptFilters +
// rptGroupByMonth w 16_reports.js), żeby „Szczegółowy raport" pokazał te same liczby: po kategorii
// rodzica, stronę wyznacza znak kwoty, bez przeliczania walut i bez przelewów wewnętrznych.
// Bez wybranych kategorii — domyślny zestaw Raportów (przychody i wydatki; kategorie systemowe
// odpadają). Transakcja z kategorią spoza słownika przechodzi filtr, jak w Raportach.
function obrotyMiesieczne(txs, wybrane) {
    const wynik = {};
    txs.forEach(t => {
        if (!t.date) return;
        const cat = categories.find(c => c.name === t.category);
        if (cat && cat.type === 'transfer') return;
        if (cat && (wybrane.size ? !wybrane.has(cat.id) : (cat.type !== 'income' && cat.type !== 'expense'))) return;
        const ym = t.date.slice(0, 7);
        wynik[ym] = wynik[ym] || { przychody: 0, wydatki: 0 };
        if (t.amount > 0) wynik[ym].przychody += t.amount;
        else wynik[ym].wydatki += Math.abs(t.amount);
    });
    return wynik;
}

// Kategorie do wyboru: przychody i wydatki bez systemowych (przelew nie jest ani jednym, ani drugim).
const kategorieObrotow = () => categories.filter(c => (c.type === 'income' || c.type === 'expense') && !c.is_system_category);

window.toggleDashKategorie = function() {
    const panel = document.getElementById('dash-cat-panel');
    if (!panel) return;
    const otworz = panel.classList.contains('hidden');
    if (otworz) {
        const grupa = (typ, tytul) => {
            const lista = kategorieObrotow().filter(c => c.type === typ);
            if (!lista.length) return '';
            return `<p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-2 mb-1 px-1">${tytul}</p>` + lista.map(c => `
                <label class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-50 cursor-pointer text-sm text-slate-700">
                    <input type="checkbox" class="dash-cat-check rounded border-slate-300 cursor-pointer" value="${c.id}" ${dashKategorie.has(c.id) ? 'checked' : ''} onchange="przelaczDashKategorie(${c.id}, this.checked)">
                    <span>${escapeHtml(c.name)}</span>
                </label>`).join('');
        };
        document.getElementById('dash-cat-list').innerHTML = grupa('expense', 'Wydatki') + grupa('income', 'Przychody');
    }
    panel.classList.toggle('hidden', !otworz);
    document.getElementById('dash-cat-btn')?.setAttribute('aria-expanded', String(otworz));
};

window.przelaczDashKategorie = function(id, zaznaczona) {
    if (zaznaczona) dashKategorie.add(id); else dashKategorie.delete(id);
    renderObrotyKategorii();
};

window.wyczyscDashKategorie = function() {
    dashKategorie.clear();
    document.querySelectorAll('.dash-cat-check').forEach(chk => { chk.checked = false; });
    renderObrotyKategorii();
};

document.addEventListener('click', e => {
    if (!e.target.closest('#dash-cat-wrap')) {
        document.getElementById('dash-cat-panel')?.classList.add('hidden');
        document.getElementById('dash-cat-btn')?.setAttribute('aria-expanded', 'false');
    }
});

function renderObrotyKategorii() {
    // Kategoria mogła zniknąć ze słownika od ostatniego wyboru.
    [...dashKategorie].forEach(id => { if (!kategorieObrotow().some(c => c.id === id)) dashKategorie.delete(id); });
    const etykieta = document.getElementById('dash-cat-label');
    if (etykieta) {
        const wybrane = kategorieObrotow().filter(c => dashKategorie.has(c.id));
        etykieta.textContent = wybrane.length === 0 ? 'Kategorie: wszystkie'
            : wybrane.length === 1 ? wybrane[0].name : `Kategorie: ${wybrane.length} wybrane`;
    }

    const ctx = document.getElementById('dashboard-obroty-chart');
    if (!ctx) return;
    if (obrotyChart) { obrotyChart.destroy(); obrotyChart = null; }
    const miesiace = widocznaSeria().map(p => p.month);
    if (miesiace.length === 0) return;
    const obroty = obrotyMiesieczne(transactions, dashKategorie);
    const przychody = miesiace.map(m => (obroty[m] ? obroty[m].przychody : 0));
    const wydatki = miesiace.map(m => (obroty[m] ? obroty[m].wydatki : 0));
    // Wybrany miesiąc w pełnym kolorze, pozostałe przygaszone.
    const kolory = kolor => miesiace.map(m => kolor + (!dashWybranyMiesiac || m === dashWybranyMiesiac ? 'BF' : '40'));

    obrotyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: miesiace.map(etykietaMiesiaca),
            datasets: [
                { label: 'Przychody', data: przychody, backgroundColor: kolory(PALETA.ochra), borderColor: PALETA.ochra, borderWidth: 1, borderRadius: 4 },
                { label: 'Wydatki', data: wydatki, backgroundColor: kolory(PALETA.stal), borderColor: PALETA.stal, borderWidth: 1, borderRadius: 4 },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            onClick: (evt, _el, chart) => {
                const trafienie = chart.getElementsAtEventForMode(evt, 'index', { intersect: false }, false)[0];
                if (!trafienie) return;
                const ym = miesiace[trafienie.index];
                // Po obsłudze zdarzenia: przerysowanie niszczy wykres, który je właśnie obsługuje.
                setTimeout(() => wybierzMiesiacDashboardu(ym === dashWybranyMiesiac ? null : ym));
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: c => `${c.dataset.label}: ${formatKwota(c.parsed.y)} PLN`,
                        footer: items => {
                            const i = items.length ? items[0].dataIndex : null;
                            if (i === null) return '';
                            const bilans = przychody[i] - wydatki[i];
                            return [`Bilans: ${bilans >= 0 ? '+' : '−'}${formatKwota(Math.abs(bilans))} PLN`, 'Kliknij, aby wybrać miesiąc'];
                        },
                    },
                },
            },
            scales: {
                y: { beginAtZero: true, ticks: { callback: v => `${Number(v).toLocaleString('pl-PL', { useGrouping: 'always' })} PLN` } },
            },
        },
    });
}

// „Pokaż transakcje": Historia operacji w wybranym miesiącu. Dashboard liczy wszystkie konta,
// więc „Widok konta" przełączamy na wszystkie — inaczej lista ukryłaby część transakcji.
window.pokazTransakcjeMiesiaca = async function(ym) {
    globalAccountFilter = '';
    const sel = document.getElementById('global-account-filter');
    if (sel) sel.value = '';
    const [y, m] = ym.split('-').map(Number);
    viewDate = new Date(y, m - 1, 1);
    await fetchRecurringPreview(y, m);
    switchTab('transactions');
};

window.pokazRaportMiesiaca = function(ym) {
    const [y, m] = ym.split('-').map(Number);
    rptPokazOkres(`${ym}-01`, `${ym}-${String(new Date(y, m, 0).getDate()).padStart(2, '0')}`, [...dashKategorie]);
};

// Pasek pod wykresami: który miesiąc jest wybrany, przejścia do szczegółów i powrót do bieżącego.
// Raporty są ukryte na telefonie (06_tabs / base.html), więc ich przycisk też.
function renderWyborMiesiaca() {
    document.querySelectorAll('.dashboard-wybor').forEach(el => {
        el.classList.toggle('hidden', !dashWybranyMiesiac);
        if (!dashWybranyMiesiac) { el.innerHTML = ''; return; }
        const ym = escapeHtml(dashWybranyMiesiac);
        const przycisk = 'px-3 py-1.5 text-sm rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 font-medium';
        el.innerHTML = `
            <span class="text-sm font-medium text-slate-700 mr-auto">Wybrany miesiąc: ${escapeHtml(nazwaMiesiaca(dashWybranyMiesiac))}</span>
            <button type="button" onclick="pokazTransakcjeMiesiaca('${ym}')" class="${przycisk}">Pokaż transakcje →</button>
            <button type="button" onclick="pokazRaportMiesiaca('${ym}')" class="${przycisk} hidden sm:inline-block">Szczegółowy raport →</button>
            <button type="button" onclick="wybierzMiesiacDashboardu(null)" class="text-sm text-slate-500 hover:text-slate-700 underline">Wyczyść ×</button>`;
    });
}

// Canvas #dashboard-chart stoi w zakladce Podsumowanie, nie Dashboard — nazwa (i
// dashboardView ponizej) zostala z czasow, gdy tam stal wykres. Wolane z renderSummary()
// (12_summary.js), nie z renderDashboard(). Filtr kont jak reszta Podsumowania: „Widok konta".
let dashboardView = 'monthly';
let dashboardChart = null;

window.setDashboardView = function(view) {
    dashboardView = view;
    const monthlyBtn = document.getElementById('dashboard-toggle-monthly');
    const yearlyBtn = document.getElementById('dashboard-toggle-yearly');
    const activeClass = 'px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white font-medium transition-colors';
    const inactiveClass = 'px-3 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-600 font-medium hover:bg-slate-200 transition-colors';
    if (view === 'monthly') {
        monthlyBtn.className = activeClass;
        yearlyBtn.className = inactiveClass;
    } else {
        yearlyBtn.className = activeClass;
        monthlyBtn.className = inactiveClass;
    }
    renderDashboardChart();
};

function renderDashboardChart() {
    const ctx = document.getElementById('dashboard-chart');
    if (!ctx) return;

    const monthNames = MIESIACE_KROTKO;

    const zakresTx = globalAccountFilter ? transactions.filter(t => t.account_id == globalAccountFilter) : transactions;
    const nonTransferTx = zakresTx.filter(t => {
        const cat = categories.find(c => c.name === t.category);
        return !cat || cat.type !== 'transfer';
    });

    let labels, incomeData, expenseData;

    if (dashboardView === 'monthly') {
        const now = new Date();
        const months = [];
        for (let i = 11; i >= 0; i--) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            months.push({ year: d.getFullYear(), month: d.getMonth() + 1, label: `${monthNames[d.getMonth()]} ${d.getFullYear()}` });
        }
        labels = months.map(m => m.label);
        incomeData = months.map(m =>
            nonTransferTx.filter(t => {
                if (!t.date) return false;
                const [ty, tm] = t.date.split('-').map(Number);
                return ty === m.year && tm === m.month && t.amount > 0;
            }).reduce((s, t) => s + t.amount, 0)
        );
        expenseData = months.map(m =>
            nonTransferTx.filter(t => {
                if (!t.date) return false;
                const [ty, tm] = t.date.split('-').map(Number);
                return ty === m.year && tm === m.month && t.amount < 0;
            }).reduce((s, t) => s + Math.abs(t.amount), 0)
        );
    } else {
        const currentYear = new Date().getFullYear();
        const years = Array.from({ length: 5 }, (_, i) => currentYear - 4 + i);
        labels = years.map(String);
        incomeData = years.map(y =>
            nonTransferTx.filter(t => t.date && t.date.startsWith(String(y)) && t.amount > 0)
                .reduce((s, t) => s + t.amount, 0)
        );
        expenseData = years.map(y =>
            nonTransferTx.filter(t => t.date && t.date.startsWith(String(y)) && t.amount < 0)
                .reduce((s, t) => s + Math.abs(t.amount), 0)
        );
    }

    if (dashboardChart) {
        dashboardChart.destroy();
        dashboardChart = null;
    }

    dashboardChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Przychody',
                    data: incomeData,
                    backgroundColor: PALETA.ochra + 'BF',
                    borderColor: PALETA.ochra,
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: 'Wydatki',
                    data: expenseData,
                    backgroundColor: PALETA.stal + 'BF',
                    borderColor: PALETA.stal,
                    borderWidth: 1,
                    borderRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${formatKwota(ctx.parsed.y)} PLN`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: val => `${val.toLocaleString('pl-PL', { useGrouping: 'always' })} PLN` }
                }
            }
        }
    });
}
