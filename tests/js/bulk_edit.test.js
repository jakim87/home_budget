// Testy edycji zbiorczej transakcji (19_bulk_edit.js).
//
// Najwazniejszy przypadek: usuniecie zaznaczonej nogi przelewu wewnetrznego
// zabiera rowniez druga noge — takze wtedy, gdy uzytkownik jej NIE zaznaczyl.
// Ostrzezenie musi to powiedziec PRZED usunieciem, bo po fakcie zniknely dane
// z konta, ktorego uzytkownik w ogole nie mial na ekranie.

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { tx, zaladujModuly } from './helpers.js';

function zbudujDom() {
    document.body.innerHTML = `
        <div id="toast-container"></div>
        <div id="tx-bulk-bar" class="hidden">
            <span id="tx-bulk-count"></span>
            <select id="tx-bulk-category"></select>
        </div>
        <input type="checkbox" id="tx-select-all">
        <table><tbody>
            <tr><td><input type="checkbox" class="tx-select-check" value="1"></td></tr>
            <tr><td><input type="checkbox" class="tx-select-check" value="2"></td></tr>
            <tr><td><input type="checkbox" class="tx-select-check" value="3"></td></tr>
        </tbody></table>
    `;
}

const pasekUkryty = () => document.getElementById('tx-bulk-bar').classList.contains('hidden');
const licznik = () => document.getElementById('tx-bulk-count').textContent;

beforeAll(() => {
    zaladujModuly('01_state.js', '04_helpers.js', '19_bulk_edit.js');
    // fetchInitialData nalezy do 15_init.js i ciagnie za soba cale ladowanie
    // stanu z serwera — w tych testach interesuje nas tylko to, ze zostala
    // zawolana po udanej operacji.
    globalThis.fetchInitialData = vi.fn();
});

beforeEach(() => {
    zbudujDom();
    clearTxSelection();
    transactions = [];
    categories = [
        { id: 1, name: 'Zakupy', type: 'expense' },
        { id: 2, name: 'Rachunki', type: 'expense' },
        { id: 3, name: 'Przelew własny', type: 'transfer' },
    ];
    document.getElementById('tx-bulk-category').dataset.filled = '';
    vi.restoreAllMocks();
    globalThis.fetchInitialData = vi.fn();
});

describe('zaznaczanie', () => {
    it('pasek akcji pojawia sie dopiero po zaznaczeniu czegokolwiek', () => {
        expect(pasekUkryty()).toBe(true);
        toggleTxSelection(1);
        expect(pasekUkryty()).toBe(false);
        toggleTxSelection(1);
        expect(pasekUkryty()).toBe(true);
    });

    it('licznik odmienia rzeczownik po polsku', () => {
        toggleTxSelection(1);
        expect(licznik()).toBe('Zaznaczono 1 transakcja');
        toggleTxSelection(2);
        expect(licznik()).toBe('Zaznaczono 2 transakcje');
        toggleTxSelection(3);
        expect(licznik()).toBe('Zaznaczono 3 transakcje');
    });

    it('"zaznacz wszystkie" obejmuje kazdy widoczny wiersz', () => {
        toggleSelectAllTx(true);
        expect(licznik()).toBe('Zaznaczono 3 transakcje');
        expect([...document.querySelectorAll('.tx-select-check')].every(c => c.checked)).toBe(true);

        toggleSelectAllTx(false);
        expect(pasekUkryty()).toBe(true);
    });

    it('checkbox naglowka jest "czesciowy" przy podzbiorze', () => {
        toggleTxSelection(1);
        const all = document.getElementById('tx-select-all');
        expect(all.indeterminate).toBe(true);
        expect(all.checked).toBe(false);

        toggleTxSelection(2);
        toggleTxSelection(3);
        expect(all.indeterminate).toBe(false);
        expect(all.checked).toBe(true);
    });

    it('lista kategorii pomija przelewy wewnetrzne', () => {
        toggleTxSelection(1);
        const opcje = [...document.getElementById('tx-bulk-category').options].map(o => o.value);
        expect(opcje).toContain('Zakupy');
        expect(opcje).toContain('Rachunki');
        expect(opcje).not.toContain('Przelew własny');
    });
});

describe('usuwanie zbiorcze', () => {
    beforeEach(() => {
        transactions = [
            tx({ id: 1, date: '2026-01-10', amount: -100 }),
            // Noga przelewu (id 2) sparowana z noga na drugim koncie (id 99),
            // ktorej uzytkownik nie widzi w biezacym widoku.
            { ...tx({ id: 2, date: '2026-01-15', amount: -500, category: 'Przelew własny' }),
              linked_transaction_id: 99 },
        ];
    });

    it('ostrzega o drugiej nodze przelewu PRZED usunieciem', async () => {
        const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(false);
        toggleTxSelection(2);

        await bulkDeleteSelected();

        expect(confirmSpy).toHaveBeenCalled();
        const komunikat = confirmSpy.mock.calls[0][0];
        expect(komunikat).toContain('przelewy wewnętrzne');
        expect(komunikat).toContain('łącznie 2');
    });

    it('rezygnacja w oknie potwierdzenia nie wysyla zadnego zadania', async () => {
        vi.spyOn(globalThis, 'confirm').mockReturnValue(false);
        const fetchSpy = vi.fn();
        globalThis.fetch = fetchSpy;

        toggleTxSelection(1);
        await bulkDeleteSelected();

        expect(fetchSpy).not.toHaveBeenCalled();
    });

    it('wysyla jedno zadanie z lista ID i odswieza dane', async () => {
        vi.spyOn(globalThis, 'confirm').mockReturnValue(true);
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ usuniete: 2, drugie_nogi: 1 }),
        });

        toggleTxSelection(1);
        toggleTxSelection(2);
        await bulkDeleteSelected();

        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        const [url, opcje] = globalThis.fetch.mock.calls[0];
        expect(url).toBe('/api/transactions/bulk/delete');
        expect(JSON.parse(opcje.body)).toEqual({ ids: [1, 2] });
        expect(globalThis.fetchInitialData).toHaveBeenCalled();
    });

    it('blad serwera nie czysci zaznaczenia i nie odswieza danych', async () => {
        vi.spyOn(globalThis, 'confirm').mockReturnValue(true);
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            json: async () => ({ error: 'Część transakcji nie istnieje lub brak uprawnień.' }),
        });

        toggleTxSelection(1);
        await bulkDeleteSelected();

        expect(globalThis.fetchInitialData).not.toHaveBeenCalled();
        expect(pasekUkryty()).toBe(false);
    });
});

describe('zbiorcza zmiana kategorii', () => {
    it('bez wybranej kategorii nie wysyla zadania', async () => {
        globalThis.fetch = vi.fn();
        toggleTxSelection(1);

        await bulkChangeCategory();

        expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('melduje liczbe pominietych przelewow', async () => {
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ zmienione: 2, pominiete_przelewy: 1 }),
        });

        toggleTxSelection(1);
        toggleTxSelection(2);
        document.getElementById('tx-bulk-category').value = 'Rachunki';
        await bulkChangeCategory();

        const toast = document.querySelector('#toast-container .toast');
        expect(toast.innerText).toContain('Zmieniono kategorię: 2');
        expect(toast.innerText).toContain('Pominięto przelewy wewnętrzne: 1');
    });
});
