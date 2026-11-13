// =============================================
// WNIOSKI: REGUŁY (bez DOM i bez sieci)
// =============================================
// Każda reguła to czysta funkcja (dane, i) → lista ciekawostek we wspólnym formacie
// (niżej `wnCiekawostka`). Karty na zakładce Wnioski — a później belka na telefonie —
// tylko wyświetlają tę listę. Nowa reguła = test w tests/js/wnioski_reguly.test.js,
// jedna funkcja i wpis w WN_REGULY na końcu pliku.
//
// Dane przygotowuje raz `wnPrzygotuj()`: operacje bez przelewów między własnymi kontami
// i bez kategorii technicznych, z kwotą w PLN po kursie NBP z końca miesiąca.
// Z globalnego stanu korzysta tylko `normalizujTekst()` z 04_helpers.js.

// Progi startowe (decyzja 9) — stałe w kodzie, bez ustawień użytkownika. Przed
// wdrożeniem do sprawdzenia na prawdziwych danych.
const WN_PROGI = {
    oknoMies: 6,           // typowy miesiąc = mediana z tylu poprzednich pełnych miesięcy
    minHistorii: 3,        // … ale z co najmniej tylu
    trendProc: 0.25, trendKwota: 200,
    duzyUdzial: 0.2, duzyKwota: 500,
    nowyKwota: 200, nowyOdHistorii: 6,   // „pierwszy raz” zalewał krótką historię
    wplywKwota: 300,
    stalaTolKwoty: 0.15, stalaTolDni: 5, stalaZmiana: 0.03, stalaZmianaMin: 2,
    bilansPunkty: 0.10, przychodyProc: 0.05, przychodyKwota: 300,
    jednaPrzyczyna: 0.7,
    lukaMinOperacji: 5,    // konto z tyloma operacjami co miesiąc, a teraz bez żadnej = brak wyciągu
    krotkoMaks: 50,
};

const WN_M_MIAN = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
const WN_M_DOP = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];
const WN_M_MSC = ['w styczniu', 'w lutym', 'w marcu', 'w kwietniu', 'w maju', 'w czerwcu', 'w lipcu', 'w sierpniu', 'we wrześniu', 'w październiku', 'w listopadzie', 'w grudniu'];
const WN_M_KR = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

// --- Drobne narzędzia ---
function wnPrzesun(ym, o) {
    const [y, m] = ym.split('-').map(Number);
    const d = new Date(y, m - 1 + o, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
const wnNrM = ym => Number(ym.slice(5)) - 1;
const wnNazwaM = ym => `${WN_M_MIAN[wnNrM(ym)]} ${ym.slice(0, 4)}`;
const wnMsc = ym => `${WN_M_MSC[wnNrM(ym)]} ${ym.slice(0, 4)}`;
const wnDataDl = d => `${Number(d.slice(8))} ${WN_M_DOP[Number(d.slice(5, 7)) - 1]}`;
const wnCap = s => s.charAt(0).toUpperCase() + s.slice(1);
const wnTys = s => s.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
// Kwota zaokrąglona do złotówki („1 234 zł”) i do grosza („1 234,50 zł”); minus typograficzny.
const wnZl = v => (Math.round(v) < 0 ? '−' : '') + wnTys(String(Math.abs(Math.round(v)))) + ' zł';
const wnZl2 = v => (Math.round(v * 100) < 0 ? '−' : '') + wnTys(Math.abs(Number(v)).toFixed(2).replace('.', ',')) + ' zł';
const wnGrosz = v => Math.round(v * 100) / 100;
function wnMediana(xs) {
    if (!xs.length) return 0;
    const s = [...xs].sort((a, b) => a - b);
    const h = s.length >> 1;
    return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
}
const wnSkroc = (s, n = WN_PROGI.krotkoMaks) => (s.length <= n ? s : s.slice(0, n - 1).trimEnd() + '…');

// Wypłaty gotówki to jeden „kontrahent” bez względu na bankomat — inaczej comiesięczna
// wypłata wychodziła jako jednorazowy wydatek u nowego kontrahenta.
const WN_GOTOWKA = 'gotowka';
function wnKluczKontrahenta(t) {
    const tekst = normalizujTekst(`${t.desc || ''} ${t.contractor_name || ''}`);
    if (/bankomat|wyplata gotowki|\batm\b/.test(tekst)) return WN_GOTOWKA;
    if (t.contractor_id) return `k${t.contractor_id}`;
    const nazwa = normalizujTekst(t.contractor_name || '').trim();
    return nazwa ? `n:${nazwa}` : null;
}

// --- Przygotowanie danych ---
// transakcje/kategorie/konta w kształcie z /api/init; kurs(waluta, 'RRRR-MM') → PLN albo null;
// dzis 'RRRR-MM-DD'. Miesiące od pierwszej transakcji do bieżącego (transakcje z datą
// w przyszłości odpadają).
function wnPrzygotuj({ transakcje, kategorie, konta, kurs, dzis }) {
    const kat = new Map(kategorie.map(c => [c.name, c]));
    const kontoById = new Map(konta.map(a => [a.id, a]));
    const posort = transakcje.filter(t => t.date)
        .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.id - b.id));
    const biezacyYm = dzis.slice(0, 7);
    let ym = posort.length && posort[0].date.slice(0, 7) < biezacyYm ? posort[0].date.slice(0, 7) : biezacyYm;
    const miesiace = [];
    for (; ym <= biezacyYm; ym = wnPrzesun(ym, 1)) miesiace.push(ym);
    const idx = new Map(miesiace.map((m, j) => [m, j]));

    const ops = [], brakKursu = new Set(), liczbaTx = new Map();
    posort.forEach(t => {
        const ymT = t.date.slice(0, 7), j = idx.get(ymT);
        if (j === undefined) return;
        if (!liczbaTx.has(t.account_id)) liczbaTx.set(t.account_id, miesiace.map(() => 0));
        liczbaTx.get(t.account_id)[j]++;
        const c = kat.get(t.category);
        // Przelew między własnymi kontami i kategorie techniczne (uzgodnienie salda) nie są ani
        // przychodem, ani wydatkiem. Transakcja z kategorią spoza słownika liczy się po znaku.
        if (c && c.type !== 'income' && c.type !== 'expense') return;
        if (normalizujTekst(t.desc || '').trim() === 'uzgadnianie salda') return;
        const konto = kontoById.get(t.account_id);
        const waluta = (konto && konto.currency) || 'PLN';
        const k = kurs(waluta, ymT);
        if (k === null || k === undefined) { brakKursu.add(waluta); return; }
        ops.push({
            id: t.id, data: t.date, ym: ymT, j, kwota: wnGrosz(t.amount * k),
            kat: t.category, katId: c ? c.id : null, konto: t.account_id,
            kontrId: t.contractor_id || null, nazwa: t.contractor_name || t.desc || '—',
            tytul: t.desc || '', klucz: wnKluczKontrahenta(t),
        });
    });

    const agg = miesiace.map(() => ({ inc: 0, exp: 0, kat: new Map() }));
    const wMies = miesiace.map(() => []);
    const pierwszyKat = new Map(), pierwszaOp = new Map(), serie = new Map(), nazwyKluczy = new Map();
    ops.forEach(o => {
        const a = agg[o.j];
        wMies[o.j].push(o);
        if (o.kwota > 0) a.inc += o.kwota;
        else {
            a.exp -= o.kwota;
            a.kat.set(o.kat, (a.kat.get(o.kat) || 0) - o.kwota);
            if (!pierwszyKat.has(o.kat)) pierwszyKat.set(o.kat, o.j);
        }
        if (!o.klucz) return;
        nazwyKluczy.set(o.klucz, o.klucz === WN_GOTOWKA ? 'Wypłaty gotówki' : o.nazwa);
        if (!pierwszaOp.has(o.klucz)) pierwszaOp.set(o.klucz, o.id);
        if (o.kwota < 0) {
            // Kontrahent z dwiema płatnościami w miesiącu (sklep, stacja) nie jest stałą opłatą.
            const s = serie.get(o.klucz) || { wiele: false, m: new Map() };
            if (s.m.has(o.j)) s.wiele = true;
            s.m.set(o.j, { kwota: -o.kwota, dzien: Number(o.data.slice(8)), o });
            serie.set(o.klucz, s);
        }
    });

    // Miesiąc z niepełnym importem: konto, które w każdym z 3 poprzednich miesięcy miało
    // kilka operacji, nagle nie ma żadnej. Taki miesiąc zaniżałby medianę („Inne: −100%”),
    // więc wypada z okna, a dla niego samego wniosków nie liczymy.
    const lukiKonta = new Map();
    liczbaTx.forEach((ile, konto) => {
        for (let j = 3; j < miesiace.length; j++) {
            if (!ile[j] && [1, 2, 3].every(o => ile[j - o] >= WN_PROGI.lukaMinOperacji)) {
                (lukiKonta.get(j) || lukiKonta.set(j, []).get(j)).push(konto);
            }
        }
    });

    return {
        miesiace, idx, biezacy: miesiace.length - 1, ops, wMies, agg, kat, kontoById,
        pierwszyKat, pierwszaOp, serie, nazwyKluczy, lukiKonta, brakKursu, pam: new Map(),
    };
}

const wnPam = (d, klucz, f) => (d.pam.has(klucz) ? d.pam.get(klucz) : d.pam.set(klucz, f()).get(klucz));

// Okno typowego miesiąca: do 6 poprzednich miesięcy, bez miesięcy z luką w imporcie.
function wnOkno(d, i) {
    const okno = [];
    for (let j = Math.max(0, i - WN_PROGI.oknoMies); j < i; j++) if (!d.lukiKonta.has(j)) okno.push(j);
    return okno;
}

// --- Wspólny format ciekawostki ---
// Ten sam kształt oddadzą przyszłe źródła belki (świeżość danych, harmonogram, tydzień):
//   klucz     — niepowtarzalny w obrębie okresu
//   zrodlo    — 'miesiac' (wnioski miesięczne); belka rozróżnia po nim miejsca
//   okres     — { typ: 'miesiac', ym }
//   rodzaj, ton ('gorzej' | 'lepiej' | 'info'), plakietka
//   temat     — { typ: 'kategoria' | 'kontrahent' | 'ogolny', nazwa } — do kciuków
//   tytul, krotko (≤ 50 znaków, na belkę), opis (jedno zdanie), kwota, delta, suf, meta
//   waga      — kwota, o którą chodzi (stałe opłaty w skali roku); po niej kolejność
//   iskra     — { od: 'RRRR-MM', wartosci: [7 miesięcy] } albo null
//   pokaz     — { cfg, tabela, opis }: częściowa konfiguracja widoku dla „Pokaż operacje”
function wnCiekawostka(d, i, x) {
    const ym = d.miesiace[i];
    return {
        zrodlo: 'miesiac', okres: { typ: 'miesiac', ym }, delta: '', suf: '', meta: '', iskra: null,
        ...x,
        klucz: `${x.klucz}@${ym}`,
        krotko: wnSkroc(x.krotko || `${x.tytul}: ${x.kwota}`),
    };
}

function wnIskra(d, i, f) {
    const od = Math.max(0, i - WN_PROGI.oknoMies);
    const wartosci = [];
    for (let j = od; j <= i; j++) wartosci.push(wnGrosz(f(j)));
    return { od: d.miesiace[od], wartosci };
}

const wnKatId = (d, nazwa) => (d.kat.get(nazwa) ? d.kat.get(nazwa).id : null);
const wnTylkoId = id => (id === null || id === undefined ? [] : [id]);
const wnNazwaKonta = (d, id) => (d.kontoById.get(id) ? d.kontoById.get(id).name : '');
// Tytuł operacji jako pierwsze zdanie opisu — chyba że to ta sama nazwa co w nagłówku karty.
const wnTytulZdanie = o => (o.tytul && normalizujTekst(o.tytul) !== normalizujTekst(o.nazwa) ? `${o.tytul}. ` : '');
const wnMeta = (d, o) => [wnDataDl(o.data), o.kat, wnNazwaKonta(d, o.konto)].filter(Boolean).join(' · ');

// Widok „ta operacja”: kategoria i miesiąc, tabela operacji.
const wnPokazOperacji = (d, o, liczy) => ({
    cfg: { okres: { typ: 'miesiac' }, kategorie: wnTylkoId(o.katId), liczy, pokaz: 'kontrahenci' },
    tabela: 'operacje', opis: o.katId !== null ? o.kat : (liczy === 'przychody' ? 'Przychody' : 'Wydatki'),
});

// --- Seria płatności kontrahenta (stałe opłaty) ---
function wnPodobne(a, b) {
    return Math.abs(a.kwota - b.kwota) <= WN_PROGI.stalaTolKwoty * Math.max(a.kwota, b.kwota)
        && Math.abs(a.dzien - b.dzien) <= WN_PROGI.stalaTolDni;
}
function wnCiag(s, od, doM) {
    if (od < 0) return false;
    for (let j = od; j <= doM; j++) {
        if (!s.m.has(j)) return false;
        if (j > od && !wnPodobne(s.m.get(j - 1), s.m.get(j))) return false;
    }
    return true;
}
// Czy do miesiąca i kontrahent był już stałą opłatą (3 podobne płatności z rzędu)?
function wnStalaDo(s, i) {
    for (const j of s.m.keys()) if (j <= i && wnCiag(s, j - 2, j)) return true;
    return false;
}

// --- Składniki wspólne kilku reguł („jedna przyczyna, jeden wniosek”) ---
function wnDuzeWydatki(d, i) {
    return wnPam(d, `duze${i}`, () => {
        const okno = wnOkno(d, i);
        const typWyd = wnMediana(okno.map(j => d.agg[j].exp));
        const prog = Math.max(WN_PROGI.duzyKwota, WN_PROGI.duzyUdzial * typWyd);
        return d.wMies[i].filter(o => {
            if (o.kwota >= 0 || -o.kwota < prog) return false;
            const s = o.klucz && d.serie.get(o.klucz);
            if (s && !s.wiele && wnStalaDo(s, i)) return false;
            // Regularny duży wydatek (np. comiesięczna wypłata gotówki): w co najmniej 3 miesiącach
            // okna u tego kontrahenta był wydatek co najmniej o połowę tej kwoty.
            if (o.klucz) {
                const podobnych = okno.filter(j => d.wMies[j].some(p => p.klucz === o.klucz && -p.kwota >= -o.kwota / 2)).length;
                if (podobnych >= 3) return false;
            }
            return true;
        });
    });
}

function wnNowiKontrahenci(d, i) {
    return wnPam(d, `nowi${i}`, () => {
        if (i < WN_PROGI.nowyOdHistorii) return [];
        const duze = wnDuzeWydatki(d, i);
        return d.wMies[i].filter(o => o.kwota < 0 && -o.kwota >= WN_PROGI.nowyKwota && o.klucz
            && o.klucz !== WN_GOTOWKA && d.pierwszaOp.get(o.klucz) === o.id && !duze.includes(o));
    });
}

function wnNietypoweWplywy(d, i) {
    return wnPam(d, `wplywy${i}`, () => {
        const okno = wnOkno(d, i);
        const zwykle = new Set();
        okno.forEach(j => d.wMies[j].forEach(o => { if (o.kwota > 0) zwykle.add(o.klucz); }));
        return d.wMies[i].filter(o => o.kwota >= WN_PROGI.wplywKwota && o.klucz && !zwykle.has(o.klucz));
    });
}

// --- Reguły ---
function wnRegulaJednorazowe(d, i) {
    const okno = wnOkno(d, i);
    const typWyd = wnMediana(okno.map(j => d.agg[j].exp));
    const lista = [];
    wnDuzeWydatki(d, i).forEach(o => {
        const wiekszy = d.ops.filter(p => p.kwota < 0 && p.data < o.data && p.kwota <= o.kwota).pop();
        lista.push(wnCiekawostka(d, i, {
            klucz: `duzy-${o.id}`, rodzaj: 'Jednorazowe zdarzenie', ton: 'info', plakietka: 'jednorazowo',
            temat: { typ: 'kontrahent', nazwa: o.nazwa }, tytul: o.nazwa, kwota: wnZl2(-o.kwota),
            krotko: `${o.nazwa}: ${wnZl(-o.kwota)} jednorazowo`,
            opis: `${wnTytulZdanie(o)}`
                + (wiekszy ? `Większy pojedynczy wydatek był ostatnio ${wnMsc(wiekszy.ym)} (${wiekszy.nazwa}, ${wnZl(-wiekszy.kwota)}).` : 'Największy pojedynczy wydatek w całej historii.')
                + (typWyd > 0 ? ` To ${Math.round(-o.kwota / typWyd * 100)}% typowych miesięcznych wydatków.` : ''),
            meta: wnMeta(d, o), waga: -o.kwota, pokaz: wnPokazOperacji(d, o, 'wydatki'),
        }));
    });
    wnNowiKontrahenci(d, i).forEach(o => lista.push(wnCiekawostka(d, i, {
        klucz: `nowy-${o.id}`, rodzaj: 'Jednorazowe zdarzenie', ton: 'info', plakietka: 'pierwszy raz',
        temat: { typ: 'kontrahent', nazwa: o.nazwa }, tytul: o.nazwa, kwota: wnZl2(-o.kwota),
        krotko: `Pierwszy raz: ${o.nazwa}, ${wnZl(-o.kwota)}`,
        opis: `${wnTytulZdanie(o)}Pierwsza płatność u tego kontrahenta.`,
        meta: wnMeta(d, o), waga: -o.kwota, pokaz: wnPokazOperacji(d, o, 'wydatki'),
    })));
    wnNietypoweWplywy(d, i).forEach(o => lista.push(wnCiekawostka(d, i, {
        klucz: `wplyw-${o.id}`, rodzaj: 'Jednorazowe zdarzenie', ton: 'lepiej', plakietka: 'dodatkowy wpływ',
        temat: { typ: 'kontrahent', nazwa: o.nazwa }, tytul: o.nazwa, kwota: '+' + wnZl2(o.kwota),
        krotko: `Wpływ: ${o.nazwa}, +${wnZl(o.kwota)}`,
        opis: `${wnTytulZdanie(o)}Od tego nadawcy nic nie wpłynęło w ${okno.length} poprzednich miesiącach.`,
        meta: wnMeta(d, o), waga: o.kwota, pokaz: wnPokazOperacji(d, o, 'przychody'),
    })));
    return lista;
}

function wnRegulaTrendy(d, i) {
    const okno = wnOkno(d, i), lista = [];
    const pokryte = [...wnDuzeWydatki(d, i), ...wnNowiKontrahenci(d, i)];
    d.pierwszyKat.forEach((od, nazwa) => {
        const c = d.kat.get(nazwa);
        if ((c && c.type !== 'expense') || i - od < WN_PROGI.minHistorii) return;
        const okn = okno.filter(j => j >= od);
        const sumaK = j => d.agg[j].kat.get(nazwa) || 0;
        const typ = wnMediana(okn.map(sumaK)), teraz = sumaK(i), r = teraz - typ;
        if (Math.abs(r) < WN_PROGI.trendKwota || (typ > 0 && Math.abs(r) < WN_PROGI.trendProc * typ)) return;
        // „Mniej niż zwykle” ma sens tylko w kategorii, w której wydaje się co miesiąc.
        if (r < 0 && !okn.every(j => sumaK(j) > 0)) return;
        // Skok, który w 70% wyjaśnia jedna operacja, pokazuje się tylko jako ta operacja.
        const zOperacji = pokryte.filter(o => o.kat === nazwa).reduce((s, o) => s - o.kwota, 0);
        if (r > 0 && zOperacji >= WN_PROGI.jednaPrzyczyna * r) return;
        let seria = 0;
        for (let j = i; j > od && (r > 0 ? sumaK(j) > sumaK(j - 1) : sumaK(j) < sumaK(j - 1)); j--) seria++;
        const proc = typ > 0 ? Math.round(Math.abs(r) / typ * 100) : null;
        lista.push(wnCiekawostka(d, i, {
            klucz: `trend-${nazwa}`, rodzaj: 'Trend kategorii', ton: r > 0 ? 'gorzej' : 'lepiej',
            plakietka: r > 0 ? 'więcej niż zwykle' : 'mniej niż zwykle',
            temat: { typ: 'kategoria', nazwa }, tytul: nazwa, kwota: wnZl(teraz),
            delta: typ > 0 ? (r > 3 * typ ? `${Math.round(teraz / typ)}× więcej` : `${r > 0 ? '+' : '−'}${proc}%`) : '',
            krotko: `${nazwa}: ${wnZl(teraz)}` + (proc !== null ? `, ${r > 0 ? '+' : '−'}${proc}% do zwykłych` : ''),
            opis: (typ > 0 ? `Zwykle ${wnZl(typ)} (mediana z ${okn.length} mies.).` : 'Zwykle w tej kategorii nic.')
                + (seria >= 2 ? ` ${r > 0 ? 'Rośnie' : 'Spada'} od ${seria} miesięcy.` : ''),
            iskra: wnIskra(d, i, sumaK), waga: Math.abs(r),
            pokaz: { cfg: { okres: { typ: 'n', n: 6 }, kategorie: wnTylkoId(wnKatId(d, nazwa)), liczy: 'wydatki', pokaz: 'czas' }, tabela: 'operacje', opis: nazwa },
        }));
    });
    return lista;
}

function wnRegulaStaleOplaty(d, i) {
    const lista = [];
    d.serie.forEach((s, klucz) => {
        if (s.wiele || klucz === WN_GOTOWKA) return;
        const a = j => s.m.get(j);
        const nazwa = d.nazwyKluczy.get(klucz);
        const ostatnia = a(i) || a(i - 1) || a(i - 2);
        const kontrId = klucz.startsWith('k') ? Number(klucz.slice(1)) : null;
        // Kontrahent bez wpisu w słowniku nie ma ID do filtra — wtedy kategoria ostatniej płatności.
        const cfg = kontrId
            ? { okres: { typ: 'n', n: 6 }, kontrahenci: [kontrId], liczy: 'wydatki', pokaz: 'czas' }
            : { okres: { typ: 'n', n: 6 }, kategorie: wnTylkoId(ostatnia && ostatnia.o.katId), liczy: 'wydatki', pokaz: 'czas' };
        const wspolne = {
            rodzaj: 'Stała opłata', temat: { typ: 'kontrahent', nazwa }, tytul: nazwa, suf: 'miesięcznie',
            kategoria: ostatnia ? ostatnia.o.kat : null,
            iskra: wnIskra(d, i, j => (a(j) ? a(j).kwota : 0)),
            pokaz: { cfg, tabela: 'operacje', opis: nazwa },
        };
        if (a(i) && wnCiag(s, i - 3, i - 1) && Math.abs(a(i).dzien - a(i - 1).dzien) <= WN_PROGI.stalaTolDni) {
            const r = a(i).kwota - a(i - 1).kwota;
            if (Math.abs(r) >= Math.max(WN_PROGI.stalaZmianaMin, WN_PROGI.stalaZmiana * a(i - 1).kwota)) {
                lista.push(wnCiekawostka(d, i, {
                    ...wspolne, klucz: `zmiana-${klucz}`, ton: r > 0 ? 'gorzej' : 'lepiej', plakietka: r > 0 ? 'podwyżka' : 'obniżka',
                    kwota: wnZl2(a(i).kwota), krotko: `${r > 0 ? 'Podwyżka' : 'Obniżka'}: ${nazwa}, ${wnZl2(a(i).kwota)}`,
                    opis: `Wcześniej ${wnZl2(a(i - 1).kwota)}. To ${wnZl2(Math.abs(r))} ${r > 0 ? 'więcej' : 'mniej'} co miesiąc, ${wnZl(Math.abs(r) * 12)} w skali roku.`,
                    waga: Math.abs(r) * 12,
                }));
            }
        }
        const pierwszy = Math.min(...s.m.keys());
        if (pierwszy >= 1 && pierwszy >= i - 2 && pierwszy < i && wnCiag(s, pierwszy, i)) {
            lista.push(wnCiekawostka(d, i, {
                ...wspolne, klucz: `nowa-${klucz}`, ton: 'info', plakietka: 'nowa', kwota: wnZl2(a(i).kwota),
                krotko: `Nowa stała opłata: ${nazwa}`,
                opis: `Płacona co miesiąc od ${WN_M_DOP[wnNrM(d.miesiace[pierwszy])]}. W skali roku to ${wnZl(a(i).kwota * 12)}.`,
                waga: a(i).kwota * 12,
            }));
        }
        if (!a(i) && !a(i - 1) && wnCiag(s, i - 4, i - 2)) {
            lista.push(wnCiekawostka(d, i, {
                ...wspolne, klucz: `znikla-${klucz}`, ton: 'info', plakietka: 'przestała się pojawiać', kwota: wnZl2(a(i - 2).kwota),
                krotko: `${nazwa}: brak opłaty od 2 miesięcy`,
                opis: `Ostatnia płatność ${wnDataDl(a(i - 2).o.data)}. ${wnCap(WN_M_MSC[wnNrM(d.miesiace[i - 1])])} i ${WN_M_MSC[wnNrM(d.miesiace[i])]} jej nie było. Jeśli to rezygnacja, w skali roku zostaje ${wnZl(a(i - 2).kwota * 12)}.`,
                waga: a(i - 2).kwota * 12,
            }));
        }
    });
    return lista;
}

function wnRegulaBilans(d, i) {
    const A = d.agg[i], okno = wnOkno(d, i), lista = [];
    if (A.inc <= 0) return lista;
    const stopaM = j => (d.agg[j].inc > 0 ? (d.agg[j].inc - d.agg[j].exp) / d.agg[j].inc : 0);
    const zostalo = A.inc - A.exp, stopa = zostalo / A.inc;
    const oknoZPrzych = okno.filter(j => d.agg[j].inc > 0);
    const typ = wnMediana(oknoZPrzych.map(stopaM));
    if (oknoZPrzych.length && Math.abs(stopa - typ) >= WN_PROGI.bilansPunkty) {
        const luka = (typ - stopa) * A.inc;
        const przyczyna = stopa < typ
            ? wnDuzeWydatki(d, i).slice().sort((x, y) => x.kwota - y.kwota).find(o => -o.kwota >= 0.5 * luka)
            : null;
        lista.push(wnCiekawostka(d, i, {
            klucz: 'bilans', rodzaj: 'Bilans', ton: stopa < typ ? 'gorzej' : 'lepiej',
            plakietka: stopa < typ ? 'zostało mniej niż zwykle' : 'zostało więcej niż zwykle',
            temat: { typ: 'ogolny', nazwa: 'bilans' }, tytul: 'Co zostało z przychodów',
            kwota: `${Math.round(stopa * 100)}%`, suf: zostalo >= 0 ? `czyli ${wnZl(zostalo)}` : '',
            krotko: `Zostało ${Math.round(stopa * 100)}% przychodów, zwykle ${Math.round(typ * 100)}%`,
            opis: (zostalo >= 0 ? '' : `Wydatki przewyższyły przychody o ${wnZl(-zostalo)}. `)
                + `Zwykle zostaje ${Math.round(typ * 100)}% przychodów, czyli przy tych przychodach ${wnZl(typ * A.inc)}.`
                + (przyczyna ? ` Główna przyczyna: ${przyczyna.nazwa}, ${wnZl(-przyczyna.kwota)}.` : ''),
            iskra: wnIskra(d, i, j => Math.round(stopaM(j) * 100)), waga: Math.abs(luka),
            pokaz: { cfg: { okres: { typ: 'n', n: 6 }, liczy: 'oba', pokaz: 'czas' }, tabela: 'zestawienie', opis: 'Bilans' },
        }));
    }
    const typInc = wnMediana(okno.map(j => d.agg[j].inc)), r = A.inc - typInc;
    const dodatkowe = wnNietypoweWplywy(d, i).reduce((s, o) => s + o.kwota, 0);
    if (typInc > 0 && Math.abs(r) >= Math.max(WN_PROGI.przychodyKwota, WN_PROGI.przychodyProc * typInc)
        && !(r > 0 && dodatkowe >= WN_PROGI.jednaPrzyczyna * r)) {
        const proc = Math.round(Math.abs(r) / typInc * 100);
        lista.push(wnCiekawostka(d, i, {
            klucz: 'przychody', rodzaj: 'Bilans', ton: r > 0 ? 'lepiej' : 'gorzej',
            plakietka: r > 0 ? 'więcej niż zwykle' : 'mniej niż zwykle',
            temat: { typ: 'ogolny', nazwa: 'przychody' }, tytul: 'Przychody', kwota: wnZl(A.inc),
            delta: `${r > 0 ? '+' : '−'}${proc}%`, krotko: `Przychody: ${wnZl(A.inc)}, ${r > 0 ? '+' : '−'}${proc}% do zwykłych`,
            opis: `Zwykle ${wnZl(typInc)} (mediana z ${okno.length} mies.).`,
            iskra: wnIskra(d, i, j => d.agg[j].inc), waga: Math.abs(r),
            pokaz: { cfg: { okres: { typ: 'n', n: 6 }, liczy: 'przychody', pokaz: 'czas' }, tabela: 'zestawienie', opis: 'Przychody' },
        }));
    }
    return lista;
}

// Wnioski za miesiąc 'RRRR-MM'. stan: 'ok' | 'trwa' (bieżący miesiąc) | 'malo' (za krótka
// historia) | 'luka' (brak wyciągu z któregoś konta — `konta` to ich ID) | 'brak' (poza danymi).
function wnWnioskiZa(d, ym) {
    const i = d.idx.get(ym);
    if (i === undefined) return { stan: 'brak', lista: [] };
    if (i >= d.biezacy) return { stan: 'trwa', lista: [] };
    if (d.lukiKonta.has(i)) return { stan: 'luka', lista: [], konta: d.lukiKonta.get(i) };
    const okno = wnOkno(d, i);
    if (i < WN_PROGI.minHistorii || okno.length < WN_PROGI.minHistorii) return { stan: 'malo', lista: [] };
    const lista = WN_REGULY.flatMap(r => r(d, i)).sort((a, b) => b.waga - a.waga);
    return { stan: 'ok', lista, okno: okno.length };
}

// Kolejność nie ma znaczenia dla wyniku — wnioski sortuje waga.
const WN_REGULY = [wnRegulaJednorazowe, wnRegulaTrendy, wnRegulaStaleOplaty, wnRegulaBilans];
