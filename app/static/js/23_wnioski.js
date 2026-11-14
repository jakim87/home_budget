// =============================================
// ZAKŁADKA: WNIOSKI
// =============================================
// Na górze wnioski z wybranego miesiąca (reguły: 22_wnioski_reguly.js), pod nimi widoki —
// filtry zapisywane pod nazwą (trzy wbudowane tutaj, do 7 własnych na koncie: /api/views).
// Liczy w przeglądarce z globalnego stanu, jak Dashboard. „Widok konta” nie dotyczy tej
// zakładki (06_tabs.js go chowa) — konta wybiera się w filtrze widoku.
// Kwoty w PLN po kursie NBP z końca miesiąca; przelewy między własnymi kontami poza sumami
// (poza widokiem sald — saldo bez nich nigdy by nie rosło).

const WN_NA_KARCIE = 6;
const WN_MAKS_WLASNYCH = 7;
const WN_MAKS_ULUBIONYCH = 10;
const WN_MAKS_LINII = 10;
const WN_MAKS_OPERACJI = 100;
const WN_KOLORY = [PALETA.stal, PALETA.ochra, PALETA.szalwia, PALETA.sliwka, PALETA.lupek,
    PALETA.umbra, PALETA.miod, PALETA.popiel, PALETA.oliwka, PALETA.grafit];

// Konfiguracja widoku. `dzien` istnieje tylko dla kroku „Pokaż operacje z tego dnia” i nie
// jest zapisywany (decyzja 16). Pola i wartości muszą zgadzać się z WidokConfigSchema.
const WN_PUSTY = { okres: { typ: 'miesiac' }, konta: [], kategorie: [], kontrahenci: [], liczy: 'oba', pokaz: 'kategorie', sald: 'auto', ulubione: false };
const WN_WBUDOWANE = [
    { id: 'w1', nazwa: 'Miesiąc w liczbach', wbudowany: true, cfg: { ...WN_PUSTY } },
    { id: 'w2', nazwa: 'Przychody i wydatki w czasie', wbudowany: true, cfg: { ...WN_PUSTY, okres: { typ: 'n', n: 12 }, pokaz: 'czas' } },
    { id: 'w3', nazwa: 'Saldo na koniec miesiąca', wbudowany: true, cfg: { ...WN_PUSTY, okres: { typ: 'n', n: 6 }, pokaz: 'salda' } },
];
const WN_TYPY_KONT = [
    { klucz: 'ROR', etykieta: 'Rachunki bieżące', kolor: PALETA.lupek },
    { klucz: 'KO', etykieta: 'Oszczędnościowe', kolor: PALETA.szalwia },
    { klucz: 'Rach. Maklerski', etykieta: 'Rachunki maklerskie', kolor: PALETA.miod },
    { klucz: 'IKZE', etykieta: 'IKZE', kolor: PALETA.sliwka },
    { klucz: 'Bez typu', etykieta: 'Bez typu (np. gotówka)', kolor: PALETA.popiel },
    { klucz: 'Kredyt', etykieta: 'Kredyty i karty', kolor: PALETA.umbra },
];

// --- Stan zakładki ---
let wnYm = null;              // wybrany miesiąc 'RRRR-MM'; null = domyślny (ostatni pełny)
let wnWszystkie = false;      // „Pokaż wszystkie” wnioski
let wnAktywnyId = 'w1';       // chip widoku: 'w1'…'w3' wbudowane, 's<id>' własne, null = niezapisany
let wnCfg = { ...WN_PUSTY };
let wnTabela = 'zestawienie';
let wnTryb = null;            // null | 'zapis' | 'usun'
let wnOpisAdHoc = '';
let wnSciezka = [];           // poprzednie kroki rozbicia: { etykieta, stan }
let wnKartaKat = null;        // ID kategorii, której kartę widać
let wnPokazPuste = false;
let wnInfoOtwarte = false;
let wnWykres = null, wnKartaWykres = null, wnMenuZrodlo = null;
let wnPamiec = null, wnPamiecZrodlo = [];

const wn$ = id => document.getElementById(id);
const wnKopia = o => JSON.parse(JSON.stringify(o));
const wnEsc = s => escapeHtml(s === null || s === undefined ? '' : s);
const wnDzis = () => toLocalISODate(new Date());

// Dane liczone raz na stan z /api/init (fetchInitialData podmienia tablice, więc wystarczy
// porównać referencje) — zmiana filtra nie przelicza wszystkiego od nowa.
function wnD() {
    const zrodlo = [transactions, categories, accounts, inactiveAccounts, monthlyRates, currencies, wnDzis()];
    if (!wnPamiec || zrodlo.some((x, k) => x !== wnPamiecZrodlo[k])) {
        const d = wnPrzygotuj({ transakcje: transactions, kategorie: categories, konta: [...accounts, ...inactiveAccounts], kurs: kursPLN, dzis: wnDzis() });
        d.salda = saldaKontMiesiecznie(transactions);
        wnPamiec = d;
        wnPamiecZrodlo = zrodlo;
    }
    return wnPamiec;
}

function wnI() {
    const d = wnD();
    if (wnYm === null || !d.idx.has(wnYm)) wnYm = d.miesiace[Math.max(0, d.biezacy - 1)];
    return d.idx.get(wnYm);
}
const wnYmZ = j => wnD().miesiace[j];
const wnRok = j => wnYmZ(j).slice(0, 4);
const wnNr = j => wnNrM(wnYmZ(j));
const wnNazwa = j => wnNazwaM(wnYmZ(j));
const wnKr = j => WN_M_KR[wnNr(j)] + (wnNr(j) === 0 ? ' ' + wnRok(j).slice(2) : '');
const wnDataKr = d => `${Number(d.slice(8))} ${WN_M_KR[Number(d.slice(5, 7)) - 1]} ${d.slice(0, 4)}`;
function wnEtykietaZakresu([od, doM]) {
    if (od === doM) return wnNazwa(od);
    return `${WN_M_KR[wnNr(od)]}${wnRok(od) !== wnRok(doM) ? ' ' + wnRok(od) : ''} – ${WN_M_KR[wnNr(doM)]} ${wnRok(doM)}`;
}
const wnKontoNazwa = id => ((accounts.find(a => a.id === id) || inactiveAccounts.find(a => a.id === id)) || {}).name || '';
const wnKategoria = id => categories.find(c => c.id === id) || null;
const wnKontrahent = id => contractors.find(c => c.id === id) || null;
const wnUlubione = () => new Set(accounts.filter(a => a.is_favorite).map(a => a.id));

// --- Liczenie widoku (czyste względem DOM) ---
function wnZakres(c, i = wnI()) {
    const o = c.okres;
    if (o.typ === 'n') return [Math.max(0, i - o.n + 1), i];
    if (o.typ === 'rok') return [Math.max(0, i - wnNr(i)), i];
    if (o.typ === 'calosc') return [0, i];
    return [i, i];
}
function wnFiltruj(c, [od, doM]) {
    const ul = c.ulubione ? wnUlubione() : null;
    return wnD().ops.filter(o => o.j >= od && o.j <= doM
        && (!c.dzien || Number(o.data.slice(8)) === c.dzien)
        && (!c.konta.length || c.konta.includes(o.konto))
        && (!ul || ul.has(o.konto))
        && (!c.kategorie.length || c.kategorie.includes(o.katId))
        && (!c.kontrahenci.length || c.kontrahenci.includes(o.kontrId)));
}
const wnLiczone = (c, o) => (o.kwota < 0 ? c.liczy !== 'przychody' : c.liczy !== 'wydatki');
function wnSumy(ops) {
    let inc = 0, exp = 0;
    ops.forEach(o => { if (o.kwota > 0) inc += o.kwota; else exp -= o.kwota; });
    return { inc: wnGrosz(inc), exp: wnGrosz(exp), n: ops.length };
}
// Element zestawienia: kategoria (po ID ze słownika) albo kontrahent (po ID, a bez wpisu
// w słowniku — po nazwie, wtedy bez rozbijania, bo filtr kontrahentów zna tylko ID).
function wnGrupa(o, pole) {
    if (pole === 'kategoria') return { klucz: `c${o.katId ?? o.kat}`, nazwa: o.kat, id: o.katId };
    return { klucz: o.kontrId ? `k${o.kontrId}` : `n${o.nazwa}`, nazwa: o.kontrId ? ((wnKontrahent(o.kontrId) || {}).name || o.nazwa) : o.nazwa, id: o.kontrId };
}
function wnZestawienie(ops, pole) {
    const mapa = new Map();
    ops.forEach(o => {
        const g = wnGrupa(o, pole), k = `${g.klucz}|${o.kwota > 0 ? 'p' : 'w'}`;
        const e = mapa.get(k) || { ...g, przychod: o.kwota > 0, kwota: 0, n: 0 };
        e.kwota += Math.abs(o.kwota); e.n++;
        mapa.set(k, e);
    });
    return [...mapa.values()].map(e => ({ ...e, kwota: wnGrosz(e.kwota) })).sort((a, b) => b.kwota - a.kwota);
}

// Salda: konta aktywne w zakresie filtra, saldo w walucie konta i w PLN po kursie z końca miesiąca.
function wnKontaWZakresie(c) {
    const ul = wnUlubione();
    return accounts.filter(a => (!c.konta.length || c.konta.includes(a.id)) && (!c.ulubione || ul.has(a.id)));
}
function wnSaldo(id, j) {
    if (j < 0) return 0;
    const s = wnD().salda, k = s.miesiace.indexOf(wnYmZ(j));
    if (k < 0 || !(id in s.salda)) return 0;
    return s.start[id] > k ? 0 : s.salda[id][k];
}
function wnSaldoPLN(a, j) {
    const kurs = kursPLN(a.currency || 'PLN', j < 0 ? wnYmZ(0) : wnYmZ(j));
    return kurs === null ? null : wnGrosz(wnSaldo(a.id, j) * kurs);
}
function wnSumaSald(konta, j) {
    return wnGrosz(konta.reduce((s, a) => s + (wnSaldoPLN(a, j) ?? 0), 0));
}
const wnOpcjeSald = c => (wnKontaWZakresie(c).length <= WN_MAKS_LINII ? ['konta', 'typy', 'razem'] : ['razem', 'typy']);
function wnTrybSald(c) { const o = wnOpcjeSald(c); return o.includes(c.sald) ? c.sald : o[0]; }

// --- Widoki zapisane ---
const wnWidoki = () => [...WN_WBUDOWANE, ...savedViews.map(v => ({ id: `s${v.id}`, sid: v.id, nazwa: v.name, cfg: { ...WN_PUSTY, ...v.config } }))];
const wnAktywny = () => wnWidoki().find(v => v.id === wnAktywnyId) || null;
function wnDoZapisu(c) {
    const reszta = { ...c };
    delete reszta.dzien;
    ['konta', 'kategorie', 'kontrahenci'].forEach(p => { reszta[p] = [...new Set(reszta[p])].sort((a, b) => a - b); });
    return reszta;
}
const wnZmieniony = () => { const w = wnAktywny(); return !!w && JSON.stringify(wnDoZapisu(w.cfg)) !== JSON.stringify(wnDoZapisu(wnCfg)); };

// Zapisany widok wskazuje elementy po ID; usunięte z czasem konto, kategoria albo kontrahent
// wypada z filtra przy wyświetlaniu, a widok mówi o tym notką (decyzja 12).
function wnOczyscCfg(c) {
    const jest = {
        konta: new Set(accounts.map(a => a.id)),
        kategorie: new Set(categories.map(x => x.id)),
        kontrahenci: new Set(contractors.map(x => x.id)),
    };
    let usuniete = 0;
    const czysta = { ...c };
    Object.keys(jest).forEach(p => {
        czysta[p] = c[p].filter(id => jest[p].has(id));
        usuniete += c[p].length - czysta[p].length;
    });
    return { cfg: czysta, usuniete };
}

// --- Wnioski: render ---
function wnIskraSvg(x) {
    const wart = x.iskra.wartosci, W = 140, H = 34, n = wart.length, gap = 3, bw = (W - gap * (n - 1)) / n;
    const max = Math.max(0, ...wart), min = Math.min(0, ...wart), rozp = max - min || 1, y0 = H * max / rozp;
    const rects = wart.map((v, k) => {
        const h = Math.max(1, Math.abs(v) / rozp * H), y = v >= 0 ? y0 - h : y0;
        return `<rect class="${k === n - 1 ? 'wn-on' : ''}" x="${(k * (bw + gap)).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}"></rect>`;
    }).join('');
    const ymK = k => wnPrzesun(x.iskra.od, k);
    const opis = wart.map((v, k) => `${WN_M_KR[wnNrM(ymK(k))]}: ${Math.round(v)}`).join(', ');
    return `<div><svg class="wn-iskra" viewBox="0 0 ${W} ${H}" role="img" aria-label="Ostatnie ${n} miesięcy"><title>${wnEsc(opis)}</title>${rects}</svg>`
        + `<span class="wn-sparklab"><span>${WN_M_KR[wnNrM(ymK(0))]}</span><span>${WN_M_KR[wnNrM(ymK(n - 1))]}</span></span></div>`;
}
function wnKartaWniosku(x) {
    const el = document.createElement('article');
    el.className = 'wn-ins';
    el.innerHTML = `<div class="wn-ins-top"><span class="wn-kind">${wnEsc(x.rodzaj)}</span><span class="wn-pill wn-ton-${x.ton}">${wnEsc(x.plakietka)}</span></div>
        <h3>${wnEsc(x.tytul)}</h3>
        <p class="wn-big"><b>${wnEsc(x.kwota)}</b>${x.delta ? `<span class="wn-delta wn-ton-${x.ton}">${wnEsc(x.delta)}</span>` : ''}${x.suf ? `<span class="wn-suf">${wnEsc(x.suf)}</span>` : ''}</p>
        <p class="wn-why">${wnEsc(x.opis)}</p>
        ${x.meta ? `<p class="wn-meta">${wnEsc(x.meta)}</p>` : ''}
        ${x.iskra ? wnIskraSvg(x) : ''}
        <div class="wn-ins-acts"><button type="button" class="wn-link" data-a="pokaz">Pokaż operacje</button></div>`;
    el.querySelector('[data-a="pokaz"]').addEventListener('click', () => wnPokazZWniosku(x));
    return el;
}

function renderWnioskiKarty() {
    const d = wnD(), i = wnI(), ym = wnYmZ(i);
    wn$('wn-mies-label').textContent = wnCap(wnNazwa(i)) + (i === d.biezacy ? ' (trwa)' : '');
    wn$('wn-mies-prev').disabled = i === 0;
    wn$('wn-mies-next').disabled = i === d.biezacy;
    wn$('wn-tytul').textContent = `Najważniejsze ${wnMsc(ym)}`;
    const w = wnWnioskiZa(d, ym), box = wn$('wn-lista'), stopka = wn$('wn-stopka'), opis = wn$('wn-opis');
    box.className = ''; box.innerHTML = ''; stopka.innerHTML = ''; opis.textContent = '';
    const notka = d.brakKursu.size ? `<p class="wn-notka">Bez operacji kont w: ${wnEsc([...d.brakKursu].join(', '))} — brak kursu NBP.</p>` : '';
    if (!d.ops.length) {
        box.innerHTML = '<p class="wn-pusto">Brak operacji. Wnioski pojawią się po dodaniu albo zaimportowaniu transakcji.</p>';
        return;
    }
    if (w.stan === 'trwa') {
        box.innerHTML = `<p class="wn-pusto">${wnEsc(wnCap(WN_M_MIAN[wnNr(i)]))} jeszcze trwa, a wnioski liczymy z pełnych miesięcy. Widoki poniżej pokazują ten miesiąc normalnie.`
            + (i > 0 ? ` <button type="button" class="wn-link" id="wn-do-poprz">Pokaż ${wnEsc(WN_M_MIAN[wnNr(i - 1)])}</button>` : '') + '</p>';
        if (wn$('wn-do-poprz')) wn$('wn-do-poprz').addEventListener('click', () => wnZmienMiesiac(-1));
        return;
    }
    if (w.stan === 'luka') {
        const konta = w.konta.map(wnKontoNazwa).filter(Boolean).join(', ');
        const co = konta ? `brakuje operacji z konta: ${wnEsc(konta)}, choć zwykle jest ich sporo` : 'nie ma żadnych operacji';
        box.innerHTML = `<p class="wn-pusto">W tym miesiącu ${co}. Wygląda to na niezaimportowane wyciągi, więc wniosków nie liczymy — wyszłyby fałszywe. Ten miesiąc wypada też z porównań w kolejnych.</p>`;
        return;
    }
    if (w.stan !== 'ok') {
        box.innerHTML = '<p class="wn-pusto">Za mało historii. Wnioski pojawiają się, gdy przed wybranym miesiącem są co najmniej 3 pełne miesiące danych.</p>';
        return;
    }
    const pokaz = wnWszystkie ? w.lista : w.lista.slice(0, WN_NA_KARCIE);
    opis.textContent = `Porównanie z typowym miesiącem, czyli medianą z ${w.okno} poprzednich.`
        + (w.lista.length ? ` ${w.lista.length} ${odmiana(w.lista.length, ['wniosek', 'wnioski', 'wniosków'])}, od największej kwoty.` : '');
    if (!w.lista.length) box.innerHTML = '<p class="wn-pusto">Nic nietypowego. Wydatki i przychody w normie.</p>';
    else { box.className = 'wn-ins-grid'; pokaz.forEach(x => box.append(wnKartaWniosku(x))); }
    if (w.lista.length > WN_NA_KARCIE) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'wn-link'; b.id = 'wn-wszystkie';
        b.textContent = wnWszystkie ? `Pokaż ${WN_NA_KARCIE} najważniejszych` : `Pokaż wszystkie (${w.lista.length})`;
        b.addEventListener('click', () => { wnWszystkie = !wnWszystkie; renderWnioskiKarty(); });
        stopka.append(b);
    }
    if (notka) stopka.insertAdjacentHTML('beforeend', notka);
}

// --- Widoki: wybór i zapis ---
function wnPokazZWniosku(x) {
    wnCfg = { ...WN_PUSTY, ...wnKopia(x.pokaz.cfg) };
    wnAktywnyId = null; wnTryb = null; wnTabela = x.pokaz.tabela; wnSciezka = []; wnKartaKat = null;
    wnOpisAdHoc = x.pokaz.opis;
    renderWidok();
    wn$('wn-note').textContent = `Widok z wniosku „${x.tytul}”. Zmień filtry albo zapisz go, żeby do niego wracać.`;
    const sek = wn$('wn-widoki-sekcja');
    if (sek && sek.scrollIntoView) sek.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function wnWybierzWidok(id) {
    const w = wnWidoki().find(v => v.id === id);
    if (!w) return;
    const { cfg, usuniete } = w.wbudowany ? { cfg: wnKopia(w.cfg), usuniete: 0 } : wnOczyscCfg(wnKopia(w.cfg));
    wnAktywnyId = id; wnCfg = cfg; wnTryb = null; wnTabela = 'zestawienie'; wnSciezka = []; wnKartaKat = null;
    renderWidok();
    wn$('wn-note').textContent = usuniete
        ? 'Część filtrów tego widoku wskazywała usunięte konta, kategorie albo kontrahentów — pominięto je. Zapisz zmiany, żeby zniknęły z widoku na stałe.'
        : '';
}

const wnBladApi = async (resp, domyslny) => {
    const body = await resp.json().catch(() => ({}));
    const e = body.error;
    return typeof e === 'string' ? e : e ? Object.values(e).flat().join(' ') : domyslny;
};

async function wnZapiszNowy(nazwa) {
    const blad = wn$('wn-zapis-blad');
    if (savedViews.length >= WN_MAKS_WLASNYCH) { blad.textContent = `Masz już ${WN_MAKS_WLASNYCH} własnych widoków. Usuń któryś, żeby zapisać nowy.`; return; }
    if (!nazwa) { blad.textContent = 'Wpisz nazwę widoku.'; return; }
    if (wnWidoki().some(v => v.nazwa.toLowerCase() === nazwa.toLowerCase())) { blad.textContent = 'Widok o tej nazwie już jest. Wybierz inną nazwę.'; return; }
    const resp = await fetch('/api/views', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: nazwa, config: wnDoZapisu(wnCfg) }) });
    if (!resp.ok) { blad.textContent = await wnBladApi(resp, 'Nie udało się zapisać widoku.'); return; }
    const w = await resp.json();
    savedViews = [...savedViews, w];
    wnAktywnyId = `s${w.id}`; wnCfg = { ...WN_PUSTY, ...wnKopia(w.config), ...(wnCfg.dzien ? { dzien: wnCfg.dzien } : {}) };
    wnTryb = null; wnSciezka = [];
    renderWidok();
    wn$('wn-note').textContent = `Zapisano widok „${w.name}”. Jest na Twoim koncie, więc zobaczysz go też na telefonie.`;
}
async function wnZapiszZmiany(w) {
    const resp = await fetch(`/api/views/${w.sid}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: w.nazwa, config: wnDoZapisu(wnCfg) }) });
    if (!resp.ok) { showToast(await wnBladApi(resp, 'Nie udało się zapisać zmian.'), 'error'); return; }
    const nowy = await resp.json();
    savedViews = savedViews.map(v => (v.id === nowy.id ? nowy : v));
    renderWidok();
    wn$('wn-note').textContent = `Zapisano zmiany w „${nowy.name}”.`;
}
async function wnUsunWidok(w) {
    const resp = await fetch(`/api/views/${w.sid}`, { method: 'DELETE' });
    if (!resp.ok) { showToast(await wnBladApi(resp, 'Nie udało się usunąć widoku.'), 'error'); return; }
    savedViews = savedViews.filter(v => v.id !== w.sid);
    wnWybierzWidok('w1');
    wn$('wn-note').textContent = `Usunięto widok „${w.nazwa}”.`;
}

function renderListyWidokow() {
    const box = wn$('wn-widoki');
    box.innerHTML = '';
    wnWidoki().forEach(w => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = w.wbudowany ? 'wn-chip wn-wbud' : 'wn-chip'; b.dataset.id = w.id;
        if (w.wbudowany) b.title = 'Widok wbudowany';
        b.setAttribute('aria-pressed', String(w.id === wnAktywnyId));
        b.innerHTML = wnEsc(w.nazwa) + (w.id === wnAktywnyId && wnZmieniony() ? ' <span class="wn-zm" title="Zmieniony, niezapisany">•</span>' : '');
        b.addEventListener('click', () => wnWybierzWidok(w.id));
        box.append(b);
    });
    if (!wnAktywnyId) {
        const s = document.createElement('span');
        s.className = 'wn-chip wn-adhoc'; s.setAttribute('aria-pressed', 'true');
        s.textContent = `Niezapisany: ${wnOpisAdHoc}, ${wnEtykietaZakresu(wnZakres(wnCfg))}`;
        box.append(s);
    }
    const i = document.createElement('button');
    i.type = 'button'; i.className = 'wn-info-btn'; i.textContent = 'i';
    i.setAttribute('aria-label', 'Jak działają widoki'); i.setAttribute('aria-expanded', String(wnInfoOtwarte)); i.setAttribute('aria-controls', 'wn-info-widoki');
    i.addEventListener('click', e => { e.stopPropagation(); wnInfoOtwarte = !wnInfoOtwarte; renderListyWidokow(); });
    const wrap = document.createElement('span');
    wrap.className = 'wn-info-wrap';
    wrap.append(i);
    if (wnInfoOtwarte) {
        const pop = document.createElement('span');
        pop.className = 'wn-info-pop'; pop.id = 'wn-info-widoki'; pop.setAttribute('role', 'note');
        pop.textContent = `Widoki z tłem są wbudowane: nie da się ich zmienić ani usunąć. Zmień filtry i zapisz je jako własny widok, żeby do nich wracać. Kliknij słupek wykresu albo nazwę w tabeli, żeby rozbić ją dalej albo zobaczyć operacje. Własnych widoków możesz mieć do ${WN_MAKS_WLASNYCH}, masz ${savedViews.length}.`;
        wrap.append(pop);
    }
    box.append(wrap);
}
const wnZamknijInfo = () => { if (wnInfoOtwarte) { wnInfoOtwarte = false; renderListyWidokow(); } };

function renderAkcji() {
    const box = wn$('wn-akcje'), w = wnAktywny();
    box.innerHTML = '';
    const btn = (txt, fn, cls = 'wn-link') => { const b = document.createElement('button'); b.type = 'button'; b.className = cls; b.textContent = txt; b.addEventListener('click', fn); box.append(b); return b; };
    if (wnTryb === 'zapis') {
        const f = document.createElement('form');
        f.className = 'wn-saveform';
        const domyslna = !w ? wnCap(wnOpisAdHoc) : `${w.nazwa} (kopia)`;
        f.innerHTML = `<label class="wn-small wn-muted" for="wn-nazwa-widoku">Nazwa widoku</label><input type="text" id="wn-nazwa-widoku" maxlength="60" value="${wnEsc(domyslna)}"><button type="submit" class="wn-btn wn-primary">Zapisz</button><button type="button" class="wn-link wn-quiet" id="wn-zapis-anuluj">Anuluj</button><span class="wn-err wn-small" id="wn-zapis-blad" role="alert"></span>`;
        f.addEventListener('submit', e => { e.preventDefault(); wnZapiszNowy(wn$('wn-nazwa-widoku').value.trim()); });
        box.append(f);
        wn$('wn-zapis-anuluj').addEventListener('click', () => { wnTryb = null; renderAkcji(); });
        return;
    }
    if (wnTryb === 'usun') {
        const s = document.createElement('span');
        s.textContent = `Usunąć widok „${w.nazwa}”? `;
        box.append(s);
        btn('Usuń', () => wnUsunWidok(w));
        btn('Zostaw', () => { wnTryb = null; renderAkcji(); }, 'wn-link wn-quiet');
        return;
    }
    if (!w) { btn('Zapisz jako widok', () => { wnTryb = 'zapis'; renderAkcji(); }, 'wn-btn'); return; }
    if (wnZmieniony()) {
        if (!w.wbudowany) btn('Zapisz zmiany', () => wnZapiszZmiany(w), 'wn-btn');
        btn('Zapisz jako nowy widok', () => { wnTryb = 'zapis'; renderAkcji(); }, w.wbudowany ? 'wn-btn' : 'wn-link');
        btn('Cofnij zmiany', () => wnWybierzWidok(w.id), 'wn-link wn-quiet');
        return;
    }
    if (w.wbudowany) return;  // opis widoków wbudowanych jest w dymku przy „i”
    btn('Usuń widok', () => { wnTryb = 'usun'; renderAkcji(); }, 'wn-link wn-quiet');
}

// --- Filtry ---
const WN_NAZWY_FILTROW = { konta: ['Konta', 'wszystkie', 'wybrane', 'wybranych'], kategorie: ['Kategorie', 'wszystkie', 'wybrane', 'wybranych'], kontrahenci: ['Kontrahenci', 'wszyscy', 'wybranych', 'wybranych'] };
function wnListaFiltra(pole) {
    if (pole === 'konta') {
        // Konto zamknięte pojawia się tylko, gdy wskazuje je filtr (np. „cała historia konta”).
        const zamkniete = inactiveAccounts.filter(a => wnCfg.konta.includes(a.id)).map(a => ({ v: a.id, l: `${a.name} (zamknięte)` }));
        return [...accounts.map(a => ({ v: a.id, l: a.name })), ...zamkniete];
    }
    if (pole === 'kategorie') {
        return categories.filter(c => (c.type === 'income' || c.type === 'expense') && !c.is_system_category)
            .sort((a, b) => a.name.localeCompare(b.name, 'pl')).map(c => ({ v: c.id, l: c.name }));
    }
    return [...contractors].sort((a, b) => a.name.localeCompare(b.name, 'pl')).map(c => ({ v: c.id, l: c.name }));
}
function wnPodpnijFiltry() {
    const sekcja = wn$('wn-widoki-sekcja');
    if (!sekcja || sekcja.dataset.wnPodpiete) return;
    sekcja.dataset.wnPodpiete = '1';
    Object.keys(WN_NAZWY_FILTROW).forEach(pole => {
        wn$(`wn-dd-${pole}-lista`).addEventListener('change', e => {
            const id = Number(e.target.value);
            const wyb = new Set(wnCfg[pole]);
            if (e.target.checked) wyb.add(id); else wyb.delete(id);
            wnCfg[pole] = [...wyb].sort((a, b) => a - b);
            renderWidok();
        });
        wn$(`wn-wsz-${pole}`).addEventListener('change', e => {
            // „Wszystkie” czyści wybór; ręcznie odznaczyć się go nie da.
            if (!e.target.checked) { e.target.checked = true; return; }
            wnCfg[pole] = [];
            if (pole === 'konta') wnCfg.ulubione = false;
            renderWidok();
        });
    });
    wn$('wn-tylko-ulubione').addEventListener('change', e => { wnCfg.ulubione = e.target.checked; renderWidok(); });
    wn$('wn-dd-kontrahenci-szukaj').addEventListener('input', e => {
        const q = normalizujTekst(e.target.value);
        wn$('wn-dd-kontrahenci-lista').querySelectorAll('.wn-opt').forEach(o => { o.hidden = !normalizujTekst(o.textContent).includes(q); });
    });
    sekcja.querySelectorAll('details.wn-dd').forEach(d => d.addEventListener('toggle', () => {
        if (d.open) sekcja.querySelectorAll('details.wn-dd').forEach(x => { if (x !== d) x.open = false; });
    }));
    wn$('wn-okres').addEventListener('change', e => {
        const v = e.target.value;
        wnCfg.dzien = null;
        wnCfg.okres = v.startsWith('n') ? { typ: 'n', n: Number(v.slice(1)) } : { typ: v };
        renderWidok();
    });
    ['liczy', 'pokaz', 'sald'].forEach(pole => wn$(`wn-${pole}`).addEventListener('click', e => {
        const b = e.target.closest('button');
        if (!b || b.disabled) return;
        wnCfg[pole] = b.dataset.v;
        renderWidok();
    }));
    wn$('wn-tab-zest').addEventListener('click', () => { wnTabela = 'zestawienie'; renderWidok(); });
    wn$('wn-tab-ops').addEventListener('click', () => { wnTabela = 'operacje'; renderWidok(); });
    wn$('wn-mies-prev').addEventListener('click', () => wnZmienMiesiac(-1));
    wn$('wn-mies-next').addEventListener('click', () => wnZmienMiesiac(1));
}
function wnOdswiezFiltry() {
    const o = wnCfg.okres;
    wn$('wn-okres').value = o.typ === 'n' ? `n${o.n}` : o.typ;
    Object.keys(WN_NAZWY_FILTROW).forEach(pole => {
        const lista = wn$(`wn-dd-${pole}-lista`), opcje = wnListaFiltra(pole), wyb = new Set(wnCfg[pole]);
        lista.innerHTML = opcje.map(({ v, l }) => `<label class="wn-opt"><input type="checkbox" value="${v}"${wyb.has(v) ? ' checked' : ''}> ${wnEsc(l)}</label>`).join('')
            || '<p class="wn-hint">Brak pozycji.</p>';
        const [nazwa, wsz, kilka, wiele] = WN_NAZWY_FILTROW[pole], n = wnCfg[pole].length;
        const pierwsza = n === 1 ? (opcje.find(x => x.v === wnCfg[pole][0]) || {}).l : '';
        const etyk = n === 0 ? wsz : n === 1 ? (pierwsza || '1 wybrany') : `${n} ${odmiana(n, [kilka, kilka, wiele])}`;
        const ul = pole === 'konta' && wnCfg.ulubione;
        const sum = wn$(`wn-dd-${pole}-sum`);
        sum.textContent = `${nazwa}: ${ul ? (n ? `ulubione, ${etyk}` : 'ulubione') : etyk}`;
        sum.classList.toggle('wn-set', n > 0 || ul);
        wn$(`wn-wsz-${pole}`).checked = !n && !ul;
    });
    const q = wn$('wn-dd-kontrahenci-szukaj').value;
    if (q) wn$('wn-dd-kontrahenci-szukaj').dispatchEvent(new Event('input'));
    ['liczy', 'pokaz'].forEach(pole => wn$(`wn-${pole}`).querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === wnCfg[pole]))));
    const ileUl = accounts.filter(a => a.is_favorite).length;
    wn$('wn-tylko-ulubione').checked = !!wnCfg.ulubione;
    // Bez ulubionych filtr dałby pusty widok, a gwiazdki są w tabeli sald.
    wn$('wn-tylko-ulubione').disabled = !ileUl && !wnCfg.ulubione;
    wn$('wn-ile-ulubionych').textContent = ileUl ? `(${ileUl} z ${WN_MAKS_ULUBIONYCH})` : '(oznacz konta gwiazdką w widoku sald)';
    wn$('wn-tab-zest').setAttribute('aria-pressed', String(wnTabela === 'zestawienie'));
    wn$('wn-tab-ops').setAttribute('aria-pressed', String(wnTabela === 'operacje'));
}

// --- Kafelki, wykres, tabela ---
const wnKafel = ([l, v, p]) => `<div class="wn-kpi"><p class="wn-eyebrow">${wnEsc(l)}</p><p class="wn-v">${wnEsc(v)}</p><p class="wn-p">${wnEsc(p)}</p></div>`;
// Kafelki zależą od tego, co widok liczy: przy samych wydatkach „Przychody 0 zł” byłyby szumem.
function wnKafelki(c, ops, [od, doM]) {
    const dl = doM - od + 1;
    const stat = o => { const p = o.filter(t => wnLiczone(c, t)); return { ...wnSumy(p), maks: p.reduce((m, t) => Math.max(m, Math.abs(t.kwota)), 0) }; };
    const a = stat(ops), b = od - dl >= 0 ? stat(wnFiltruj(c, [od - dl, doM - dl])) : null;
    const por = (f, fmt = wnZl) => (b ? `poprzednio: ${fmt(f(b))}` : 'poprzednio: brak danych');
    if (c.liczy === 'oba') {
        return [['Przychody', wnZl(a.inc), por(s => s.inc)], ['Wydatki', wnZl(a.exp), por(s => s.exp)],
            ['Bilans', wnZl(a.inc - a.exp), por(s => s.inc - s.exp)], ['Operacje', String(a.n), por(s => s.n, String)]];
    }
    const wyd = c.liczy === 'wydatki', suma = s => (wyd ? s.exp : s.inc);
    return [[wyd ? 'Wydatki' : 'Przychody', wnZl(suma(a)), por(suma)], ['Średnio na miesiąc', wnZl(suma(a) / dl), por(s => suma(s) / dl)],
        ['Operacje', String(a.n), por(s => s.n, String)], [wyd ? 'Największy wydatek' : 'Największy wpływ', wnZl(a.maks), por(s => s.maks)]];
}

function wnDaneWykresu(c, ops, [od, doM]) {
    const policz = ops.filter(o => wnLiczone(c, o));
    if (c.pokaz === 'czas') {
        let etykiety, klucz;
        if (od === doM) {
            const [y, m] = wnYmZ(od).split('-').map(Number);
            etykiety = Array.from({ length: new Date(y, m, 0).getDate() }, (_, k) => String(k + 1));
            klucz = o => Number(o.data.slice(8)) - 1;
        } else {
            etykiety = [];
            for (let j = od; j <= doM; j++) etykiety.push(j === od && wnNr(j) !== 0 ? `${WN_M_KR[wnNr(j)]} ${wnRok(j).slice(2)}` : wnKr(j));
            klucz = o => o.j - od;
        }
        const seria = filtr => { const dd = etykiety.map(() => 0); policz.filter(filtr).forEach(o => { dd[klucz(o)] += Math.abs(o.kwota); }); return dd.map(wnGrosz); };
        const zbiory = [];
        // Przy 2–6 wybranych kategoriach wykres w czasie piętrzy je osobno.
        const podzial = c.liczy !== 'oba' && c.kategorie.length >= 2 && c.kategorie.length <= 6;
        if (podzial) {
            c.kategorie.forEach((id, n) => zbiory.push({ label: (wnKategoria(id) || {}).name || '?', katId: id, data: seria(o => o.katId === id), backgroundColor: WN_KOLORY[n % WN_KOLORY.length], stack: 's' }));
        } else {
            if (c.liczy !== 'wydatki') zbiory.push({ label: 'Przychody', strona: 'p', data: seria(o => o.kwota > 0), backgroundColor: PALETA.ochra });
            if (c.liczy !== 'przychody') zbiory.push({ label: 'Wydatki', strona: 'w', data: seria(o => o.kwota < 0), backgroundColor: PALETA.stal });
        }
        return { poziomy: false, stos: podzial, etykiety, zbiory };
    }
    const pole = c.pokaz === 'kategorie' ? 'kategoria' : 'kontrahent';
    const wiersze = wnZestawienie(policz, pole).slice(0, pole === 'kategoria' ? 12 : 10);
    return {
        poziomy: true, pole, wiersze, etykiety: wiersze.map(w => w.nazwa),
        zbiory: [{ label: 'Kwota', data: wiersze.map(w => w.kwota), backgroundColor: wiersze.map(w => (w.przychod ? PALETA.ochra : PALETA.stal)) }],
    };
}

const wnOsTicks = { callback: v => wnTys(String(v)) };
function wnRysujWykres(c, ops, z) {
    const d = wnDaneWykresu(c, ops, z), box = wn$('wn-chartbox');
    box.style.height = d.poziomy ? `${Math.max(160, d.etykiety.length * 30 + 40)}px` : '280px';
    if (wnWykres) { wnWykres.destroy(); wnWykres = null; }
    if (typeof Chart === 'undefined') return d;
    const os = d.poziomy ? 'x' : 'y';
    wnWykres = new Chart(wn$('wn-wykres'), {
        type: 'bar',
        data: { labels: d.etykiety, datasets: d.zbiory.map(s => ({ ...s, borderRadius: 2, maxBarThickness: 36 })) },
        options: {
            responsive: true, maintainAspectRatio: false, indexAxis: d.poziomy ? 'y' : 'x', animation: false,
            onClick: (e, els) => (els.length ? wnKlikWykresu(e, d, z, els[0]) : wnZamknijMenu()),
            onHover: (e, els) => { e.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
            plugins: { legend: { display: !d.poziomy, position: 'bottom', labels: { boxWidth: 12 } }, tooltip: { callbacks: { label: x => `${x.dataset.label}: ${wnZl2(x.parsed[os])}` } } },
            scales: {
                [os]: { stacked: !!d.stos, beginAtZero: true, ticks: wnOsTicks },
                [d.poziomy ? 'y' : 'x']: { stacked: !!d.stos, grid: { display: false } },
            },
        },
    });
    return d;
}

function wnPrzyciskDrill(typ, el, nazwa, kwota, strona = '') {
    return `<button type="button" class="wn-drill" aria-haspopup="menu" data-typ="${typ}" data-v="${el}" data-n="${wnEsc(nazwa)}" data-s="${strona}" data-kw="${wnEsc(kwota)}">${wnEsc(nazwa)}</button>`;
}

function wnTabelaOperacji(ops, maks = WN_MAKS_OPERACJI, zKontem = true) {
    const rows = [...ops].sort((a, b) => (b.data < a.data ? -1 : b.data > a.data ? 1 : b.id - a.id));
    const kw = o => `${o.kwota > 0 ? '+' : '−'}${wnZl2(Math.abs(o.kwota))}`;
    const html = `<table><thead><tr><th>Data</th><th>Opis</th>${zKontem ? '<th>Kategoria</th><th>Konto</th>' : ''}<th class="wn-num">Kwota</th></tr></thead><tbody>${rows.slice(0, maks).map(o => `<tr><td class="wn-date">${wnDataKr(o.data)}</td><td>${wnEsc(o.tytul)}<div class="wn-sub">${wnEsc(o.nazwa)}${zKontem ? '' : ` · ${wnEsc(wnKontoNazwa(o.konto))}`}</div></td>${zKontem ? `<td>${wnEsc(o.kat)}</td><td>${wnEsc(wnKontoNazwa(o.konto))}</td>` : ''}<td class="wn-num ${o.kwota > 0 ? 'wn-pos' : ''}">${kw(o)}</td></tr>`).join('')}</tbody></table>`;
    return { html, n: rows.length };
}

function wnRysujTabele(c, ops, [od, doM]) {
    const policz = ops.filter(o => wnLiczone(c, o)), box = wn$('wn-tabela');
    wn$('wn-tab-ops').textContent = `Operacje (${policz.length})`;
    if (wnTabela === 'operacje') {
        const { html, n } = wnTabelaOperacji(policz);
        box.innerHTML = html + (n > WN_MAKS_OPERACJI ? `<p class="wn-small wn-muted" style="margin-top:8px">Pokazano ${WN_MAKS_OPERACJI} najnowszych z ${n} operacji.</p>` : '')
            + (!n ? '<p class="wn-pusto">Brak operacji w tym widoku.</p>' : '');
        return;
    }
    const grupuj = c.pokaz === 'czas' ? (od === doM ? 'kategoria' : 'miesiac') : c.pokaz === 'kategorie' ? 'kategoria' : 'kontrahent';
    if (grupuj === 'miesiac') {
        const kol = [c.liczy !== 'wydatki' && 'Przychody', c.liczy !== 'przychody' && 'Wydatki', c.liczy === 'oba' && 'Bilans'].filter(Boolean);
        let html = `<table><thead><tr><th>Miesiąc</th>${kol.map(k => `<th class="wn-num">${k}</th>`).join('')}</tr></thead><tbody>`;
        for (let j = doM; j >= od; j--) {
            const s = wnSumy(policz.filter(o => o.j === j));
            const wart = { Przychody: s.inc, Wydatki: s.exp, Bilans: s.inc - s.exp };
            html += `<tr><td>${wnPrzyciskDrill('miesiac', j, wnCap(wnNazwa(j)), wnZl2(c.liczy === 'przychody' ? s.inc : s.exp))}</td>${kol.map(k => `<td class="wn-num">${wnZl2(wart[k])}</td>`).join('')}</tr>`;
        }
        box.innerHTML = html + '</tbody></table>';
        return;
    }
    const pole = grupuj;
    const grupy = [c.liczy !== 'przychody' && ['Wydatki', o => o.kwota < 0, 'w'], c.liczy !== 'wydatki' && ['Przychody', o => o.kwota > 0, 'p']].filter(Boolean);
    let html = `<table><thead><tr><th>${pole === 'kategoria' ? 'Kategoria' : 'Kontrahent'}</th><th class="wn-num">Kwota</th><th class="wn-num">Udział</th><th class="wn-num">Operacje</th></tr></thead><tbody>`;
    grupy.forEach(([nazwa, f, strona]) => {
        const czesc = policz.filter(f);
        if (!czesc.length) return;
        const suma = wnGrosz(czesc.reduce((s, o) => s + Math.abs(o.kwota), 0));
        html += `<tr class="wn-grp"><td colspan="4">${nazwa}</td></tr>`;
        wnZestawienie(czesc, pole).forEach(e => {
            const udz = suma ? e.kwota / suma * 100 : 0;
            const etykieta = e.id ? wnPrzyciskDrill(pole, e.id, e.nazwa, wnZl2(e.kwota), strona) : wnEsc(e.nazwa);
            html += `<tr><td>${etykieta}</td><td class="wn-num">${wnZl2(e.kwota)}</td><td class="wn-num"><span class="wn-bar" style="width:${Math.max(2, Math.round(udz * 0.6))}px"></span>${udz.toFixed(1).replace('.', ',')}%</td><td class="wn-num">${e.n}</td></tr>`;
        });
        html += `<tr class="wn-sum"><td>Razem</td><td class="wn-num">${wnZl2(suma)}</td><td class="wn-num">100%</td><td class="wn-num">${czesc.length}</td></tr>`;
    });
    box.innerHTML = html + '</tbody></table>' + (!policz.length ? '<p class="wn-pusto">Brak operacji w tym widoku.</p>' : '');
}

// --- Salda kont ---
const wnNaKoniec = j => (j === wnD().biezacy ? 'na dziś' : `na koniec ${WN_M_DOP[wnNr(j)]}`);
function wnPrzelaczUlubione(a) {
    const nowe = !a.is_favorite;
    if (nowe && accounts.filter(x => x.is_favorite).length >= WN_MAKS_ULUBIONYCH) {
        wn$('wn-note').textContent = `Ulubionych może być najwyżej ${WN_MAKS_ULUBIONYCH}, tyle linii mieści się czytelnie na wykresie.`;
        return;
    }
    fetch(`/api/accounts/${a.id}/favorite`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_favorite: nowe }) })
        .then(async resp => {
            if (!resp.ok) { wn$('wn-note').textContent = await wnBladApi(resp, 'Nie udało się zapisać ulubionego konta.'); return; }
            accounts = accounts.map(x => (x.id === a.id ? { ...x, is_favorite: nowe } : x));
            renderWidok();
            wn$('wn-note').textContent = `${a.name}: ${nowe ? 'dodane do ulubionych' : 'usunięte z ulubionych'}.`;
        })
        .catch(() => { wn$('wn-note').textContent = 'Nie udało się zapisać ulubionego konta.'; });
}

function wnRysujSalda(c, [od, doM]) {
    const konta = wnKontaWZakresie(c), tryb = wnTrybSald(c);
    const bezKursu = konta.filter(a => wnSaldoPLN(a, doM) === null);
    const koniec = wnSumaSald(konta, doM), poczatek = wnSumaSald(konta, od - 1);
    const ujemne = konta.filter(a => (wnSaldoPLN(a, doM) ?? 0) < 0).length;
    wn$('wn-kpi').innerHTML = [
        ['Suma sald', wnZl(koniec), wnNaKoniec(doM)],
        ['Zmiana w okresie', (koniec - poczatek > 0 ? '+' : '') + wnZl(koniec - poczatek), od > 0 ? `od końca ${WN_M_DOP[wnNr(od - 1)]}` : 'od początku danych'],
        ['Konta', String(konta.length), 'w zakresie filtra'],
        ['Na minusie', String(ujemne), ujemne ? odmiana(ujemne, ['konto', 'konta', 'kont']) + ' z saldem ujemnym' : 'wszystkie na plusie'],
    ].map(wnKafel).join('') + (bezKursu.length ? `<p class="wn-notka">Poza sumą: ${wnEsc(bezKursu.map(a => a.name).join(', '))} — brak kursu NBP.</p>` : '');

    const NAZWY = { konta: 'Wg kont', typy: 'Wg typu kont', razem: 'Razem' };
    wn$('wn-sald').innerHTML = wnOpcjeSald(c).map(v => `<button type="button" data-v="${v}" aria-pressed="${v === tryb}">${NAZWY[v]}</button>`).join('');

    const miesiace = [];
    for (let j = od; j <= doM; j++) miesiace.push(j);
    const etykiety = miesiace.map(j => (j === od && wnNr(j) !== 0 ? `${WN_M_KR[wnNr(j)]} ${wnRok(j).slice(2)}` : wnKr(j)));
    const linia = (label, lista, kolor) => ({ label, data: miesiace.map(j => wnSumaSald(lista, j)), borderColor: kolor, backgroundColor: kolor });
    const typKonta = a => a.account_type || 'Bez typu';
    let zbiory;
    if (tryb === 'razem') zbiory = [linia('Suma sald', konta, PALETA.ochra)];
    else if (tryb === 'typy') zbiory = WN_TYPY_KONT.map(t => [t, konta.filter(a => typKonta(a) === t.klucz)]).filter(([, l]) => l.length).map(([t, l]) => linia(t.etykieta, l, t.kolor));
    else zbiory = konta.map((a, n) => linia(a.name, [a], WN_KOLORY[n % WN_KOLORY.length]));
    wn$('wn-chartbox').style.height = '280px';
    if (wnWykres) { wnWykres.destroy(); wnWykres = null; }
    if (typeof Chart !== 'undefined') {
        wnWykres = new Chart(wn$('wn-wykres'), {
            type: od === doM ? 'bar' : 'line',
            data: { labels: etykiety, datasets: zbiory.map(z => ({ ...z, tension: 0.25, pointRadius: 3, maxBarThickness: 48 })) },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } }, tooltip: { callbacks: { label: x => `${x.dataset.label}: ${wnZl2(x.parsed.y)}` } } },
                scales: { y: { ticks: wnOsTicks }, x: { grid: { display: false } } },
            },
        });
    }

    // Tabela: konta w wierszach (ulubione, potem wg typu), saldo na koniec i zmiana zaraz po
    // nazwie (na telefonie widać je bez przewijania), dalej historia od najnowszego miesiąca.
    const kol = [od - 1, ...miesiace];
    const pusteKonto = a => kol.every(j => wnSaldo(a.id, j) === 0);
    const puste = konta.filter(pusteKonto), widoczne = wnPokazPuste ? konta : konta.filter(a => !pusteKonto(a));
    const grupy = [];
    const ul = widoczne.filter(a => a.is_favorite);
    if (ul.length) grupy.push(['Ulubione', ul]);
    WN_TYPY_KONT.forEach(t => { const l = widoczne.filter(a => !a.is_favorite && typKonta(a) === t.klucz); if (l.length) grupy.push([t.etykieta, l]); });
    const naglowek = j => (j < od ? (j < 0 ? 'na start' : `koniec ${WN_M_KR[wnNr(j)]} ${wnRok(j).slice(2)}`) : j === wnD().biezacy ? `${WN_M_KR[wnNr(j)]} (dziś)` : wnKr(j));
    const historia = kol.filter(j => j !== doM).reverse();
    const zmiana = v => (v > 0 ? '+' : '') + wnZl2(v);
    const komorkiSum = f => `<td class="wn-num wn-teraz">${wnZl2(f(doM))}</td><td class="wn-num ${f(doM) - f(od - 1) > 0 ? 'wn-pos' : ''}">${zmiana(wnGrosz(f(doM) - f(od - 1)))}</td>` + historia.map(j => `<td class="wn-num">${wnZl2(f(j))}</td>`).join('');
    // Konto walutowe: saldo w walucie konta, pod nim wartość w PLN.
    const komorkaKonta = (a, j, cls = '') => {
        if (!a.currency || a.currency === 'PLN') return `<td class="wn-num ${cls}">${wnZl2(wnSaldo(a.id, j))}</td>`;
        const pln = wnSaldoPLN(a, j);
        return `<td class="wn-num ${cls}">${formatKwota(wnSaldo(a.id, j))} ${wnEsc(a.currency)}<div class="wn-sub">${pln === null ? 'brak kursu' : '≈ ' + wnZl2(pln)}</div></td>`;
    };
    let html = `<table class="wn-salda"><thead><tr><th>Konto</th><th class="wn-num wn-teraz">${wnEsc(wnCap(wnNaKoniec(doM)))}</th><th class="wn-num">Zmiana (PLN)</th>${historia.map(j => `<th class="wn-num">${wnEsc(naglowek(j))}</th>`).join('')}</tr></thead><tbody>`;
    grupy.forEach(([nazwa, lista]) => {
        html += `<tr class="wn-grp"><td colspan="${kol.length + 2}">${wnEsc(nazwa)}</td></tr>`;
        lista.forEach(a => {
            const zm = (wnSaldoPLN(a, doM) ?? 0) - (wnSaldoPLN(a, od - 1) ?? 0);
            html += `<tr><td><button type="button" class="wn-gw" data-k="${a.id}" aria-pressed="${!!a.is_favorite}" aria-label="${a.is_favorite ? 'Usuń z ulubionych' : 'Dodaj do ulubionych'}: ${wnEsc(a.name)}">${a.is_favorite ? '★' : '☆'}</button>${wnEsc(a.name)}</td>`
                + komorkaKonta(a, doM, 'wn-teraz') + `<td class="wn-num ${zm > 0 ? 'wn-pos' : ''}">${zmiana(wnGrosz(zm))}</td>` + historia.map(j => komorkaKonta(a, j)).join('') + '</tr>';
        });
        if (lista.length > 1 && grupy.length > 1) html += `<tr class="wn-podsuma"><td>Razem: ${wnEsc(nazwa.toLowerCase())}</td>${komorkiSum(j => wnSumaSald(lista, j))}</tr>`;
    });
    html += `<tr class="wn-sum"><td>Razem (PLN)</td>${komorkiSum(j => wnSumaSald(konta, j))}</tr></tbody></table>`;
    const tabela = wn$('wn-tabela');
    tabela.innerHTML = html
        + (puste.length ? `<p class="wn-small" style="margin-top:8px"><button type="button" class="wn-link" id="wn-puste">${wnPokazPuste ? 'Ukryj konta z zerowym saldem' : `Pokaż konta z zerowym saldem (${puste.length})`}</button></p>` : '')
        + `<p class="wn-small wn-muted" style="margin-top:8px">Gwiazdka oznacza konto jako ulubione: trafia na górę tabeli i do filtra „Tylko ulubione” w liście kont. Saldo liczone ze wszystkich operacji konta, także przelewów między Twoimi kontami. Tylko konta aktywne${inactiveAccounts.length ? ` (pominięte zamknięte: ${inactiveAccounts.length})` : ''}. Konto w obcej walucie przeliczane po kursie NBP z końca miesiąca.</p>`;
    tabela.querySelectorAll('.wn-gw').forEach(b => b.addEventListener('click', () => wnPrzelaczUlubione(accounts.find(a => a.id === Number(b.dataset.k)))));
    if (wn$('wn-puste')) wn$('wn-puste').addEventListener('click', () => { wnPokazPuste = !wnPokazPuste; renderWidok(); });
}

// --- Rozbijanie: menu po kliknięciu, ścieżka, karta kategorii ---
const wnMigawka = () => ({ cfg: wnKopia(wnCfg), tabela: wnTabela, ym: wnYm, aktywnyId: wnAktywnyId, opisAdHoc: wnOpisAdHoc, karta: wnKartaKat });
const wnEtykietaBiezaca = () => (wnKartaKat ? `Karta: ${(wnKategoria(wnKartaKat) || {}).name || ''}` : wnAktywny() ? wnAktywny().nazwa : wnOpisAdHoc);
const wnNazwaDnia = dz => `${dz} ${WN_M_DOP[wnNr(wnI())]}`;
function wnOpisEl(el) {
    if (el.typ === 'miesiac') return wnCap(wnNazwa(el.v)) + (el.katNazwa ? `, ${el.katNazwa}` : '');
    if (el.typ === 'dzien') return wnNazwaDnia(el.v) + (el.katNazwa ? `, ${el.katNazwa}` : '');
    return el.nazwa;
}
function wnPrzywroc(k) {
    const st = wnSciezka[k].stan;
    wnSciezka = wnSciezka.slice(0, k);
    wnCfg = wnKopia(st.cfg); wnTabela = st.tabela; wnAktywnyId = st.aktywnyId; wnOpisAdHoc = st.opisAdHoc; wnKartaKat = st.karta; wnTryb = null;
    if (wnYm !== st.ym) { wnYm = st.ym; renderWnioskiKarty(); }
    wn$('wn-note').textContent = '';
    renderWidok();
}
// Każdy krok zapamiętuje stan sprzed siebie, więc ścieżka cofa dokładnie tam, skąd przyszliśmy.
function wnDrill(etykieta, zmiana) {
    wnSciezka.push({ etykieta: wnEtykietaBiezaca(), stan: wnMigawka() });
    // Z karty rozbijamy kategorię z ostatnich 12 miesięcy, niezależnie od filtrów sprzed karty.
    if (wnKartaKat && !zmiana.karta) {
        const kat = wnKategoria(wnKartaKat);
        wnCfg = { ...WN_PUSTY, kategorie: [wnKartaKat], okres: { typ: 'n', n: 12 }, liczy: kat && kat.type === 'income' ? 'przychody' : 'wydatki', pokaz: 'czas' };
    }
    if (zmiana.f) zmiana.f();
    wnKartaKat = zmiana.karta || null;
    if (zmiana.ym && zmiana.ym !== wnYm) { wnYm = zmiana.ym; wnCfg.dzien = null; renderWnioskiKarty(); }
    wnAktywnyId = null; wnTryb = null; wnOpisAdHoc = etykieta;
    wn$('wn-note').textContent = '';
    wnZamknijMenu(false);
    renderWidok();
}
// Lista akcji menu dla klikniętego elementu: [etykieta, opis kroku, zmiana stanu, dodatki].
function wnAkcjeDla(el, z) {
    const strona = el.strona ? { liczy: el.strona === 'p' ? 'przychody' : 'wydatki' } : {};
    const katSeg = () => { if (el.katId) wnCfg.kategorie = [el.katId]; Object.assign(wnCfg, strona); };
    // „Wyklucz” = zostaw wszystko, co widać, poza tym elementem.
    const bez = (pole, klucz) => [...new Set(wnFiltruj({ ...wnCfg, [pole]: [] }, z).filter(o => wnLiczone(wnCfg, o)).map(o => o[klucz]))]
        .filter(x => x !== null && x !== el.v).sort((a, b) => a - b);
    const A = [];
    if (el.typ === 'kategoria') {
        const kat = wnKategoria(el.v);
        A.push(['Pokaż operacje', el.nazwa, () => { wnCfg.kategorie = [el.v]; Object.assign(wnCfg, strona); wnTabela = 'operacje'; }]);
        A.push(['Rozbij na kontrahentów', `${el.nazwa} wg kontrahentów`, () => { wnCfg.kategorie = [el.v]; Object.assign(wnCfg, strona); wnCfg.pokaz = 'kontrahenci'; wnTabela = 'zestawienie'; }]);
        A.push(['Rozbij w czasie (6 mies.)', `${el.nazwa} w czasie`, () => { wnCfg.kategorie = [el.v]; Object.assign(wnCfg, strona); wnCfg.pokaz = 'czas'; wnCfg.okres = { typ: 'n', n: 6 }; wnCfg.dzien = null; wnTabela = 'zestawienie'; }]);
        A.push(['Wyklucz z widoku', `bez: ${el.nazwa}`, () => { wnCfg.kategorie = bez('kategorie', 'katId'); }]);
        if (kat) A.push(['Karta kategorii', `Karta: ${el.nazwa}`, null, { karta: el.v }]);
    } else if (el.typ === 'kontrahent') {
        A.push(['Pokaż operacje', el.nazwa, () => { wnCfg.kontrahenci = [el.v]; Object.assign(wnCfg, strona); wnTabela = 'operacje'; }]);
        A.push(['Rozbij w czasie (6 mies.)', `${el.nazwa} w czasie`, () => { wnCfg.kontrahenci = [el.v]; Object.assign(wnCfg, strona); wnCfg.pokaz = 'czas'; wnCfg.okres = { typ: 'n', n: 6 }; wnCfg.dzien = null; wnTabela = 'zestawienie'; }]);
        A.push(['Rozbij na kategorie', `${el.nazwa} wg kategorii`, () => { wnCfg.kontrahenci = [el.v]; Object.assign(wnCfg, strona); wnCfg.pokaz = 'kategorie'; wnTabela = 'zestawienie'; }]);
        A.push(['Wyklucz z widoku', `bez: ${el.nazwa}`, () => { wnCfg.kontrahenci = bez('kontrahenci', 'kontrId'); }]);
    } else if (el.typ === 'miesiac') {
        const mies = { typ: 'miesiac' }, et = wnOpisEl(el), ym = wnYmZ(el.v);
        A.push(['Pokaż operacje', et, () => { katSeg(); wnCfg.okres = mies; wnTabela = 'operacje'; }, { ym }]);
        A.push(['Rozbij na dni', `${et} dzień po dniu`, () => { katSeg(); wnCfg.okres = mies; wnCfg.pokaz = 'czas'; wnTabela = 'zestawienie'; }, { ym }]);
        A.push(['Rozbij na kategorie', `${et} wg kategorii`, () => { katSeg(); wnCfg.okres = mies; wnCfg.pokaz = 'kategorie'; wnTabela = 'zestawienie'; }, { ym }]);
        A.push(['Rozbij na kontrahentów', `${et} wg kontrahentów`, () => { katSeg(); wnCfg.okres = mies; wnCfg.pokaz = 'kontrahenci'; wnTabela = 'zestawienie'; }, { ym }]);
        if (el.katId) A.push(['Karta kategorii', `Karta: ${el.katNazwa}`, null, { karta: el.katId, ym }]);
    } else if (el.typ === 'dzien') {
        const et = wnOpisEl(el);
        A.push(['Pokaż operacje z tego dnia', et, () => { katSeg(); wnCfg.dzien = el.v; wnTabela = 'operacje'; }]);
        A.push(['Rozbij na kategorie', `${et} wg kategorii`, () => { katSeg(); wnCfg.dzien = el.v; wnCfg.pokaz = 'kategorie'; wnTabela = 'zestawienie'; }]);
        if (el.katId) A.push(['Karta kategorii', `Karta: ${el.katNazwa}`, null, { karta: el.katId }]);
    }
    return A;
}
function wnOtworzMenu(punkt, el, z) {
    const m = wn$('wn-drill-menu'), akcje = wnAkcjeDla(el, z);
    wnMenuZrodlo = punkt.zrodlo || null;
    m.innerHTML = `<p class="wn-dm-tyt">${wnEsc(el.naglowek)}</p>` + akcje.map(([l, , , extra], k) => `<button type="button" role="menuitem" data-i="${k}"${extra && extra.karta ? ' class="wn-karta-btn"' : ''}>${wnEsc(l)}</button>`).join('');
    m.querySelectorAll('button').forEach(b => b.addEventListener('click', e => {
        e.stopPropagation();
        const [, et, f, extra] = akcje[Number(b.dataset.i)];
        wnDrill(et, { f, ...(extra || {}) });
    }));
    m.hidden = false;
    const telefon = window.matchMedia && window.matchMedia('(max-width: 640px)').matches;
    if (telefon) { m.style.left = ''; m.style.top = ''; } else {
        const r = m.getBoundingClientRect();
        m.style.left = `${Math.max(8, Math.min(punkt.x, innerWidth - r.width - 8))}px`;
        m.style.top = `${Math.max(8, Math.min(punkt.y, innerHeight - r.height - 8))}px`;
    }
    const pierwszy = m.querySelector('button');
    if (pierwszy) pierwszy.focus();
}
function wnZamknijMenu(oddajFokus = true) {
    const m = wn$('wn-drill-menu');
    if (!m || m.hidden) return;
    m.hidden = true;
    if (oddajFokus && wnMenuZrodlo && document.contains(wnMenuZrodlo)) wnMenuZrodlo.focus();
}
function wnKlikWykresu(e, d, [od, doM], { datasetIndex: ds, index: i }) {
    const kw = d.zbiory[ds].data[i], zbior = d.zbiory[ds];
    let el;
    if (d.poziomy) {
        const w = d.wiersze[i];
        if (!w.id) return;  // kontrahent spoza słownika — filtr zna tylko ID
        el = { typ: d.pole, v: w.id, nazwa: w.nazwa, strona: w.przychod ? 'p' : 'w' };
    } else {
        const katId = zbior.katId || null;
        const katNazwa = katId ? zbior.label : null;
        const strona = zbior.strona || null;
        el = od === doM ? { typ: 'dzien', v: i + 1, strona, katId, katNazwa } : { typ: 'miesiac', v: od + i, strona, katId, katNazwa };
    }
    el.naglowek = `${wnOpisEl(el)} · ${wnZl2(kw)}`;
    // Dymek z kwotą zasłaniałby menu, a menu i tak ją pokazuje w nagłówku.
    if (wnWykres && wnWykres.tooltip) { wnWykres.tooltip.setActiveElements([], { x: 0, y: 0 }); wnWykres.update('none'); }
    wnOtworzMenu({ x: e.native.clientX + 4, y: e.native.clientY + 4 }, el, [od, doM]);
}
function wnPodepnijDrill(box) {
    box.querySelectorAll('button.wn-drill').forEach(b => b.addEventListener('click', e => {
        e.stopPropagation();
        const r = b.getBoundingClientRect(), typ = b.dataset.typ;
        const el = { typ, v: Number(b.dataset.v), nazwa: b.dataset.n, strona: b.dataset.s || null };
        el.naglowek = `${wnOpisEl(el)} · ${b.dataset.kw}`;
        wnOtworzMenu({ x: r.left, y: r.bottom + 4, zrodlo: b }, el, wnZakres(wnCfg));
    }));
}
function renderSciezka() {
    const n = wn$('wn-sciezka');
    n.hidden = !wnSciezka.length;
    if (!wnSciezka.length) { n.innerHTML = ''; return; }
    n.innerHTML = wnSciezka.map((k, i) => `<button type="button" class="wn-link" data-i="${i}">${wnEsc(k.etykieta)}</button><span aria-hidden="true">›</span>`).join('') + `<b aria-current="step">${wnEsc(wnEtykietaBiezaca())}</b>`;
    n.querySelectorAll('[data-i]').forEach(b => b.addEventListener('click', () => wnPrzywroc(Number(b.dataset.i))));
}

// Karta: wszystko o jednej kategorii w jednym miejscu, zawsze ze wszystkich kont, 12 miesięcy do wybranego.
function wnDaneKarty(katId, i = wnI()) {
    const d = wnD(), kat = wnKategoria(katId), przych = kat && kat.type === 'income';
    const opsK = d.ops.filter(o => o.katId === katId);
    const ops12 = opsK.filter(o => o.j <= i && o.j > i - 12);
    const sumaM = j => wnGrosz(opsK.filter(o => o.j === j).reduce((a, o) => a + Math.abs(o.kwota), 0));
    const mies = [];
    for (let j = Math.max(0, i - 11); j <= i; j++) mies.push(j);
    const okno = wnOkno(d, i);
    const rok = wnGrosz(mies.reduce((a, j) => a + sumaM(j), 0));
    const calosc = mies.reduce((a, j) => a + (przych ? d.agg[j].inc : d.agg[j].exp), 0);
    return { kat, przych, ops12, mies, okno, teraz: sumaM(i), typowo: wnMediana(okno.map(sumaM)), rok, calosc, sumaM };
}
function renderKarta(katId) {
    const i = wnI(), d = wnD(), k = wnDaneKarty(katId, i), nazwa = k.kat ? k.kat.name : '';
    const kontr = wnZestawienie(k.ops12, 'kontrahent').slice(0, 8);
    const ktoW = new Set(k.ops12.map(o => o.nazwa));
    const wn = wnWnioskiZa(d, wnYmZ(i)).lista.filter(x => (x.temat.typ === 'kategoria' && x.temat.nazwa === nazwa)
        || (x.pokaz.cfg.kategorie || []).includes(katId) || (x.rodzaj === 'Stała opłata' && (x.kategoria === nazwa || ktoW.has(x.tytul))));
    const kafle = [
        [wnCap(WN_M_MIAN[wnNr(i)]) + (i === d.biezacy ? ' (trwa)' : ''), wnZl(k.teraz), k.okno.length >= 3 ? `typowo ${wnZl(k.typowo)} (mediana z ${k.okno.length} mies.)` : 'za krótka historia na porównanie'],
        ['Ostatnie 12 miesięcy', wnZl(k.rok), k.calosc ? `${Math.round(k.rok / k.calosc * 100)}% wszystkich ${k.przych ? 'przychodów' : 'wydatków'}` : ''],
        ['Średnio na miesiąc', wnZl(k.rok / k.mies.length), `${k.ops12.length} ${odmiana(k.ops12.length, ['operacja', 'operacje', 'operacji'])} w 12 mies.`],
    ];
    const { html: ostatnie } = wnTabelaOperacji(k.ops12, 8, false);
    wn$('wn-karta').innerHTML = `
        <p class="wn-eyebrow" style="margin-top:14px">Karta kategorii · ${k.przych ? 'przychód' : 'wydatek'} · wszystkie konta</p>
        <h3>${wnEsc(nazwa)}</h3>
        <div class="wn-kpis">${kafle.map(wnKafel).join('')}</div>
        <div class="wn-chartbox" style="height:220px"><canvas id="wn-karta-wykres" aria-label="${wnEsc(nazwa)} w ostatnich 12 miesiącach"></canvas></div>
        <div class="wn-karta-grid">
            <section><h4>Wnioski ${wnMsc(wnYmZ(i))}</h4>${wn.length ? wn.map(x => `<div class="wn-mini wn-ton-${x.ton}"><b>${wnEsc(x.tytul)} · ${wnEsc(x.plakietka)}</b>${wnEsc(x.opis)}</div>`).join('') : `<p class="wn-small wn-muted">${i === d.biezacy ? 'Miesiąc jeszcze trwa, wnioski liczą się z pełnych miesięcy.' : 'Nic nietypowego w tej kategorii.'}</p>`}</section>
            <section><h4>Najwięksi kontrahenci (12 mies.)</h4>${kontr.length ? `<table><thead><tr><th>Kontrahent</th><th class="wn-num">Kwota</th><th class="wn-num">Operacje</th></tr></thead><tbody>${kontr.map(e => `<tr><td>${e.id ? wnPrzyciskDrill('kontrahent', e.id, e.nazwa, wnZl2(e.kwota)) : wnEsc(e.nazwa)}</td><td class="wn-num">${wnZl2(e.kwota)}</td><td class="wn-num">${e.n}</td></tr>`).join('')}</tbody></table>` : '<p class="wn-small wn-muted">Brak operacji.</p>'}</section>
        </div>
        <section style="margin-top:18px"><h4>Ostatnie operacje</h4>${ostatnie}
            <p class="wn-small" style="margin-top:8px"><button type="button" class="wn-link" id="wn-karta-wszystkie">Wszystkie operacje kategorii z 12 miesięcy (${k.ops12.length})</button></p>
        </section>`;
    wnPodepnijDrill(wn$('wn-karta'));
    wn$('wn-karta-wszystkie').addEventListener('click', () => wnDrill(`${nazwa}: operacje`, { f: () => { wnTabela = 'operacje'; } }));
    if (wnKartaWykres) { wnKartaWykres.destroy(); wnKartaWykres = null; }
    if (typeof Chart === 'undefined') return;
    wnKartaWykres = new Chart(wn$('wn-karta-wykres'), {
        type: 'bar',
        data: { labels: k.mies.map(j => (j === k.mies[0] && wnNr(j) !== 0 ? `${WN_M_KR[wnNr(j)]} ${wnRok(j).slice(2)}` : wnKr(j))), datasets: [{ label: nazwa, data: k.mies.map(k.sumaM), backgroundColor: k.mies.map(j => (j === i ? PALETA.ochra : PALETA.stal)), borderRadius: 2, maxBarThickness: 36 }] },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            onClick: (e, els) => {
                if (!els.length) return;
                const j = k.mies[els[0].index];
                wnDrill(`${wnCap(wnNazwa(j))}, ${nazwa}`, { ym: wnYmZ(j), f: () => { wnCfg.okres = { typ: 'miesiac' }; wnTabela = 'operacje'; } });
            },
            onHover: (e, els) => { e.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: x => `${wnZl2(x.parsed.y)} · kliknij, żeby zobaczyć operacje` } } },
            scales: { y: { beginAtZero: true, ticks: wnOsTicks }, x: { grid: { display: false } } },
        },
    });
}

function renderWidok() {
    renderSciezka();
    const wKarcie = !!wnKartaKat;
    ['wn-filtry', 'wn-kpi', 'wn-chartbox', 'wn-tabbar', 'wn-tabela'].forEach(id => { wn$(id).hidden = wKarcie; });
    wn$('wn-karta').hidden = !wKarcie;
    if (wKarcie) {
        wn$('wn-widok-okres').textContent = '';
        renderListyWidokow(); wn$('wn-akcje').innerHTML = '';
        if (wnWykres) { wnWykres.destroy(); wnWykres = null; }
        renderKarta(wnKartaKat);
        return;
    }
    const z = wnZakres(wnCfg), salda = wnCfg.pokaz === 'salda';
    // Saldo nie ma kategorii, kontrahenta ani podziału na przychody i wydatki.
    ['wn-dd-kategorie', 'wn-dd-kontrahenci', 'wn-liczy', 'wn-tabbar'].forEach(id => { wn$(id).hidden = salda; });
    wn$('wn-sald').hidden = !salda;
    wn$('wn-widok-okres').textContent = wnCap(wnEtykietaZakresu(z));
    renderListyWidokow(); renderAkcji(); wnOdswiezFiltry();
    if (salda) { wnRysujSalda(wnCfg, z); return; }
    const ops = wnFiltruj(wnCfg, z);
    wn$('wn-kpi').innerHTML = wnKafelki(wnCfg, ops, z).map(wnKafel).join('');
    wnRysujWykres(wnCfg, ops, z);
    wnRysujTabele(wnCfg, ops, z);
    wnPodepnijDrill(wn$('wn-tabela'));
}

function wnZmienMiesiac(o) {
    const d = wnD();
    wnYm = d.miesiace[Math.min(d.biezacy, Math.max(0, wnI() + o))];
    wnCfg.dzien = null;
    wnWszystkie = false;
    renderWnioskiKarty(); renderWidok();
}

function renderWnioski() {
    if (!wn$('tab-wnioski')) return;
    wnPodpnijFiltry();
    wnI();
    renderWnioskiKarty();
    renderWidok();
}
// Po odświeżeniu danych (fetchInitialData) — tylko gdy zakładka jest otwarta.
function odswiezWnioski() {
    const tab = wn$('tab-wnioski');
    if (tab && !tab.classList.contains('tab-hidden')) renderWnioski();
}

// --- Wejścia z innych zakładek: niezapisany widok ---
function wnOtworzZWidokiem(ym, cfg, opis) {
    wnYm = ym; wnCfg = { ...WN_PUSTY, ...cfg }; wnAktywnyId = null; wnTryb = null; wnTabela = 'zestawienie';
    wnSciezka = []; wnKartaKat = null; wnOpisAdHoc = opis; wnWszystkie = false;
    switchTab('wnioski');
}
// „Szczegółowy raport” z Dashboardu: wybrany miesiąc i kategorie z filtra wykresu.
function wnPokazOkres(ym, kategorieIds) {
    const nazwy = kategorieIds.map(id => (wnKategoria(id) || {}).name).filter(Boolean);
    wnOtworzZWidokiem(ym, { kategorie: [...kategorieIds].sort((a, b) => a - b) },
        nazwy.length === 0 ? 'Szczegółowy raport' : nazwy.length === 1 ? nazwy[0] : `${nazwy.length} kategorie`);
}
// „Cała historia konta” z listy kont (także zamkniętego). Konto z samymi przelewami (np. zamknięta
// lokata) pokazałoby we Wnioskach pusty widok — przelewy są poza sumami, a zamknięte konta poza
// saldami — więc wtedy otwieramy jego Transakcje.
function wnPokazKonto(id) {
    if (!wnD().ops.some(o => o.konto === id)) { viewAccountTransactions(id); return; }
    wnOtworzZWidokiem(wnD().miesiace[wnD().biezacy], { konta: [id], okres: { typ: 'calosc' }, pokaz: 'czas' }, wnKontoNazwa(id) || 'Konto');
}

document.addEventListener('click', e => {
    if (!e.target.closest('.wn-info-wrap')) wnZamknijInfo();
    if (!e.target.closest('details.wn-dd')) document.querySelectorAll('details.wn-dd').forEach(x => { x.open = false; });
    if (!e.target.closest('#wn-drill-menu, button.wn-drill, #tab-wnioski canvas')) wnZamknijMenu();
});
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') wnZamknijInfo();
    const m = wn$('wn-drill-menu');
    if (!m || m.hidden) return;
    if (e.key === 'Escape') { wnZamknijMenu(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const b = [...m.querySelectorAll('button')], k = b.indexOf(document.activeElement);
        b[(k + (e.key === 'ArrowDown' ? 1 : b.length - 1)) % b.length].focus();
        e.preventDefault();
    }
});
