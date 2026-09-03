// Testy liczenia w zakladce Raporty.
//
// Raporty licza wszystko po stronie przegladarki z globalnego stanu (patrz
// CLAUDE.md) — backend nie zna tych liczb i nie moze ich sprawdzic. Testy
// backendu, ktorych jest kilkaset, nie dotykaja tej sciezki w ogole.
//
// Najwazniejszy przypadek to wykluczanie przelewow wewnetrznych: bez niego
// kazdy przelew miedzy wlasnymi kontami liczy sie DWA razy (raz jako wyplyw,
// raz jako wplyw), wiec obroty w raporcie sa zawyzone, a wynik netto wyglada
// poprawnie tylko przypadkiem.

import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { tx, zaladujModuly } from './helpers.js';

// Elementy, ktorych dotyka 16_reports.js. Osobny test nizej pilnuje, zeby ta
// lista nie rozjechala sie z base.html.
const ID_KPI = [
    'rpt-kpi-income', 'rpt-kpi-income-count',
    'rpt-kpi-expense', 'rpt-kpi-expense-count',
    'rpt-kpi-net', 'rpt-kpi-transfers', 'rpt-kpi-transfers-count',
];
const ID_FILTROW = [
    'rpt-date-from', 'rpt-date-to', 'rpt-exclude-transfers',
    'rpt-accounts-badge', 'rpt-categories-badge', 'rpt-contractors-badge',
];

function zbudujDom() {
    document.body.innerHTML = `
        <input id="rpt-date-from" value="">
        <input id="rpt-date-to" value="">
        <input type="checkbox" id="rpt-exclude-transfers" checked>
        <span id="rpt-accounts-badge"></span>
        <span id="rpt-categories-badge"></span>
        <span id="rpt-contractors-badge"></span>
        ${ID_KPI.map(id => `<span id="${id}"></span>`).join('')}
        <tbody id="rpt-table-body"></tbody>
        <span id="rpt-table-count"></span>
        <input id="rpt-table-search" value="">
    `;
}

/** Ustawia zakres dat i przelacznik przelewow, po czym przelicza raport. */
function przelicz({ od = '', do: doDaty = '', bezPrzelewow = true } = {}) {
    document.getElementById('rpt-date-from').value = od;
    document.getElementById('rpt-date-to').value = doDaty;
    document.getElementById('rpt-exclude-transfers').checked = bezPrzelewow;
    applyRptFilters();
}

const kpi = id => document.getElementById(id).textContent;

beforeAll(() => {
    zaladujModuly('01_state.js', '16_reports.js');
    // Wykresy i tabela nie sa przedmiotem tych testow — rysowanie wymagaloby
    // Chart.js z CDN i canvasu. Podmieniamy je na puste funkcje, zeby zostac
    // przy tym, co faktycznie sprawdzamy: przy liczbach.
    globalThis.renderRptBarChart = () => {};
    globalThis.renderRptLineChart = () => {};
    globalThis.renderRptTable = () => {};
});

beforeEach(() => {
    zbudujDom();
    transactions = [];
    categories = [
        { id: 1, name: 'Zakupy', type: 'expense' },
        { id: 2, name: 'Wypłata', type: 'income' },
        { id: 3, name: 'Przelew własny', type: 'transfer' },
    ];
    contractors = [];
    accounts = [{ id: 1, name: 'ROR' }, { id: 2, name: 'Oszczędnościowe' }];
});

describe('przelewy wewnetrzne', () => {
    beforeEach(() => {
        transactions = [
            tx({ id: 1, date: '2026-01-05', amount: 5000, category: 'Wypłata' }),
            tx({ id: 2, date: '2026-01-10', amount: -200, category: 'Zakupy' }),
            // Obie nogi tego samego przelewu miedzy wlasnymi kontami:
            tx({ id: 3, date: '2026-01-15', amount: -1000, category: 'Przelew własny', account_id: 1 }),
            tx({ id: 4, date: '2026-01-15', amount: 1000, category: 'Przelew własny', account_id: 2 }),
        ];
    });

    it('domyslnie nie wchodza do przychodow ani wydatkow', () => {
        przelicz({ bezPrzelewow: true });

        expect(kpi('rpt-kpi-income')).toBe('5000,00 PLN');
        expect(kpi('rpt-kpi-expense')).toBe('200,00 PLN');
        expect(kpi('rpt-kpi-net')).toBe('+4800,00 PLN');
    });

    it('sa pokazane osobno, zeby nie znikaly bez sladu', () => {
        przelicz({ bezPrzelewow: true });

        expect(kpi('rpt-kpi-transfers-count')).toBe('2 transakcji');
        // Obie nogi sie znosza — suma przelewow wewnetrznych to zero i to jest
        // sygnal, ze zaden przelew nie zgubil swojej drugiej strony.
        expect(kpi('rpt-kpi-transfers')).toBe('+0,00 PLN');
    });

    it('wlaczone — zawyzaja obroty po obu stronach', () => {
        przelicz({ bezPrzelewow: false });

        // To jest dokladnie ten blad, przed ktorym chroni domyslne wykluczenie:
        // 1000 zl przelozone miedzy wlasnymi kontami wyglada jak przychod
        // i jak wydatek jednoczesnie.
        expect(kpi('rpt-kpi-income')).toBe('6000,00 PLN');
        expect(kpi('rpt-kpi-expense')).toBe('1200,00 PLN');
        // Wynik netto zostaje poprawny, choc obroty sa zmyslone — dlatego
        // sam wynik netto nie wystarcza do wykrycia problemu.
        expect(kpi('rpt-kpi-net')).toBe('+4800,00 PLN');
    });
});

describe('zakres dat', () => {
    beforeEach(() => {
        transactions = [
            tx({ id: 1, date: '2026-01-31', amount: -100, category: 'Zakupy' }),
            tx({ id: 2, date: '2026-02-01', amount: -200, category: 'Zakupy' }),
            tx({ id: 3, date: '2026-02-28', amount: -300, category: 'Zakupy' }),
            tx({ id: 4, date: '2026-03-01', amount: -400, category: 'Zakupy' }),
        ];
    });

    it('obie granice sa domkniete — dzien "od" i dzien "do" wchodza do wyniku', () => {
        przelicz({ od: '2026-02-01', do: '2026-02-28' });

        expect(kpi('rpt-kpi-expense')).toBe('500,00 PLN');      // 200 + 300
        expect(kpi('rpt-kpi-expense-count')).toBe('2 transakcji');
    });

    it('transakcja dzien przed zakresem i dzien po nim jest pomijana', () => {
        przelicz({ od: '2026-02-02', do: '2026-02-27' });

        expect(kpi('rpt-kpi-expense')).toBe('0,00 PLN');
        expect(kpi('rpt-kpi-expense-count')).toBe('0 transakcji');
    });

    it('pusty zakres nie wywala raportu, tylko pokazuje zera', () => {
        przelicz({ od: '2030-01-01', do: '2030-12-31' });

        expect(kpi('rpt-kpi-income')).toBe('0,00 PLN');
        expect(kpi('rpt-kpi-expense')).toBe('0,00 PLN');
        expect(kpi('rpt-kpi-net')).toBe('+0,00 PLN');
    });
});

describe('rptGroupByMonth', () => {
    it('rozdziela przychody od wydatkow, wydatki jako wartosc dodatnia', () => {
        const miesiace = rptGroupByMonth([
            tx({ id: 1, date: '2026-01-10', amount: 1000 }),
            tx({ id: 2, date: '2026-01-20', amount: -400 }),
            tx({ id: 3, date: '2026-02-10', amount: -150 }),
        ]);

        expect(miesiace['2026-01']).toEqual({ income: 1000, expense: 400 });
        expect(miesiace['2026-02']).toEqual({ income: 0, expense: 150 });
    });

    it('pusta lista daje pusty wynik', () => {
        expect(rptGroupByMonth([])).toEqual({});
    });
});

describe('rptFmt', () => {
    it('formatuje polskim przecinkiem i dwoma miejscami', () => {
        expect(rptFmt(1234.5)).toBe('1234,50 PLN');
    });

    it('ze znakiem uzywa minusa typograficznego dla wartosci ujemnych', () => {
        expect(rptFmt(-50, true)).toBe('−50,00 PLN');
        expect(rptFmt(50, true)).toBe('+50,00 PLN');
    });
});

describe('atrapa DOM zgadza sie z base.html', () => {
    // Testy wyzej dzialaja na recznie zbudowanym DOM. Gdyby ktos zmienil id
    // w szablonie, testy nadal by przechodzily, a aplikacja przestalaby
    // wyswietlac KPI. Ten test wiaze jedno z drugim.
    it('kazdy id z atrapy istnieje w szablonie', async () => {
        const { readFileSync } = await import('node:fs');
        const szablon = readFileSync('app/templates/base.html', 'utf-8');

        for (const id of [...ID_KPI, ...ID_FILTROW]) {
            expect(szablon, `brak id="${id}" w base.html`).toContain(`id="${id}"`);
        }
    });
});
