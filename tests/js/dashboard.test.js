// Testy liczenia serii Net Worth na dashboardzie.
//
// Dlaczego akurat to: `computeNetWorthSeries()` jest jedynym miejscem na
// froncie, ktore liczy narastajaco po miesiacach — a wykres z tej funkcji
// jest tym, na co uzytkownik patrzy, decydujac "czy nas stac". Bledy
// narastajace sa najtrudniejsze do zauwazenia golym okiem, bo wykres
// zawsze wyglada wiarygodnie.

import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { tx, zaladujModuly } from './helpers.js';

beforeAll(() => {
    zaladujModuly('01_state.js', '04_helpers.js', '13_dashboard.js');
});

beforeEach(() => {
    transactions = [];
    accounts = [];
    inactiveAccounts = [];
});

describe('computeNetWorthSeries', () => {
    it('sumuje narastajaco kolejne miesiace', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: 1000 }),
            tx({ id: 2, date: '2026-02-10', amount: -300 }),
            tx({ id: 3, date: '2026-03-10', amount: 500 }),
        ];
        computeNetWorthSeries();

        const wartosci = Object.fromEntries(netWorthSeriesFull.map(p => [p.month, p.value]));
        expect(wartosci['2026-01']).toBe(1000);
        expect(wartosci['2026-02']).toBe(700);   // 1000 - 300
        expect(wartosci['2026-03']).toBe(1200);  // 700 + 500
    });

    it('nie gubi miesiaca bez zadnej transakcji — przenosi poprzednia wartosc', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: 1000 }),
            // luty pusty
            tx({ id: 2, date: '2026-03-10', amount: 200 }),
        ];
        computeNetWorthSeries();

        const miesiace = netWorthSeriesFull.map(p => p.month);
        expect(miesiace).toContain('2026-02');

        const luty = netWorthSeriesFull.find(p => p.month === '2026-02');
        expect(luty.value).toBe(1000);
    });

    it('zalicza transakcje z ostatniego dnia miesiaca do tego miesiaca', () => {
        // Granica miesiaca liczona jest przez new Date(rok, miesiac, 0), wiec
        // luty w roku przestepnym musi miec 29 dni. 2028 jest przestepny.
        transactions = [
            tx({ id: 1, date: '2028-02-29', amount: 400 }),
            tx({ id: 2, date: '2028-03-01', amount: 100 }),
        ];
        computeNetWorthSeries();

        const luty = netWorthSeriesFull.find(p => p.month === '2028-02');
        expect(luty.value).toBe(400);

        const marzec = netWorthSeriesFull.find(p => p.month === '2028-03');
        expect(marzec.value).toBe(500);
    });

    it('obsluguje przelom roku', () => {
        transactions = [
            tx({ id: 1, date: '2025-12-20', amount: 800 }),
            tx({ id: 2, date: '2026-01-05', amount: -200 }),
        ];
        computeNetWorthSeries();

        const miesiace = netWorthSeriesFull.map(p => p.month);
        expect(miesiace).toContain('2025-12');
        expect(miesiace).toContain('2026-01');
        expect(netWorthSeriesFull.find(p => p.month === '2026-01').value).toBe(600);
    });

    it('liczy wszystkie konta — Dashboard nie ma filtra kont', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: 1000, account_id: 1 }),
            tx({ id: 2, date: '2026-01-11', amount: 5000, account_id: 2 }),
        ];
        computeNetWorthSeries();

        expect(netWorthSeriesFull.find(p => p.month === '2026-01').value).toBe(6000);
    });

    it('przy braku transakcji zwraca pusta serie zamiast rzucac bledem', () => {
        transactions = [];
        computeNetWorthSeries();
        expect(netWorthSeriesFull).toEqual([]);
    });

    it('rata kredytu (kwota ujemna) obniza wartosc netto', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: 3000 }),
            tx({ id: 2, date: '2026-01-15', amount: -4500, category: 'Kredyt' }),
        ];
        computeNetWorthSeries();
        expect(netWorthSeriesFull.find(p => p.month === '2026-01').value).toBe(-1500);
    });
});

// Konta walutowe: saldo w walucie konta razy kurs NBP. Kurs bierzemy z konca
// kazdego miesiaca osobno — inaczej historia pokazywalaby dzisiejsza wycene
// dawnych sald i wykres rysowalby zmiany, ktorych nie bylo.
describe('konta walutowe', () => {
    beforeEach(() => {
        inactiveAccounts = [];
        accounts = [
            { id: 1, name: 'PLN', balance: 1000, currency: 'PLN' },
            { id: 2, name: 'Euro', balance: 100, currency: 'EUR' },
        ];
        currencies = { EUR: { name: 'euro', rate: 4.4, date: '2026-03-27' } };
        monthlyRates = { EUR: { '2026-01': 4.2, '2026-02': 4.3, '2026-03': 4.4 } };
    });

    it('Net Worth przelicza saldo EUR po najnowszym kursie', () => {
        const { suma, brak } = sumaSaldPLN(accounts);
        expect(suma).toBeCloseTo(1440);  // 1000 + 100 * 4.4
        expect(brak).toEqual([]);
    });

    it('konto bez kursu wypada z sumy jawnie, nie jako zero po cichu', () => {
        accounts.push({ id: 3, name: 'Lira', balance: 500, currency: 'TRY' });
        const { suma, brak } = sumaSaldPLN(accounts);
        expect(suma).toBeCloseTo(1440);
        expect(brak).toEqual(['TRY']);
    });

    it('wykres wycenia saldo EUR po kursie z konca kazdego miesiaca', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: 1000, account_id: 1 }),
            tx({ id: 2, date: '2026-01-10', amount: 100, account_id: 2 }),
        ];
        computeNetWorthSeries();

        const wartosc = m => netWorthSeriesFull.find(p => p.month === m).value;
        // Saldo EUR sie nie zmienia, a jego wartosc w PLN tak — za kursem.
        expect(wartosc('2026-01')).toBeCloseTo(1420);
        expect(wartosc('2026-02')).toBeCloseTo(1430);
        expect(wartosc('2026-03')).toBeCloseTo(1440);
    });

    it('konto zamkniete tez jest wyceniane w swojej walucie', () => {
        inactiveAccounts = [{ id: 9, name: 'Stare EUR', balance: 0, currency: 'EUR' }];
        transactions = [tx({ id: 1, date: '2026-02-10', amount: 10, account_id: 9 })];
        computeNetWorthSeries();
        expect(netWorthSeriesFull.find(p => p.month === '2026-02').value).toBeCloseTo(43);
    });
});

// Majatek wg typu konta: kazdy punkt serii niesie sumy per typ i liczbe kont,
// ktore do konca miesiaca mialy juz jakas transakcje. Suma typow musi dac
// majatek netto — inaczej wykres warstw i linia rozjada sie po cichu.
describe('majatek wg typu konta', () => {
    beforeEach(() => {
        currencies = { EUR: { name: 'euro', rate: 4.4, date: '2026-03-27' } };
        monthlyRates = { EUR: { '2026-01': 4.2, '2026-02': 4.3, '2026-03': 4.4 } };
        accounts = [
            { id: 1, name: 'Osobiste', balance: 0, currency: 'PLN', account_type: 'ROR' },
            { id: 2, name: 'Oszczednosci', balance: 0, currency: 'PLN', account_type: 'KO' },
            { id: 3, name: 'Karta', balance: 0, currency: 'PLN', account_type: 'Kredyt' },
            { id: 4, name: 'Euro', balance: 0, currency: 'EUR', account_type: 'KO' },
            { id: 5, name: 'Gotowka', balance: 0, currency: 'PLN', account_type: null },
        ];
    });

    it('suma typow w kazdym miesiacu rowna sie majatkowi netto', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-05', amount: 5000, account_id: 1 }),
            tx({ id: 2, date: '2026-01-06', amount: 2000, account_id: 2 }),
            tx({ id: 3, date: '2026-02-10', amount: -800, account_id: 3 }),
            tx({ id: 4, date: '2026-02-11', amount: 100, account_id: 4 }),
            tx({ id: 5, date: '2026-03-01', amount: 300, account_id: 5 }),
        ];
        computeNetWorthSeries();

        for (const p of netWorthSeriesFull) {
            const suma = Object.values(p.typy).reduce((s, v) => s + v, 0);
            expect(suma).toBeCloseTo(p.value);
        }
        const marzec = netWorthSeriesFull.find(p => p.month === '2026-03');
        expect(marzec.typy.ROR).toBe(5000);
        expect(marzec.typy.KO).toBeCloseTo(2000 + 100 * 4.4);  // konto EUR wycenione w swoim typie
        expect(marzec.typy.Kredyt).toBe(-800);
        expect(marzec.typy['Bez typu']).toBe(300);              // konto bez typu ma wlasna grupe
    });

    it('typ konta pojawia sie od miesiaca pierwszej transakcji', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-05', amount: 5000, account_id: 1 }),
            tx({ id: 2, date: '2026-03-10', amount: 700, account_id: 2 }),
        ];
        computeNetWorthSeries();

        const styczen = netWorthSeriesFull.find(p => p.month === '2026-01');
        const marzec = netWorthSeriesFull.find(p => p.month === '2026-03');
        expect(styczen.konta).toEqual({ ROR: 1 });
        expect(marzec.konta).toEqual({ ROR: 1, KO: 1 });
    });
});

describe('zmianyMajatku', () => {
    const seria = [
        { month: '2025-10', value: -2000 },
        { month: '2025-11', value: 1000 },
        { month: '2026-09', value: 40000 },
        { month: '2026-10', value: 44000 },
    ];

    it('porownuje z koncem poprzedniego miesiaca i tego samego miesiaca rok wczesniej', () => {
        const z = zmianyMajatku(seria, 44000, '2026-10');
        expect(z.miesiac).toEqual({ miesiac: '2026-09', wartosc: 40000, zmiana: 4000, procent: 0.1 });
        expect(z.rok.miesiac).toBe('2025-10');
        expect(z.rok.zmiana).toBe(46000);
    });

    it('nie liczy procentu od ujemnej albo zerowej bazy', () => {
        expect(zmianyMajatku(seria, 44000, '2026-10').rok.procent).toBeNull();
    });

    it('bez punktu w historii zwraca null zamiast porownania z zerem', () => {
        const z = zmianyMajatku(seria, 1000, '2025-11');
        expect(z.miesiac.wartosc).toBe(-2000);
        expect(z.rok).toBeNull();
    });

    it('zmiane zaokragla do grosza — brak ruchu to zero, nie -0,00 z bledu zmiennoprzecinkowego', () => {
        const z = zmianyMajatku([{ month: '2026-09', value: 0.1 + 0.2 }], 0.3, '2026-10');
        expect(Object.is(z.miesiac.zmiana, 0)).toBe(true);
    });

    it('obsluguje przelom roku (zmiana miesiac do miesiaca)', () => {
        const z = zmianyMajatku([{ month: '2025-12', value: 10 }], 30, '2026-01');
        expect(z.miesiac.miesiac).toBe('2025-12');
    });
});

// Wlasne pietrzenie warstw: typ z saldem 0 zostaje na swoim miejscu w stosie.
// Wbudowane pietrzenie sprowadzalo go do osi zero — w miesiacu otwarcia
// rachunku maklerskiego jego warstwa przecinala warstwe KO (blad z makiety).
describe('ulozWarstwy', () => {
    const klucze = ['ROR', 'KO', 'Rach. Maklerski', 'Kredyt'];

    it('warstwa o saldzie 0 ma zerowa grubosc na szczycie warstw ponizej', () => {
        const { gora } = ulozWarstwy([{ ROR: 100, KO: 50 }, { ROR: 100, KO: 50, 'Rach. Maklerski': 20 }], klucze);
        expect(gora[2]).toEqual([150, 170]);   // maklerski: przed otwarciem na szczycie KO, potem wyzej
        expect(gora[1]).toEqual([150, 150]);
    });

    it('salda ujemne pietrza sie w dol od zera, niezaleznie od dodatnich', () => {
        const { gora, dol } = ulozWarstwy([{ ROR: 100, Kredyt: -300 }], klucze);
        expect(dol[3]).toEqual([-300]);
        expect(gora[3]).toEqual([100]);        // kredyt nie zmienia stosu dodatniego
        expect(dol[0]).toEqual([0]);
    });

    it('konto biezace z debetem trafia do stosu ujemnego', () => {
        const { gora, dol } = ulozWarstwy([{ ROR: -50, KO: 200, Kredyt: -100 }], klucze);
        expect(gora[1]).toEqual([200]);
        expect(dol[0]).toEqual([-50]);
        expect(dol[3]).toEqual([-150]);
    });
});

describe('strukturaMajatku', () => {
    it('udzial liczy w aktywach; zobowiazania maja udzial ujemny', () => {
        const wiersze = strukturaMajatku({ typy: { ROR: 3000, KO: 7000, Kredyt: -1000 }, konta: { ROR: 2, KO: 1, Kredyt: 1 } });
        const po = Object.fromEntries(wiersze.map(w => [w.typ, w]));
        expect(po.ROR).toEqual({ typ: 'ROR', konta: 2, saldo: 3000, udzial: 0.3 });
        expect(po.KO.udzial).toBe(0.7);
        expect(po.Kredyt.udzial).toBe(-0.1);
        const sumaDodatnich = wiersze.filter(w => w.saldo > 0).reduce((s, w) => s + w.udzial, 0);
        expect(sumaDodatnich).toBeCloseTo(1);
    });

    it('pomija typy bez kont i trzyma kolejnosc legendy', () => {
        const wiersze = strukturaMajatku({ typy: { Kredyt: -10, ROR: 10 }, konta: { Kredyt: 1, ROR: 1 } });
        expect(wiersze.map(w => w.typ)).toEqual(['ROR', 'Kredyt']);
    });
});
