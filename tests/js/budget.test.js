// Testy zakladki Budzet.
//
// Same kwoty licze backend (tests/test_budget_plan.py) — tutaj sprawdzamy to,
// czego pytest nie zobaczy: jak wynik zamienia sie na pasek postepu. Kierunek
// jest tu istotny, bo ten sam procent znaczy cos przeciwnego po obu stronach:
// przekroczony plan wydatkow to zla wiadomosc, osiagniety plan przychodow —
// dobra.

import { beforeAll, describe, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';

// Elementy, ktorych dotyka 20_budget.js. Osobny test nizej pilnuje, zeby ta
// lista nie rozjechala sie z base.html.
const ID_WIDOKU = [
    'budget-month-display', 'budget-planned-income', 'budget-planned-expense',
    'budget-balance', 'budget-warning', 'budget-rows',
];

const pozycja = (nadpisania = {}) => ({
    category_id: 1, category_name: 'Jedzenie', category_type: 'expense',
    plan: 1000, wykonane: 0, zarezerwowane: 0,
    sugestia: { kwota: null, podstawa: 'Za mało danych', zakres_min: null, zakres_max: null, liczba_miesiecy: 0, rok_temu: null },
    ...nadpisania,
});

beforeAll(() => {
    zaladujModuly('04_helpers.js', '20_budget.js');
});

describe('pasek postepu', () => {
    it('bez planu nie pokazuje procentu', () => {
        const stan = budgetStanPozycji(pozycja({ plan: null, wykonane: 300 }));
        expect(stan.procent).toBeNull();
        expect(stan.szerWykonane).toBe(0);
    });

    it('wydatek w granicach planu jest zielony', () => {
        const stan = budgetStanPozycji(pozycja({ wykonane: 400 }));
        expect(stan.procent).toBe(40);
        expect(stan.kolor).toBe('bg-emerald-500');
        expect(stan.ostrzezenie).toBe(false);
    });

    it('wydatek blisko planu ostrzega kolorem, ale jeszcze nie flaga', () => {
        const stan = budgetStanPozycji(pozycja({ wykonane: 900 }));
        expect(stan.kolor).toBe('bg-amber-500');
        expect(stan.ostrzezenie).toBe(false);
    });

    it('przekroczony plan wydatkow jest czerwony i oflagowany', () => {
        const stan = budgetStanPozycji(pozycja({ wykonane: 1200 }));
        expect(stan.kolor).toBe('bg-rose-500');
        expect(stan.ostrzezenie).toBe(true);
    });

    it('osiagniety plan przychodow to dobra wiadomosc, nie ostrzezenie', () => {
        const stan = budgetStanPozycji(pozycja({
            category_type: 'income', category_name: 'Wynagrodzenie', wykonane: 1200,
        }));
        expect(stan.kolor).toBe('bg-emerald-500');
        expect(stan.ostrzezenie).toBe(false);
    });

    it('rezerwacje dokladaja sie do wykonania, a nie obok niego', () => {
        const stan = budgetStanPozycji(pozycja({ wykonane: 300, zarezerwowane: 200 }));
        expect(stan.procent).toBe(50);
        expect(stan.szerWykonane).toBe(30);
        expect(stan.szerRezerwacji).toBe(20);
    });

    it('segmenty nie wyjezdzaja poza pasek przy przekroczeniu', () => {
        const stan = budgetStanPozycji(pozycja({ wykonane: 900, zarezerwowane: 800 }));
        expect(stan.szerWykonane + stan.szerRezerwacji).toBeLessThanOrEqual(100);
    });
});

describe('kreska uplywu miesiaca', () => {
    it('polowa miesiaca to okolo 50%', () => {
        expect(budgetUplywMiesiaca(2026, 4, new Date(2026, 3, 15))).toBeCloseTo(50, 0);
    });

    it('dla innego miesiaca niz biezacy kreski nie ma', () => {
        expect(budgetUplywMiesiaca(2026, 4, new Date(2026, 5, 15))).toBeNull();
        expect(budgetUplywMiesiaca(2025, 4, new Date(2026, 3, 15))).toBeNull();
    });
});

describe('atrapa DOM zgadza sie z base.html', () => {
    it('kazdy id uzywany przez modul istnieje w szablonie', async () => {
        const { readFileSync } = await import('node:fs');
        const szablon = readFileSync('app/templates/base.html', 'utf-8');

        for (const id of ID_WIDOKU) {
            expect(szablon, `brak id="${id}" w base.html`).toContain(`id="${id}"`);
        }
    });

    it('zakladka jest podpieta do switchTab', async () => {
        const { readFileSync } = await import('node:fs');
        const taby = readFileSync('app/static/js/06_tabs.js', 'utf-8');
        expect(taby).toContain("'budget'");
        expect(taby).toContain('renderBudget()');
    });
});
