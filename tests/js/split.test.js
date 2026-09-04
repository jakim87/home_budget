// Testy modala rozbijania transakcji (11_transactions.js).
//
// Pole kwoty przelicza sume przy kazdym znaku (oninput), wiec podsumowanie musi
// dac sie odswiezyc BEZ przerysowania wierszy — inaczej input znika spod palcow
// uzytkownika razem z kursorem. Ten podzial pilnuje test "nie przerysowuje
// wierszy": to jedyne miejsce, gdzie widac roznice miedzy renderSplitRows()
// a aktualizujPodsumowanieSplitu().

import { readFileSync } from 'node:fs';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';

// Elementy modala, ktorych dotyka kod podzialu. Osobny test nizej pilnuje, zeby
// ta lista nie rozjechala sie z base.html.
const ID_MODALA = ['split-modal', 'split-rows', 'split-remaining', 'split-save-btn',
                   'split-original-desc', 'split-original-amount'];

function zbudujDom() {
    document.body.innerHTML = `
        <input id="tx-desc"><select id="tx-category"></select><select id="tx-account"></select>
        <form id="transaction-form"></form><form id="category-form"></form>
        <div id="split-modal" class="hidden">
            <span id="split-original-amount"></span>
            <p id="split-original-desc"></p>
            <p id="split-remaining"></p>
            <div id="split-rows"></div>
            <button id="split-save-btn"></button>
        </div>
    `;
}

const pozostalo = () => document.getElementById('split-remaining').innerText;
const zapisZablokowany = () => document.getElementById('split-save-btn').disabled;

beforeAll(() => {
    // 11_transactions.js podpina sluchacze do formularza transakcji juz przy
    // wczytaniu pliku, wiec DOM musi istniec przed zaladowaniem modulu.
    zbudujDom();
    zaladujModuly('01_state.js', '04_helpers.js', '07_categories.js', '11_transactions.js');
});

beforeEach(() => {
    zbudujDom();
    categories = [
        { id: 1, name: 'Jedzenie', type: 'expense' },
        { id: 2, name: 'Inne', type: 'expense' },
    ];
    transactions = [{ id: 13, date: '2026-09-01', amount: -26.36, desc: 'Sklep Chorten',
                      category: 'Inne', account_id: 1, splits: [] }];
    openSplitModal(13);
});

describe('podsumowanie podzialu', () => {
    it('pokazuje cala kwote transakcji, dopoki nie ma pozycji', () => {
        expect(pozostalo()).toBe('26.36 PLN');
        expect(document.getElementById('split-original-amount').innerText).toBe('26.36 PLN');
    });

    it('odejmuje wpisana kwote juz przy pisaniu, bez przerysowania wierszy', () => {
        addSplitRow();
        const input = document.querySelector('#split-rows input[type=number]');
        input.value = '2';
        updateSplit(currentSplits[0].id, 'amount', '2');

        expect(pozostalo()).toBe('24.36 PLN');
        // Ten sam wezel co przed przeliczeniem — gdyby wiersze zostaly
        // przerysowane, uzytkownik stracilby kursor w polu.
        expect(document.querySelector('#split-rows input[type=number]')).toBe(input);
        expect(input.value).toBe('2');
    });

    it('przy rozdzieleniu do zera pozwala zapisac', () => {
        addSplitRow();
        updateSplit(currentSplits[0].id, 'amount', '20');
        addSplitRow();
        updateSplit(currentSplits[1].id, 'amount', '6.36');

        expect(pozostalo()).toBe('0.00 PLN');
        expect(zapisZablokowany()).toBe(false);
    });

    it('przy przekroczeniu kwoty blokuje zapis', () => {
        addSplitRow();
        updateSplit(currentSplits[0].id, 'amount', '30');

        expect(pozostalo()).toBe('-3.64 PLN');
        expect(zapisZablokowany()).toBe(true);
    });

    it('odblokowuje zapis, gdy uzytkownik poprawi zawyzona kwote', () => {
        addSplitRow();
        updateSplit(currentSplits[0].id, 'amount', '30');
        updateSplit(currentSplits[0].id, 'amount', '10');

        expect(zapisZablokowany()).toBe(false);
        expect(pozostalo()).toBe('16.36 PLN');
    });
});

describe('badge transakcji rozbitej', () => {
    it('otwiera modal podzialu klikiem i Enterem, ale nie dowolnym klawiszem', () => {
        closeSplitModal();
        expect(splitTxId).toBe(null);

        openSplitModal(13, { key: 'a', preventDefault() {} });
        expect(splitTxId).toBe(null);

        openSplitModal(13, { key: 'Enter', preventDefault() {} });
        expect(splitTxId).toBe(13);
    });
});

describe('atrapa DOM zgadza sie z base.html', () => {
    it('kazde uzyte id istnieje w szablonie', () => {
        const szablon = readFileSync('app/templates/base.html', 'utf-8');
        for (const id of ID_MODALA) {
            expect(szablon, `brak id="${id}" w base.html`).toContain(`id="${id}"`);
        }
    });
});
