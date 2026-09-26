// Kalkulator kredytu — publiczna strona /kalkulator-kredytu (bez logowania).
// Liczy wylacznie w przegladarce: nic, co uzytkownik wpisze, nie trafia na serwer.
//
// Odsetki za miesiac = saldo * stopa roczna / 12, zaokraglane do grosza — tak liczy
// bank (sprawdzone na harmonogramie hipoteki z Pekao, patrz testy). Nie jest to
// modul SPA (brak prefiksu liczbowego) — base.html go nie laduje.

function zaokr(x) {
    return Math.round((x + Number.EPSILON) * 100) / 100;
}

function rataRowna(saldo, miesiace, i) {
    if (i === 0) return zaokr(saldo / miesiace);
    return zaokr(saldo * i / (1 - Math.pow(1 + i, -miesiace)));
}

/**
 * Plan splaty. trybNadplaty: 'okres' — rata zostaje, kredyt sie skraca;
 * 'rata' — okres zostaje, rata jest przeliczana na pozostale miesiace.
 */
function harmonogram({ kwota, miesiace, oprocentowanie, rodzaj = 'rowne', nadplataMiesieczna = 0,
                       nadplatyJednorazowe = [], trybNadplaty = 'okres' }) {
    const i = oprocentowanie / 100 / 12;
    let saldo = zaokr(kwota);
    let rata = rataRowna(saldo, miesiace, i);
    let czescKapitalowa = zaokr(saldo / miesiace);
    const raty = [];
    let sumaOdsetek = 0, sumaNadplat = 0;

    for (let nr = 1; nr <= miesiace && saldo > 0; nr++) {
        const odsetki = zaokr(saldo * i);
        let kapital = rodzaj === 'malejace' ? czescKapitalowa : zaokr(rata - odsetki);
        // Ostatnia rata domyka saldo — zaokraglenia rat nie zostawiaja groszy.
        if (nr === miesiace || kapital > saldo) kapital = saldo;
        saldo = zaokr(saldo - kapital);

        const zaplanowana = nadplatyJednorazowe
            .filter(n => n.miesiac === nr)
            .reduce((s, n) => s + n.kwota, nadplataMiesieczna);
        const nadplata = zaokr(Math.min(saldo, zaplanowana));
        saldo = zaokr(saldo - nadplata);

        raty.push({ nr, rata: zaokr(odsetki + kapital), odsetki, kapital, nadplata, saldo });
        sumaOdsetek += odsetki;
        sumaNadplat += nadplata;

        if (nadplata > 0 && trybNadplaty === 'rata' && saldo > 0) {
            rata = rataRowna(saldo, miesiace - nr, i);
            czescKapitalowa = zaokr(saldo / (miesiace - nr));
        }
    }
    return { raty, sumaOdsetek: zaokr(sumaOdsetek), sumaNadplat: zaokr(sumaNadplat) };
}

/**
 * RRSO w % — stopa X, przy ktorej wyplacona kwota rowna sie zdyskontowanym
 * platnosciom (miesiac t w chwili t/12 roku). Bisekcja: wartosc bieżąca maleje z X.
 */
function rrso(wyplacono, platnosci) {
    const npv = x => platnosci.reduce((s, p, t) => s + p / Math.pow(1 + x, (t + 1) / 12), -wyplacono);
    let lo = -0.99, hi = 10;
    for (let k = 0; k < 200; k++) {
        const mid = (lo + hi) / 2;
        if (npv(mid) > 0) lo = mid; else hi = mid;
    }
    return zaokr(lo * 100);
}

/** Wszystko, co pokazuje strona: plan, koszty, RRSO i test wzrostu stop. */
function policzKredyt(p) {
    const { kwota, prowizjaProcent = 0, prowizjaKwota = 0, prowizjaKredytowana = false, oplataMiesieczna = 0 } = p;
    const prowizja = zaokr(kwota * prowizjaProcent / 100 + prowizjaKwota);
    const doSplaty = { ...p, kwota: prowizjaKredytowana ? kwota + prowizja : kwota };
    const bezNadplat = { ...doSplaty, nadplataMiesieczna: 0, nadplatyJednorazowe: [] };

    const plan = harmonogram(doSplaty);
    const bazowy = harmonogram(bezNadplat);
    const wyplacono = prowizjaKredytowana ? kwota : kwota - prowizja;

    return {
        plan,
        bazowy,
        prowizja,
        // Suma rat i nadpłat: kapitał (z prowizją, jeśli kredytowana) + odsetki.
        doOddania: zaokr(doSplaty.kwota + plan.sumaOdsetek),
        sumaOplat: zaokr(oplataMiesieczna * plan.raty.length),
        kosztCalkowity: zaokr(plan.sumaOdsetek + prowizja + oplataMiesieczna * plan.raty.length),
        // Jak w ofertach banku: RRSO z planu bez nadplat.
        rrso: rrso(wyplacono, bazowy.raty.map(r => r.rata + oplataMiesieczna)),
        testStop: [1, 2, 3].map(d => {
            const h = harmonogram({ ...bezNadplat, oprocentowanie: zaokr(p.oprocentowanie + d) });
            return { oprocentowanie: zaokr(p.oprocentowanie + d), rata: h.raty[0].rata, sumaOdsetek: h.sumaOdsetek };
        }),
    };
}

// --- Strona ---------------------------------------------------------------

const zl = x => x.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' zł';

/** 1 rok / 2 lata / 5 lat — polska liczba mnoga zależy od końcówki liczby. */
function odmiana(n, [jeden, kilka, wiele]) {
    if (n === 1) return `${n} ${jeden}`;
    const kilkaKoncowka = n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14);
    return `${n} ${kilkaKoncowka ? kilka : wiele}`;
}

function okresSlownie(miesiace) {
    const lata = Math.floor(miesiace / 12), m = miesiace % 12;
    return [lata && odmiana(lata, ['rok', 'lata', 'lat']), (m || !lata) && odmiana(m, ['miesiąc', 'miesiące', 'miesięcy'])]
        .filter(Boolean).join(' ');
}

/** Miesiąc raty nr N przy pierwszej racie w `pierwsza` ('RRRR-MM') → 'MM.RRRR'. */
function miesiacRaty(pierwsza, nr) {
    const [rok, mies] = pierwsza.split('-').map(Number);
    const indeks = rok * 12 + (mies - 1) + (nr - 1);
    return `${String(indeks % 12 + 1).padStart(2, '0')}.${Math.floor(indeks / 12)}`;
}

function czytajFormularz() {
    const liczba = id => parseFloat(String(document.getElementById(id).value).replace(',', '.')) || 0;
    const nadplatyJednorazowe = [...document.querySelectorAll('#kk-nadplaty .kk-nadplata')]
        .map(w => ({ miesiac: parseInt(w.querySelector('[name=miesiac]').value, 10), kwota: parseFloat(w.querySelector('[name=kwota]').value) || 0 }))
        .filter(n => n.miesiac > 0 && n.kwota > 0);
    return {
        kwota: liczba('kk-kwota'),
        miesiace: Math.round(liczba('kk-lata') * 12),
        oprocentowanie: liczba('kk-oprocentowanie'),
        rodzaj: document.querySelector('input[name=kk-rodzaj]:checked').value,
        prowizjaProcent: liczba('kk-prowizja-procent'),
        prowizjaKwota: liczba('kk-prowizja-kwota'),
        prowizjaKredytowana: document.getElementById('kk-prowizja-kredytowana').checked,
        oplataMiesieczna: liczba('kk-oplata'),
        nadplataMiesieczna: liczba('kk-nadplata-miesieczna'),
        nadplatyJednorazowe,
        trybNadplaty: document.querySelector('input[name=kk-tryb]:checked').value,
    };
}

function ustawTekst(id, tekst) {
    document.getElementById(id).textContent = tekst;
}

function renderKalkulator() {
    const p = czytajFormularz();
    const wynik = document.getElementById('kk-wynik');
    if (!(p.kwota > 0 && p.miesiace > 0 && p.oprocentowanie >= 0)) {
        wynik.hidden = true;
        return;
    }
    wynik.hidden = false;
    const w = policzKredyt(p);
    const raty = w.plan.raty;
    const pierwsza = document.getElementById('kk-start').value;
    const miesiac = nr => pierwsza ? miesiacRaty(pierwsza, nr) : '—';

    ustawTekst('kk-rata', p.rodzaj === 'malejace'
        ? `${zl(raty[0].rata)} → ${zl(raty.at(-1).rata)}` : zl(raty[0].rata));
    ustawTekst('kk-liczba-rat', `${raty.length} (${okresSlownie(raty.length)}), ostatnia rata ${miesiac(raty.length)}`);
    ustawTekst('kk-odsetki', zl(w.plan.sumaOdsetek));
    ustawTekst('kk-do-oddania', zl(w.doOddania));
    ustawTekst('kk-prowizja', zl(w.prowizja));
    ustawTekst('kk-oplaty', zl(w.sumaOplat));
    ustawTekst('kk-koszt', zl(w.kosztCalkowity));
    ustawTekst('kk-rrso', w.rrso.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + '%');

    const efekt = document.getElementById('kk-efekt-nadplat');
    efekt.hidden = w.plan.sumaNadplat === 0;
    efekt.textContent = `Nadpłaty (${zl(w.plan.sumaNadplat)}) oszczędzają ${zl(zaokr(w.bazowy.sumaOdsetek - w.plan.sumaOdsetek))} odsetek`
        + (w.bazowy.raty.length > raty.length ? ` i skracają kredyt o ${okresSlownie(w.bazowy.raty.length - raty.length)}.` : '.');

    document.getElementById('kk-test-stop').innerHTML = w.testStop.map(t => `<tr>
        <td>${t.oprocentowanie.toLocaleString('pl-PL')}%</td><td>${zl(t.rata)}</td>
        <td>${zl(zaokr(t.rata - w.bazowy.raty[0].rata))}</td><td>${zl(t.sumaOdsetek)}</td></tr>`).join('');

    document.getElementById('kk-harmonogram').innerHTML = raty.map(r => `<tr>
        <td>${r.nr}</td><td>${miesiac(r.nr)}</td><td>${zl(r.rata)}</td><td>${zl(r.kapital)}</td><td>${zl(r.odsetki)}</td>
        <td>${r.nadplata ? zl(r.nadplata) : '—'}</td><td>${zl(r.saldo)}</td></tr>`).join('');
}

function dodajNadplate() {
    const wiersz = document.getElementById('kk-nadplata-wzor').content.firstElementChild.cloneNode(true);
    wiersz.querySelector('button').addEventListener('click', () => { wiersz.remove(); renderKalkulator(); });
    document.getElementById('kk-nadplaty').appendChild(wiersz);
}

if (typeof document !== 'undefined' && document.getElementById('kk-form')) {
    // Domyślnie pierwsza rata w przyszłym miesiącu.
    const d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() + 1);
    const start = document.getElementById('kk-start');
    if (!start.value) start.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    document.getElementById('kk-form').addEventListener('input', renderKalkulator);
    document.getElementById('kk-dodaj-nadplate').addEventListener('click', dodajNadplate);
    renderKalkulator();
}
