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
    zaladujModuly('01_state.js', '13_dashboard.js');
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
