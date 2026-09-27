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
    dashboardAccountIds.clear();
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

    it('uwzglednia filtr kont — transakcje spoza wybranych kont nie licza sie', () => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: 1000, account_id: 1 }),
            tx({ id: 2, date: '2026-01-11', amount: 5000, account_id: 2 }),
        ];
        dashboardAccountIds.add(1);
        computeNetWorthSeries();

        expect(netWorthSeriesFull.find(p => p.month === '2026-01').value).toBe(1000);
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
