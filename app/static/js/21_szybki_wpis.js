// --- SZYBKI WPIS TRANSAKCJI ---
// Jedna linia tekstu („Biedronka 85,60 wczoraj") rozkładana na pola formularza
// transakcji. Pola pod spodem (te same co wcześniej, te same id i ten sam zapis
// w 11_transactions.js) pokazują, co aplikacja zrozumiała; ręczna zmiana pola
// wygrywa z rozpoznaniem. Plan: docs/plany/poprawka-wizualna-aplikacji.md, sekcja 2.

const RE_KWOTA = /^(\d+(?:[.,]\d{1,2})?)(?:zł|zl|pln)?$/i;
const RE_DATA = /^(\d{1,2})\.(\d{1,2})\.?(\d{4})?$/;
const SLOWA_DATY = { dzis: 0, dzisiaj: 0, wczoraj: 1, przedwczoraj: 2 };

// Konto po fragmencie nazwy — tylko gdy jednoznaczne (dwa konta „Konto …" nie dają wyniku).
function kontoPoFragmencie(fragment) {
    const f = normalizujTekst(fragment);
    if (!f) return null;
    const pasujace = accounts.filter(a => normalizujTekst(a.name).split(/\s+/).some(w => w.startsWith(f)));
    return pasujace.length === 1 ? pasujace[0] : null;
}

const pierwszaKategoriaPrzelewu = () => categories.find(c => c.type === 'transfer') || null;
const kategorieWpisu = () => categories.filter(c => (c.type === 'income' || c.type === 'expense') && !c.is_system_category);

// Rozkłada linię na: kwota, data (null = formularz wstawi dziś), konto (@), konto docelowe (>),
// nazwa (tekst bez kwoty, daty i znaczników), kontrahent i kategoria.
function rozlozWpis(tekst, dzis = new Date()) {
    const wynik = { kwota: null, data: null, konto: null, docelowe: null, nazwa: '', kontrahent: null, kategoria: null };
    let tokeny = String(tekst).trim().split(/\s+/).filter(Boolean);

    tokeny = tokeny.filter(t => {
        if (t[0] === '@') { wynik.konto = kontoPoFragmencie(t.slice(1)); return false; }
        if (t[0] === '>') { wynik.docelowe = kontoPoFragmencie(t.slice(1)); return false; }
        const ileDni = SLOWA_DATY[normalizujTekst(t)];
        if (ileDni !== undefined) {
            wynik.data = toLocalISODate(new Date(dzis.getFullYear(), dzis.getMonth(), dzis.getDate() - ileDni));
            return false;
        }
        return true;
    });

    // „12.10" samo jest kwotą; datą staje się dopiero obok osobnej kwoty albo z rokiem.
    // Data bez roku zawsze wskazuje przeszłość (ostatnie takie wystąpienie) — przyszłą
    // datę ustawia się w polu Data.
    const liczby = tokeny.filter(t => RE_KWOTA.test(t) || RE_DATA.test(t));
    if (!wynik.data) {
        const kandydat = tokeny.find(t => {
            const m = t.match(RE_DATA);
            return m && (m[3] || liczby.length > 1);
        });
        const m = kandydat && kandydat.match(RE_DATA);
        if (m) {
            const [d, mies] = [Number(m[1]), Number(m[2])];
            let rok = m[3] ? Number(m[3]) : dzis.getFullYear();
            let data = new Date(rok, mies - 1, d);
            if (!m[3] && data > dzis) data = new Date(--rok, mies - 1, d);
            if (data.getMonth() === mies - 1 && data.getDate() === d) {  // 31.02 nie istnieje
                wynik.data = toLocalISODate(data);
                tokeny.splice(tokeny.indexOf(kandydat), 1);
            }
        }
    }
    const kwota = [...tokeny].reverse().find(t => RE_KWOTA.test(t));
    if (kwota) {
        wynik.kwota = parseFloat(kwota.match(RE_KWOTA)[1].replace(',', '.'));
        tokeny.splice(tokeny.lastIndexOf(kwota), 1);
    }

    wynik.nazwa = tokeny.join(' ');
    if (wynik.docelowe) {
        const k = pierwszaKategoriaPrzelewu();
        wynik.kategoria = k ? k.name : null;
        return wynik;
    }
    const n = normalizujTekst(wynik.nazwa);
    if (n.length >= 2) {
        wynik.kontrahent = dopasujKontrahenta(wynik.nazwa)
            || contractors.find(c => !c.name.startsWith('Moje konto: ') && normalizujTekst(c.name).startsWith(n))
            || null;
        if (wynik.kontrahent) {
            wynik.kategoria = wynik.kontrahent.default_category_name || null;
        } else {
            const k = kategorieWpisu().find(c => normalizujTekst(c.name).startsWith(n));
            wynik.kategoria = k ? k.name : null;
        }
    }
    return wynik;
}

// Tytuł transakcji (kolumna „Opis"): tekst nazwy z wpisu, a gdy go nie ma — nazwa kategorii.
function tytulWpisu(wpis, kategoria) {
    return wpis.nazwa || kategoria || '';
}

// Podpowiedzi dla końcówki pola: konta po „@"/„>", inaczej kontrahenci i kategorie po
// początku nazwy; nieznana nazwa (min. 3 znaki) dostaje „Dodaj kontrahenta".
function sugestieWpisu(tekst, kontoZrodloweId) {
    const m = tekst.match(/(?:^|\s)([>@])(\S*)$/);
    if (m) {
        const f = normalizujTekst(m[2]);
        return accounts
            .filter(a => m[1] === '@' || a.id !== kontoZrodloweId)
            .filter(a => !f || normalizujTekst(a.name).split(/\s+/).some(w => w.startsWith(f)))
            .map(a => ({ typ: 'konto', znacznik: m[1], fragment: m[1] + m[2], konto: a, nazwa: a.name,
                         opis: m[1] === '>' ? 'przelew na to konto' : 'konto transakcji' }));
    }
    if (/\s$/.test(tekst)) return [];
    const wpis = rozlozWpis(tekst);
    const n = normalizujTekst(wpis.nazwa);
    if (!n || !tekst.endsWith(wpis.nazwa)) return [];
    const ranga = nazwa => (normalizujTekst(nazwa).startsWith(n) ? 0 : normalizujTekst(nazwa).split(/\s+/).some(w => w.startsWith(n)) ? 1 : 2);
    const kontrahenci = contractors
        .filter(c => !c.name.startsWith('Moje konto: ') && ranga(c.name) < 2)
        .sort((a, b) => ranga(a.name) - ranga(b.name))
        .map(c => ({ typ: 'kontrahent', kontrahent: c, nazwa: c.name, opis: c.default_category_name || 'bez kategorii' }));
    const kat = kategorieWpisu()
        .filter(c => ranga(c.name) < 2)
        .map(c => ({ typ: 'kategoria', nazwa: c.name, opis: 'kategoria' }));
    const wszystkie = [...kontrahenci, ...kat];
    if (wszystkie.some(s => normalizujTekst(s.nazwa) === n)) return [];
    if (!kontrahenci.length && n.length >= 3) {
        wszystkie.push({ typ: 'nowy', nazwa: `Dodaj kontrahenta „${wpis.nazwa}”`, opis: 'nowy w słowniku', nowaNazwa: wpis.nazwa });
    }
    return wszystkie.slice(0, 7);
}

// Najczęściej używani kontrahenci z ostatnich 90 dni (bez przelewów „Moje konto").
function najczestsiKontrahenci(dzis = new Date(), ile = 5) {
    const od = toLocalISODate(new Date(dzis.getFullYear(), dzis.getMonth(), dzis.getDate() - 90));
    const licznik = new Map();
    transactions.forEach(t => {
        if (t.contractor_id && t.date >= od) licznik.set(t.contractor_id, (licznik.get(t.contractor_id) || 0) + 1);
    });
    return contractors
        .filter(c => licznik.has(c.id) && !c.name.startsWith('Moje konto: '))
        .sort((a, b) => licznik.get(b.id) - licznik.get(a.id) || a.name.localeCompare(b.name, 'pl'))
        .slice(0, ile);
}

// --- Obsługa formularza ---

const szybkiWpis = { sugestie: [], wybrana: 0, strzalkami: false, reczne: new Set(), przyklad: 0 };
const POLA_WPISU = {
    kwota: 'tx-amount', kontrahent: 'tx-contractor-input', kategoria: 'tx-category',
    konto: 'tx-account', data: 'tx-date', docelowe: 'tx-dest-account',
};
const pole = klucz => document.getElementById(POLA_WPISU[klucz]);
// Telefon i tablet rozpoznajemy po wskaźniku, nie po szerokości — wąskie okno na komputerze
// nadal ma klawisz Tab.
const ekranDotykowy = () => !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

function ustawKategorieWpisu(nazwa) {
    const el = pole('kategoria');
    if (el.value === (nazwa || '')) return;
    el.value = nazwa || '';
    el.dispatchEvent(new Event('change'));  // przełącza pola przelewu (11_transactions.js)
    delete el.dataset.userSet;              // ustawienie automatyczne, nie ręczne
}

// Przenosi rozpoznany wpis do pól, których użytkownik nie zmieniał ręcznie.
function wypelnijPolaWpisu(wpis) {
    const r = szybkiWpis.reczne;
    if (!r.has('kwota')) pole('kwota').value = wpis.kwota != null ? wpis.kwota.toFixed(2) : '';
    if (!r.has('kontrahent')) {
        document.getElementById('tx-contractor').value = wpis.kontrahent ? wpis.kontrahent.id : '';
        pole('kontrahent').value = wpis.kontrahent ? wpis.kontrahent.name : '';
    }
    if (!r.has('kategoria')) ustawKategorieWpisu(wpis.kategoria);
    if (!r.has('konto')) {
        const konto = wpis.konto ? wpis.konto.id : (szybkiWpis.zachowaneKonto || preferredFormAccountId());
        if (konto && pole('konto').value != konto) {
            pole('konto').value = konto;
            pole('konto').dispatchEvent(new Event('change'));
        }
    }
    if (!r.has('docelowe') && wpis.docelowe) pole('docelowe').value = wpis.docelowe.id;
    if (!r.has('data')) pole('data').value = wpis.data || szybkiWpis.zachowanaData || toLocalISODate(new Date());
    document.querySelectorAll('[data-wpis-znacznik]').forEach(el => {
        const klucz = el.dataset.wpisZnacznik;
        el.textContent = r.has(klucz) ? 'ręcznie' : '';
    });
}

function odswiezSzybkiWpis() {
    const q = document.getElementById('tx-desc');
    const wpis = rozlozWpis(q.value);
    szybkiWpis.wpis = wpis;
    szybkiWpis.sugestie = sugestieWpisu(q.value, Number(pole('konto').value) || preferredFormAccountId());
    if (szybkiWpis.wybrana >= szybkiWpis.sugestie.length) szybkiWpis.wybrana = 0;

    // Pola pokazują to, co wstawiłby Tab — także po wyborze strzałkami.
    const s = szybkiWpis.sugestie[szybkiWpis.wybrana];
    const podglad = { ...wpis };
    if (s && s.typ === 'kontrahent') { podglad.kontrahent = s.kontrahent; podglad.kategoria = s.kontrahent.default_category_name || null; }
    if (s && s.typ === 'kategoria') { podglad.kontrahent = null; podglad.kategoria = s.nazwa; }
    if (s && s.typ === 'konto' && s.znacznik === '>') { podglad.docelowe = s.konto; podglad.kategoria = pierwszaKategoriaPrzelewu()?.name || null; }
    if (s && s.typ === 'konto' && s.znacznik === '@') podglad.konto = s.konto;
    // Puste pole też: rozpoznane wcześniej wartości wracają do domyślnych (ręczne zostają).
    wypelnijPolaWpisu(podglad);
    rysujPodpowiedziWpisu(wpis);
    podsumujWpis();
}

function rysujPodpowiedziWpisu(wpis) {
    const q = document.getElementById('tx-desc');
    const lista = document.getElementById('tx-quick-sugg');
    const dotyk = ekranDotykowy();
    lista.replaceChildren(...szybkiWpis.sugestie.map((s, i) => {
        const li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', String(i === szybkiWpis.wybrana));
        li.className = `flex items-baseline justify-between gap-3 px-3 py-2 cursor-pointer rounded-md ${i === szybkiWpis.wybrana ? 'bg-blue-50' : 'hover:bg-slate-50'}`;
        const nazwa = document.createElement('span');
        nazwa.className = s.typ === 'nowy' ? 'text-emerald-700 font-medium' : 'text-slate-800';
        nazwa.textContent = s.nazwa;
        const opis = document.createElement('small');
        opis.className = 'text-xs text-slate-500 whitespace-nowrap';
        opis.textContent = s.opis + (i === szybkiWpis.wybrana && !dotyk ? '  ⇥ Tab' : '');
        li.append(nazwa, opis);
        li.addEventListener('mousedown', e => { e.preventDefault(); wybierzPodpowiedzWpisu(i); });
        return li;
    }));
    lista.classList.toggle('hidden', !szybkiWpis.sugestie.length || document.activeElement !== q);

    // Szara podpowiedź w polu: dokończenie nazwy, potem nazwa kolejnego kroku.
    const tlo = document.getElementById('tx-quick-ghost');
    tlo.replaceChildren();
    const tekst = q.value;
    if (!tekst) return;
    const s = szybkiWpis.sugestie[szybkiWpis.wybrana];
    const odstep = /\s$/.test(tekst) ? '' : ' ';
    let wskazowka;
    if (s && s.typ === 'konto') {
        wskazowka = `   ⇥ ${s.nazwa}`;
    } else if (s && s.typ !== 'nowy' && normalizujTekst(s.nazwa).startsWith(normalizujTekst(wpis.nazwa))) {
        wskazowka = s.nazwa.slice(wpis.nazwa.length) + '   ⇥ Tab';
    } else if (s) {
        wskazowka = `   ⇥ ${s.nazwa}`;
    } else if (!wpis.nazwa && !wpis.docelowe) {
        wskazowka = odstep + 'kontrahent';
    } else if (wpis.kwota == null) {
        wskazowka = odstep + 'kwota';
    } else if (!wpis.data) {
        wskazowka = odstep + 'data   ↵ dziś';
    } else {
        wskazowka = '   ↵ zapisz';
    }
    // Na telefonie nie ma klawisza Tab: zostaje dokończenie nazwy i nazwa kroku, bez symboli.
    if (dotyk) wskazowka = wskazowka.replace(/\s{3}[⇥↵].*$/, '');
    const wpisany = document.createElement('span');
    wpisany.className = 'text-transparent';
    wpisany.textContent = tekst;
    const szare = document.createElement('span');
    szare.className = 'text-slate-400';
    szare.textContent = wskazowka;
    tlo.append(wpisany, szare);
}

function wybierzPodpowiedzWpisu(i) {
    const s = szybkiWpis.sugestie[i];
    const q = document.getElementById('tx-desc');
    if (!s) return;
    if (s.typ === 'nowy') {
        // Istniejące okno szybkiego dodania kontrahenta (09_quickadd.js) wpisze nowego do pola.
        currentQuickAddSelect = { id: 'tx-contractor' };
        szybkiWpis.reczne.add('kontrahent');
        openQuickContractorModal(s.nowaNazwa);
        return;
    }
    if (s.typ === 'konto') {
        // Konto trafia do pola, a znacznik znika z tekstu — nazwy kont bywają wielowyrazowe
        // i niejednoznaczne, więc tekst nie musi ich odtwarzać (decyzja T6).
        q.value = q.value.slice(0, q.value.length - s.fragment.length).replace(/\s+$/, '');
        q.value += q.value ? ' ' : '';
        if (s.znacznik === '@') {
            pole('konto').value = s.konto.id;
            pole('konto').dispatchEvent(new Event('change'));
            szybkiWpis.reczne.add('konto');
        } else {
            ustawKategorieWpisu(pierwszaKategoriaPrzelewu()?.name);
            szybkiWpis.reczne.add('kategoria');
            updateDestAccountOptions();
            pole('docelowe').value = s.konto.id;
            szybkiWpis.reczne.add('docelowe');
        }
    } else {
        q.value = q.value.slice(0, q.value.length - szybkiWpis.wpis.nazwa.length) + s.nazwa + ' ';
    }
    szybkiWpis.wybrana = 0;
    szybkiWpis.strzalkami = false;
    odswiezSzybkiWpis();
    q.focus();
}

// Linia nad „Zapisz": co zostanie zapisane albo czego brakuje. Liczona z pól, więc
// uwzględnia ręczne poprawki.
function podsumujWpis() {
    const el = document.getElementById('tx-quick-summary');
    const q = document.getElementById('tx-desc');
    if (!el) return;
    if (!q.value.trim() && !szybkiWpis.reczne.size) {
        const przyklad = przykladyWpisu()[szybkiWpis.przyklad % przykladyWpisu().length];
        el.className = 'text-sm text-slate-500 flex-1 min-w-[16rem]';
        el.textContent = przyklad ? `Przykład: „${przyklad}” → ${opisWpisu(rozlozWpis(przyklad))}` : '';
        return;
    }
    const kwota = parseFloat(pole('kwota').value);
    const kat = categories.find(c => c.name === pole('kategoria').value);
    const brak = [];
    if (!(kwota > 0)) brak.push('kwoty');
    if (!kat) brak.push('kategorii');
    if (kat && kat.type === 'transfer') {
        if (!pole('docelowe').value) brak.push('konta docelowego');
        else if (pole('docelowe').value === pole('konto').value) brak.push('innego konta docelowego niż źródłowe');
    }
    if (brak.length) {
        el.className = 'text-sm text-rose-600 flex-1 min-w-[16rem]';
        el.textContent = `Brakuje: ${brak.join(', ')}.`;
        return;
    }
    const konto = accounts.find(a => a.id == pole('konto').value);
    const docelowe = kat.type === 'transfer' ? accounts.find(a => a.id == pole('docelowe').value) : null;
    const znak = kat.type === 'income' ? '+' : '−';
    const kontrahent = kat.type === 'transfer' ? '' : (pole('kontrahent').value ? ` · ${pole('kontrahent').value}` : ' · bez kontrahenta');
    el.className = 'text-sm text-slate-600 flex-1 min-w-[16rem]';
    el.textContent = `Zapisze: ${znak}${formatKwota(kwota)} PLN${kontrahent} · ${kat.name} · ${konto ? konto.name : '—'}${docelowe ? ' → ' + docelowe.name : ''} · ${pole('data').value}`;
}

function opisWpisu(wpis) {
    const kat = categories.find(c => c.name === wpis.kategoria);
    const czesci = [];
    if (wpis.kwota != null) czesci.push(`${kat && kat.type === 'income' ? '+' : '−'}${formatKwota(wpis.kwota)} PLN`);
    if (wpis.kontrahent) czesci.push(wpis.kontrahent.name);
    if (wpis.kategoria) czesci.push(wpis.kategoria);
    if (wpis.docelowe) czesci.push(`→ ${wpis.docelowe.name}`);
    if (wpis.konto) czesci.push(wpis.konto.name);
    czesci.push(!wpis.data ? 'dziś (domyślnie)' : wpis.data);
    return czesci.join(' · ');
}

// Przykłady w pustym polu, z danych użytkownika (nazwy, które naprawdę rozpozna).
function przykladyWpisu() {
    const [k1, k2] = najczestsiKontrahenci();
    const kat = kategorieWpisu().find(c => c.type === 'expense');
    const piecDniTemu = new Date(); piecDniTemu.setDate(piecDniTemu.getDate() - 5);
    const docelowe = accounts.find(a => a.id != preferredFormAccountId());
    return [
        `${k1 ? k1.name : 'Biedronka'} 85,60 wczoraj`,
        kat ? `${kat.name} 235,6` : null,
        k2 ? `${k2.name} 43 ${piecDniTemu.getDate()}.${piecDniTemu.getMonth() + 1}` : null,
        docelowe && kontoPoFragmencie(docelowe.name.split(/\s+/).pop()) ? `>${docelowe.name.split(/\s+/).pop().toLowerCase()} 500` : null,
    ].filter(Boolean);
}

function rysujNajczestszych() {
    const el = document.getElementById('tx-quick-chips');
    if (!el) return;
    const lista = najczestsiKontrahenci();
    el.classList.toggle('hidden', !lista.length);
    el.replaceChildren(...(lista.length ? [Object.assign(document.createElement('span'), { textContent: 'Najczęstsze:' })] : []),
        ...lista.map(c => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'px-2.5 py-1 rounded-full border border-slate-300 bg-white text-slate-700 hover:border-blue-400 hover:bg-blue-50';
            b.textContent = c.name;
            b.addEventListener('click', () => {
                const q = document.getElementById('tx-desc');
                q.value = c.name + ' ';
                odswiezSzybkiWpis();
                q.focus();
            });
            return b;
        }));
}

// Po zapisie (11_transactions.js): czyste pole na kolejny wpis; data i konto wracają do
// „dziś" i konta domyślnego, chyba że zaznaczono „Zachowaj" (decyzja T7).
function poZapisieSzybkiegoWpisu() {
    const zachowaj = document.getElementById('tx-quick-sticky')?.checked;
    // Panel na telefonie zamyka się po zapisie; z „Zachowaj" zostaje na kolejny paragon.
    if (panelWpisuOtwarty() && !zachowaj) zamknijPanelWpisu();
    szybkiWpis.zachowanaData = zachowaj ? pole('data').value : null;
    szybkiWpis.zachowaneKonto = zachowaj ? Number(pole('konto').value) : null;
    szybkiWpis.reczne.clear();
    szybkiWpis.wybrana = 0;
    szybkiWpis.strzalkami = false;
    const q = document.getElementById('tx-desc');
    q.value = '';
    pole('kwota').value = '';
    document.getElementById('tx-contractor').value = '';
    pole('kontrahent').value = '';
    ustawKategorieWpisu('');
    pole('docelowe').value = '';
    pole('data').value = szybkiWpis.zachowanaData || toLocalISODate(new Date());
    const konto = szybkiWpis.zachowaneKonto || preferredFormAccountId();
    if (konto) pole('konto').value = konto;
    wypelnijPolaWpisu(rozlozWpis(''));
    rysujPodpowiedziWpisu(rozlozWpis(''));
    podsumujWpis();
    q.focus();
}

function initSzybkiWpis() {
    initPanelWpisu();
    const q = document.getElementById('tx-desc');
    if (!q) return;

    q.addEventListener('input', () => { szybkiWpis.wybrana = 0; szybkiWpis.strzalkami = false; odswiezSzybkiWpis(); });
    q.addEventListener('focus', () => rysujPodpowiedziWpisu(szybkiWpis.wpis || rozlozWpis(q.value)));
    q.addEventListener('blur', () => document.getElementById('tx-quick-sugg').classList.add('hidden'));
    q.addEventListener('keydown', e => {
        const ile = szybkiWpis.sugestie.length;
        if (!ile) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            szybkiWpis.wybrana = (szybkiWpis.wybrana + (e.key === 'ArrowDown' ? 1 : ile - 1)) % ile;
            szybkiWpis.strzalkami = true;
            odswiezSzybkiWpis();
        } else if ((e.key === 'Tab' && !e.shiftKey) || (e.key === 'Enter' && szybkiWpis.strzalkami)) {
            // Tab dokańcza podpowiedź; Enter robi to samo tylko po świadomym wyborze strzałkami,
            // inaczej zapisuje formularz.
            e.preventDefault();
            wybierzPodpowiedzWpisu(szybkiWpis.wybrana);
        } else if (e.key === 'Escape') {
            szybkiWpis.sugestie = [];
            document.getElementById('tx-quick-sugg').classList.add('hidden');
        }
    });

    // Ręczna zmiana pola wygrywa z rozpoznaniem. Tylko zdarzenia od użytkownika (isTrusted) —
    // pola ustawiane z kodu też wysyłają „change".
    Object.entries(POLA_WPISU).forEach(([klucz, id]) => {
        const el = document.getElementById(id);
        if (!el) return;
        const oznacz = e => { if (e.isTrusted) { szybkiWpis.reczne.add(klucz); podsumujWpis(); wypelnijPolaWpisu(szybkiWpis.wpis || rozlozWpis(q.value)); } };
        el.addEventListener('input', oznacz);
        el.addEventListener('change', oznacz);
    });
    document.getElementById('tx-contractor-dropdown')?.addEventListener('mousedown', e => {
        if (e.isTrusted) szybkiWpis.reczne.add('kontrahent');
        setTimeout(podsumujWpis);
    });
    document.getElementById('tx-comment')?.addEventListener('input', podsumujWpis);

    // Pasek skrótów tylko na urządzeniu dotykowym: znaki @ i > są tam na drugim ekranie klawiatury.
    const skroty = document.getElementById('tx-quick-tokens');
    if (skroty && ekranDotykowy()) {
        skroty.classList.remove('hidden');
        skroty.classList.add('flex');
        skroty.querySelectorAll('[data-znacznik]').forEach(b => {
            b.addEventListener('mousedown', e => e.preventDefault());  // nie zabieraj fokusu polu
            b.addEventListener('click', () => {
                q.value += (q.value && !/\s$/.test(q.value) ? ' ' : '') + b.dataset.znacznik;
                q.focus();
                szybkiWpis.wybrana = 0;
                odswiezSzybkiWpis();
            });
        });
    }

    // Rotujące przykłady w pustym polu.
    setInterval(() => {
        const przyklady = przykladyWpisu();
        if (!przyklady.length) return;
        szybkiWpis.przyklad = (szybkiWpis.przyklad + 1) % przyklady.length;
        q.placeholder = `np. ${przyklady[szybkiWpis.przyklad]}`;
        if (!q.value) podsumujWpis();
    }, 3500);
}

// Odświeżenie danych (nowi kontrahenci, kategorie) — wołane z fetchInitialData.
function odswiezDaneSzybkiegoWpisu() {
    odswiezPrzyciskWpisu();
    if (otworzWpisPoZaladowaniu) { otworzWpisPoZaladowaniu = false; otworzWpis(); }
    rysujNajczestszych();
    const przyklady = przykladyWpisu();
    const q = document.getElementById('tx-desc');
    if (q && przyklady.length) q.placeholder = `np. ${przyklady[szybkiWpis.przyklad % przyklady.length]}`;
    podsumujWpis();
}

// --- Szybki wpis z każdej zakładki (telefon) ---
// Przycisk „+" otwiera od dołu panel z TYM SAMYM formularzem, przeniesionym z zakładki
// Transakcje (bez drugiej kopii id). Tylko na urządzeniu dotykowym i nie na zakładce
// Transakcje, gdzie formularz i tak stoi na górze.
let otworzWpisPoZaladowaniu = false;  // skrót /login?dodaj=1 — panel po wczytaniu danych
let miejsceFormularzaWpisu = null;

const panelWpisuOtwarty = () => !document.getElementById('tx-sheet')?.classList.contains('hidden');

function odswiezPrzyciskWpisu(zakladka) {
    const fab = document.getElementById('tx-fab');
    if (!fab) return;
    const aktywna = zakladka || (['dashboard', 'transactions', 'summary', 'budget', 'categories', 'staging', 'reports']
        .find(n => !document.getElementById(`tab-${n}`)?.classList.contains('tab-hidden')));
    fab.classList.toggle('hidden', !ekranDotykowy() || aktywna === 'transactions' || !accounts.length);
}

function otworzPanelWpisu() {
    const karta = document.getElementById('tx-form-card');
    if (!karta || panelWpisuOtwarty()) return;
    miejsceFormularzaWpisu = document.createComment('miejsce formularza transakcji');
    karta.before(miejsceFormularzaWpisu);
    document.getElementById('tx-sheet-body').append(karta);
    document.getElementById('tx-sheet').classList.remove('hidden');
    document.getElementById('tx-sheet-tlo').classList.remove('hidden');
    document.getElementById('tx-desc').focus();
}

function zamknijPanelWpisu() {
    if (!panelWpisuOtwarty()) return;
    miejsceFormularzaWpisu.after(document.getElementById('tx-form-card'));
    miejsceFormularzaWpisu.remove();
    document.getElementById('tx-sheet').classList.add('hidden');
    document.getElementById('tx-sheet-tlo').classList.add('hidden');
    document.getElementById('tx-fab')?.focus();
}

// Skrót z ekranu telefonu: panel; na komputerze — zakładka Transakcje z kursorem w polu.
function otworzWpis() {
    if (ekranDotykowy()) {
        otworzPanelWpisu();
    } else {
        switchTab('transactions');
        document.getElementById('tx-desc')?.focus();
    }
}

function zadajOtwarciaWpisu() {
    otworzWpisPoZaladowaniu = true;
}

function initPanelWpisu() {
    document.getElementById('tx-fab')?.addEventListener('click', otworzPanelWpisu);
    document.getElementById('tx-sheet-tlo')?.addEventListener('click', zamknijPanelWpisu);
    document.getElementById('tx-sheet-zamknij')?.addEventListener('click', zamknijPanelWpisu);
    const panel = document.getElementById('tx-sheet');
    panel?.addEventListener('keydown', e => {
        // Pierwszy Esc zamyka listę podpowiedzi (obsługuje ją pole), dopiero kolejny panel.
        if (e.key === 'Escape' && document.getElementById('tx-quick-sugg').classList.contains('hidden')) {
            zamknijPanelWpisu();
            return;
        }
        // Fokus zostaje w panelu, dopóki jest otwarty (okno dialogowe).
        if (e.key !== 'Tab' || e.defaultPrevented) return;
        const fokusowalne = [...panel.querySelectorAll('button, input, select, textarea')].filter(el => !el.disabled && el.getClientRects().length);
        const [pierwszy, ostatni] = [fokusowalne[0], fokusowalne[fokusowalne.length - 1]];
        if (e.shiftKey && document.activeElement === pierwszy) { e.preventDefault(); ostatni.focus(); }
        else if (!e.shiftKey && document.activeElement === ostatni) { e.preventDefault(); pierwszy.focus(); }
    });
}
