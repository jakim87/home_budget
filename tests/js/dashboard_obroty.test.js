// Przychody i wydatki wg kategorii na Dashboardzie oraz przejscie „Szczegolowy raport".
//
// Slupek miesiaca na Dashboardzie musi sie zgadzac z tym, co pokaze widok we Wnioskach po
// przejsciu z niego — inaczej uzytkownik dostaje dwie rozne liczby za ten sam miesiac.
// Dlatego test liczy oba miejsca na tych samych danych i porownuje wyniki.

import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { htmlWnioskow, tx, zaladujModuly } from './helpers.js';

beforeAll(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 4, 10));
    zaladujModuly('01_state.js', '04_helpers.js', '13_dashboard.js', '22_wnioski_reguly.js', '23_wnioski.js');
    // switchTab z 06_tabs.js przelacza zakladki w DOM; tu wystarczy, ze narysuje Wnioski.
    globalThis.switchTab = (nazwa) => { if (nazwa === 'wnioski') renderWnioski(); };
});
afterAll(() => vi.useRealTimers());

beforeEach(() => {
    document.body.innerHTML = htmlWnioskow();
    accounts = [{ id: 1, name: 'ROR', currency: 'PLN' }, { id: 2, name: 'Oszczednosci', currency: 'PLN' }, { id: 3, name: 'Konto EUR', currency: 'EUR' }];
    inactiveAccounts = [];
    contractors = [];
    savedViews = [];
    currencies = { EUR: { rate: 4.3, date: '2026-05-08' } };
    monthlyRates = { EUR: { '2026-03': 4.25 } };
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
        tx({ id: 9, date: '2026-03-22', amount: -10, category: 'Zakupy', account_id: 3 }),
    ];
});

// Widok, który otwiera „Szczegółowy raport”, i jego sumy.
const wnioskiZaMarzec = () => {
    pokazRaportMiesiaca('2026-03');
    return wnSumy(wnFiltruj(wnCfg, wnZakres(wnCfg)));
};

describe('obrotyMiesieczne', () => {
    it('bez wybranych kategorii: bez przelewow i kategorii systemowych, po znaku kwoty, w PLN', () => {
        const marzec = obrotyMiesieczne(transactions, new Set())['2026-03'];
        expect(marzec.przychody).toBe(5000);
        expect(marzec.wydatki).toBeCloseTo(120 + 240 + 15 + 10 * 4.25);
    });

    it('z wybranymi kategoriami liczy tylko je (bez transakcji z kategoria spoza slownika)', () => {
        const marzec = obrotyMiesieczne(transactions, new Set([2]))['2026-03'];
        expect(marzec.wydatki).toBe(240);
        expect(marzec.przychody).toBe(0);
    });

    it('konto bez kursu wypada z sumy, zamiast liczyc sie jak PLN', () => {
        monthlyRates = {};
        currencies = {};
        expect(obrotyMiesieczne(transactions, new Set())['2026-03'].wydatki).toBeCloseTo(120 + 240 + 15);
    });
});

describe('Szczegolowy raport z Dashboardu otwiera Wnioski', () => {
    it('bez wybranych kategorii pokazuje te same sumy co slupek Dashboardu', () => {
        const dashboard = obrotyMiesieczne(transactions, new Set())['2026-03'];
        const widok = wnioskiZaMarzec();
        expect(widok.inc).toBeCloseTo(dashboard.przychody);
        expect(widok.exp).toBeCloseTo(dashboard.wydatki);
    });

    it('z wybranymi kategoriami tez sie zgadza', () => {
        dashKategorie.clear(); dashKategorie.add(1); dashKategorie.add(3);
        const dashboard = obrotyMiesieczne(transactions, dashKategorie)['2026-03'];
        const widok = wnioskiZaMarzec();
        expect(wnCfg.kategorie).toEqual([1, 3]);
        expect(widok.inc).toBeCloseTo(dashboard.przychody);
        expect(widok.exp).toBeCloseTo(dashboard.wydatki);
        dashKategorie.clear();
    });

    it('ustawia wybrany miesiac jako niezapisany widok jednego miesiaca', () => {
        wnioskiZaMarzec();
        expect(wnYm).toBe('2026-03');
        expect(wnCfg.okres).toEqual({ typ: 'miesiac' });
        expect(wnAktywnyId).toBeNull();
        expect(document.getElementById('wn-kpi').textContent).toContain('5 000 zł');
    });
});

describe('przycisk „Szczegółowy raport”', () => {
    const przyciski = ym => {
        document.body.innerHTML = '<div class="dashboard-wybor"></div>';
        dashWybranyMiesiac = ym;
        renderWyborMiesiaca();
        return document.querySelector('.dashboard-wybor').textContent;
    };

    it('jest przy miesiącu bieżącym i przeszłym', () => {
        expect(przyciski('2026-03')).toContain('Szczegółowy raport');
        expect(przyciski('2026-05')).toContain('Szczegółowy raport');
    });

    it('znika przy miesiącu z przyszłości — Wnioski go nie liczą i pokazałyby inny miesiąc', () => {
        expect(przyciski('2026-06')).not.toContain('Szczegółowy raport');
        expect(przyciski('2026-06')).toContain('Pokaż transakcje');
    });
});
