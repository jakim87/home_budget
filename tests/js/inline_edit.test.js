// Edycja wiersza transakcji (saveInlineEdit w 11_transactions.js).
//
// Kategorie systemowe ("Uzgadnianie salda") nie trafiaja do selecta kategorii,
// wiec select w trybie edycji zaznaczal pierwsza opcje i zapis zmienial
// kategorie uzgodnienia na pierwsza z listy. Do tego znak kwoty brany z typu
// kategorii odwracal uzgodnienie na plus w wydatek.

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

function zbudujDom(id, { zSelectem, kategoria = 'Jedzenie' }) {
    document.body.innerHTML = `
        <input id="tx-desc"><select id="tx-category"></select><select id="tx-account"></select>
        <form id="transaction-form"></form><form id="category-form"></form>
        <input id="edit-date-${id}" value="2026-10-01">
        <input id="edit-desc-${id}" value="Korekta">
        <input id="edit-amount-${id}" value="150.00">
        <select id="edit-cont-${id}"><option value="" selected></option></select>
        <input id="edit-comment-${id}" value="">
        ${zSelectem ? `<select id="edit-cat-${id}"><option value="${kategoria}" selected>${kategoria}</option></select>` : ''}
    `;
}

let wyslane;

beforeAll(() => {
    zbudujDom(0, { zSelectem: false });
    zaladujModuly('01_state.js', '04_helpers.js', '07_categories.js', '11_transactions.js');
});

beforeEach(() => {
    categories = [
        { id: 1, name: 'Jedzenie', type: 'expense' },
        { id: 2, name: 'Pensja', type: 'income' },
        { id: 3, name: 'Uzgadnianie salda', type: 'system_reconciliation', is_system_category: true },
        { id: 4, name: 'Zakupy', type: 'expense' },
        { id: 5, name: 'Przelew wewnętrzny', type: 'transfer' },
    ];
    wyslane = null;
    globalThis.fetch = vi.fn(async (_url, opts) => { wyslane = JSON.parse(opts.body); return { ok: true }; });
    globalThis.fetchInitialData = vi.fn();
    globalThis.showToast = vi.fn();
});

describe('edycja uzgodnienia salda', () => {
    it('zachowuje kategorie systemowa i znak kwoty', async () => {
        transactions = [{ id: 7, date: '2026-10-01', amount: 120, desc: 'Korekta',
                          category: 'Uzgadnianie salda', account_id: 1, splits: [] }];
        zbudujDom(7, { zSelectem: false });

        await saveInlineEdit(7);

        expect(wyslane.category).toBe('Uzgadnianie salda');
        expect(wyslane.amount).toBe(150);
    });

    it('ignoruje select kategorii, gdyby jednak byl w wierszu', async () => {
        transactions = [{ id: 8, date: '2026-10-01', amount: -40, desc: 'Korekta',
                          category: 'Uzgadnianie salda', account_id: 1, splits: [] }];
        zbudujDom(8, { zSelectem: true });

        await saveInlineEdit(8);

        expect(wyslane.category).toBe('Uzgadnianie salda');
        expect(wyslane.amount).toBe(-150);
    });

    it('zwykla transakcja nadal bierze kategorie i znak z selecta', async () => {
        transactions = [{ id: 9, date: '2026-10-01', amount: 40, desc: 'Zakupy',
                          category: 'Pensja', account_id: 1, splits: [] }];
        zbudujDom(9, { zSelectem: true });

        await saveInlineEdit(9);

        expect(wyslane.category).toBe('Jedzenie');
        expect(wyslane.amount).toBe(-150);
    });
});

describe('edycja transakcji z podzialem (#249)', () => {
    it('zachowuje kategorie i znak, nawet gdy autouzupelnianie zmienilo pole', async () => {
        transactions = [{ id: 10, date: '2026-10-01', amount: 40, desc: 'Wyplata',
                          category: 'Pensja', account_id: 1,
                          splits: [{ category: 'Pensja', amount: 40 }] }];
        // Pole z kategoria "Jedzenie" udaje to, co zostawial handleAutoFill.
        zbudujDom(10, { zSelectem: true });

        await saveInlineEdit(10);

        expect(wyslane.category).toBe('Pensja');
        expect(wyslane.amount).toBe(150);
    });
});

// Znak bierze się z kategorii tylko przy zmianie jej TYPU. Zwrot z Biedronki ma kwotę
// dodatnią i kategorię wydatkową (z reguły kontrahenta) — poprawka samego opisu
// robiła z niego wydatek i przesuwała saldo o podwójną kwotę.
describe('edycja bez zmiany typu kategorii zachowuje znak', () => {
    it('zwrot w kategorii wydatkowej zostaje wplywem', async () => {
        transactions = [{ id: 11, date: '2026-10-01', amount: 15, desc: 'Zwrot',
                          category: 'Jedzenie', account_id: 1, splits: [] }];
        zbudujDom(11, { zSelectem: true });

        await saveInlineEdit(11);

        expect(wyslane.amount).toBe(150);
    });

    it('zwrot przeniesiony do innej kategorii wydatkowej tez', async () => {
        transactions = [{ id: 12, date: '2026-10-01', amount: 15, desc: 'Zwrot',
                          category: 'Zakupy', account_id: 1, splits: [] }];
        zbudujDom(12, { zSelectem: true });

        await saveInlineEdit(12);

        expect(wyslane.category).toBe('Jedzenie');
        expect(wyslane.amount).toBe(150);
    });

    it('wplyw przelewu bez pary zostaje wplywem', async () => {
        transactions = [{ id: 13, date: '2026-10-01', amount: 300, desc: 'Z oszczednosci',
                          category: 'Przelew wewnętrzny', account_id: 1, splits: [] }];
        zbudujDom(13, { zSelectem: true, kategoria: 'Przelew wewnętrzny' });

        await saveInlineEdit(13);

        expect(wyslane.amount).toBe(150);
    });
});
