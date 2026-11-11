// Zapis konta w słowniku (formularz w 08_accounts.js).
//
// Zmiana nazwy konta przemianowuje po stronie serwera także jego kontrahenta
// „Moje konto: …”, a front trzyma kontrahentów w pamięci z ostatniego /api/init.
// Bez odświeżenia słownik i pole kontrahenta przy przelewie pokazywałyby starą nazwę
// aż do przeładowania strony.

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

function zbudujDom() {
    document.body.innerHTML = `
        <ul id="account-list"></ul>
        <form id="account-form">
            <input id="acc-id"><input id="acc-name"><input id="acc-bank"><input id="acc-number">
            <select id="acc-type"><option value=""></option></select>
            <select id="acc-currency"><option value="PLN">PLN</option></select>
            <input id="acc-owner"><input id="acc-co-owner"><input id="acc-default" type="checkbox">
            <button id="acc-cancel-btn" class="hidden" type="button"></button>
            <button id="acc-submit-btn" class="bg-indigo-600 hover:bg-indigo-700" type="submit"></button>
        </form>
        <div id="reconcile-modal"></div><span id="reconcile-account-name"></span>
        <span id="reconcile-current-balance"></span><input id="reconcile-new-balance">
        <form id="reconcile-form"></form><input id="reconcile-date">
    `;
}

beforeAll(() => {
    zbudujDom();
    zaladujModuly('01_state.js', '04_helpers.js', '08_accounts.js');
});

beforeEach(() => {
    accounts = [{ id: 1, name: 'Wakacje', bank_name: 'Bank', balance: 0, currency: 'PLN' }];
    globalThis.fetchInitialData = vi.fn();
    globalThis.showToast = vi.fn();
});

/** Zapisuje edycję konta nr 1; serwer odpowiada kontem o podanej nazwie. */
async function zapiszEdycje({ wpisanaNazwa, odpowiedz }) {
    globalThis.fetch = vi.fn(async () => ({
        ok: true,
        json: async () => ({ id: 1, name: odpowiedz, bank_name: 'Bank', balance: 0, currency: 'PLN' }),
    }));
    document.getElementById('acc-id').value = '1';
    document.getElementById('acc-name').value = wpisanaNazwa;
    document.getElementById('account-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect(showToast).toHaveBeenCalled());
}

describe('zapis edycji konta', () => {
    it('po zmianie nazwy odświeża dane z serwera — kontrahent „Moje konto: …” też zmienił nazwę', async () => {
        await zapiszEdycje({ wpisanaNazwa: 'Wakacje 2027', odpowiedz: 'Wakacje 2027' });

        expect(fetchInitialData).toHaveBeenCalledTimes(1);
        expect(accounts[0].name).toBe('Wakacje 2027');
    });

    it('bez zmiany nazwy nie przeładowuje całego stanu', async () => {
        await zapiszEdycje({ wpisanaNazwa: 'Wakacje', odpowiedz: 'Wakacje' });

        expect(fetchInitialData).not.toHaveBeenCalled();
        expect(accounts[0].name).toBe('Wakacje');
    });
});
