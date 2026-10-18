// Przychody i wydatki wg kategorii na Dashboardzie oraz przejscie „Szczegolowy raport".
//
// Slupek miesiaca na Dashboardzie musi sie zgadzac z tym, co pokaze zakladka Raporty po
// przejsciu z niego — inaczej uzytkownik dostaje dwie rozne liczby za ten sam miesiac.
// Dlatego test liczy oba widoki na tych samych danych i porownuje wyniki.

import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { tx, zaladujModuly } from './helpers.js';

beforeAll(() => {
    zaladujModuly('01_state.js', '04_helpers.js', '13_dashboard.js', '16_reports.js');
    globalThis.renderRptBarChart = () => {};
    globalThis.renderRptLineChart = () => {};
    globalThis.renderRptTable = () => {};
    globalThis.renderBudget = () => {};
    // switchTab z 06_tabs.js przelacza zakladki w DOM; tu wystarczy, ze przeliczy raport.
    globalThis.switchTab = (nazwa) => { if (nazwa === 'reports') renderReports(); };
});

beforeEach(() => {
    document.body.innerHTML = `
        <input id="rpt-date-from"><input id="rpt-date-to">
        <input type="checkbox" id="rpt-exclude-transfers">
        <span id="rpt-accounts-badge"></span><span id="rpt-categories-badge"></span><span id="rpt-contractors-badge"></span>
        <span id="rpt-kpi-income"></span><span id="rpt-kpi-income-count"></span>
        <span id="rpt-kpi-expense"></span><span id="rpt-kpi-expense-count"></span>
        <span id="rpt-kpi-net"></span><span id="rpt-kpi-transfers"></span><span id="rpt-kpi-transfers-count"></span>
        <div id="rpt-accounts-list"></div><div id="rpt-categories-list"></div><div id="rpt-contractors-list"></div>
    `;
    rptInitialized = false;
    accounts = [{ id: 1, name: 'ROR' }, { id: 2, name: 'Oszczednosci' }];
    contractors = [];
    categories = [
        { id: 1, name: 'Zakupy', type: 'expense' },
        { id: 2, name: 'Paliwo', type: 'expense' },
        { id: 3, name: 'Wyplata', type: 'income' },
        { id: 4, name: 'Przelew wlasny', type: 'transfer' },
        { id: 5, name: 'Korekta salda', type: 'system_reconciliation', is_system_category: true },
    ];
    transactions = [
        tx({ id: 1, date: '2026-03-02', amount: -120, category: 'Zakupy' }),
        tx({ id: 2, date: '2026-03-05', amount: -240, category: 'Paliwo' }),
        tx({ id: 3, date: '2026-03-10', amount: 5000, category: 'Wyplata' }),
        tx({ id: 4, date: '2026-03-11', amount: -1000, category: 'Przelew wlasny' }),
        tx({ id: 5, date: '2026-03-11', amount: 1000, category: 'Przelew wlasny', account_id: 2 }),
        tx({ id: 6, date: '2026-03-20', amount: 37, category: 'Korekta salda' }),
        tx({ id: 7, date: '2026-03-21', amount: -15, category: 'Kategoria usunieta' }),
        tx({ id: 8, date: '2026-04-01', amount: -60, category: 'Zakupy' }),
    ];
});

const raportZaMarzec = (kategorieIds) => {
    rptPokazOkres('2026-03-01', '2026-03-31', kategorieIds);
    return rptGroupByMonth(rptFilteredTxs)['2026-03'];
};

describe('obrotyMiesieczne', () => {
    it('bez wybranych kategorii: bez przelewow i kategorii systemowych, po znaku kwoty', () => {
        const marzec = obrotyMiesieczne(transactions, new Set())['2026-03'];
        expect(marzec).toEqual({ przychody: 5000, wydatki: 120 + 240 + 15 });
    });

    it('z wybranymi kategoriami liczy tylko je', () => {
        const marzec = obrotyMiesieczne(transactions, new Set([2]))['2026-03'];
        expect(marzec.wydatki).toBe(240 + 15);  // jak Raporty: transakcja z kategoria spoza slownika przechodzi filtr
        expect(marzec.przychody).toBe(0);
    });
});

describe('Szczegolowy raport z Dashboardu', () => {
    it('bez wybranych kategorii pokazuje te same sumy co slupek Dashboardu', () => {
        const dashboard = obrotyMiesieczne(transactions, new Set())['2026-03'];
        const raport = raportZaMarzec([]);
        expect(raport.income).toBeCloseTo(dashboard.przychody);
        expect(raport.expense).toBeCloseTo(dashboard.wydatki);
    });

    it('z wybranymi kategoriami tez sie zgadza', () => {
        const dashboard = obrotyMiesieczne(transactions, new Set([1, 3]))['2026-03'];
        const raport = raportZaMarzec([1, 3]);
        expect(raport.income).toBeCloseTo(dashboard.przychody);
        expect(raport.expense).toBeCloseTo(dashboard.wydatki);
    });

    it('ustawia zakres dat na caly miesiac i nie nadpisuje go presetem przy pierwszym otwarciu', () => {
        raportZaMarzec([]);
        expect(document.getElementById('rpt-date-from').value).toBe('2026-03-01');
        expect(document.getElementById('rpt-date-to').value).toBe('2026-03-31');
        expect(rptFilteredTxs.some(t => t.date === '2026-04-01')).toBe(false);
    });
});
