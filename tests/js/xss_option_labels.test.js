// XSS w listach wyboru budowanych przez innerHTML (A1 z audytu 2026-09-13).
//
// Nazwy kont i kontrahentów trafiają do <option> sklejanych w string, a ten
// string ląduje w row.innerHTML (poczekalnia, edycja inline) — tam, w
// przeciwieństwie do select.innerHTML, przeglądarka NIE ignoruje obcych tagów.
// Nazwę konta ustala użytkownik, a konto demo jest publiczne, więc payload w
// nazwie („</select><img onerror=…>") wykonałby się u innych zwiedzających.
// Dlatego każda nazwa musi przejść przez escapeHtml() — patrz reguła XSS w CLAUDE.md.

import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';

const PAYLOAD = '</select><img src=x onerror=alert(1)>';

beforeAll(() => {
    // 07_categories.js na poziomie modułu podpina handler do #category-form,
    // więc element musi istnieć zanim wykonamy plik (tak jak w przeglądarce).
    document.body.innerHTML = '<form id="category-form"><input id="cat-name"><select id="cat-type"></select></form>';
    zaladujModuly('01_state.js', '04_helpers.js', '07_categories.js');
});

beforeEach(() => {
    // Stan globalny zadeklarowany w 01_state.js; nadpisujemy go na potrzeby testu.
    accounts = [
        { id: 1, name: PAYLOAD, bank_name: PAYLOAD, balance: 10, is_default: false },
        { id: 2, name: 'Konto zwykłe', bank_name: 'ING', balance: 20, is_default: true },
    ];
    inactiveAccounts = [];
    contractors = [{ id: 7, name: PAYLOAD }];
});

// Wstawia wynik funkcji tak, jak robi to kod produkcyjny: przez innerHTML
// całego wiersza (a nie samego <select>), bo to jest wektor ataku.
function wstawJakoWiersz(optionsHtml) {
    const row = document.createElement('tr');
    row.innerHTML = `<td><select><option value="">—</option>${optionsHtml}</select></td>`;
    document.body.innerHTML = '';
    document.body.appendChild(row);
    return row;
}

describe('escapowanie nazw w listach wyboru (A1)', () => {
    it('getContractorOptionsHtml nie przepuszcza tagów z nazwy kontrahenta', () => {
        const row = wstawJakoWiersz(getContractorOptionsHtml());
        expect(row.querySelector('img')).toBeNull();
        expect(getContractorOptionsHtml()).not.toContain('<img');
    });

    it('getDestAccountOptionsHtml nie przepuszcza tagów z nazwy konta', () => {
        // sourceAccountId=2, więc na liście zostaje konto z payloadem (id 1).
        const row = wstawJakoWiersz(getDestAccountOptionsHtml(2));
        expect(row.querySelector('img')).toBeNull();
    });

    it('option nadal niesie poprawne id jako value', () => {
        expect(getContractorOptionsHtml()).toContain('value="7"');
        expect(getDestAccountOptionsHtml(2)).toContain('value="1"');
    });
});
