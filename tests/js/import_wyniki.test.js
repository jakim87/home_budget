// Testy listy wyników importu (02_import.js): karta pliku i podsumowanie paczki.
//
// Podsumowanie mówi, ile wyciągów weszło i których kont zabrakło — to tylko
// informacja, więc liczy się wyłącznie z tego, co serwer zwrócił dla każdego pliku
// i z historii importów.

import { readFileSync } from 'node:fs';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';

// Elementy, które 02_import.js wyszukuje przy ładowaniu.
const ID_STRONY = [
    'csvFileInput', 'folderInput', 'pickFilesBtn', 'pickFolderBtn', 'import-dropzone',
    'import-progress', 'import-results', 'importError',
    'toggleImportHistoryBtn', 'import-history', 'importHistoryChevron',
];

beforeAll(() => {
    document.body.innerHTML = ID_STRONY.map(id => `<div id="${id}"></div>`).join('');
    zaladujModuly('01_state.js', '04_helpers.js', '03_staging.js', '02_import.js');
});

beforeEach(() => {
    accounts = [
        { id: 1, name: 'Moje ING' },
        { id: 2, name: 'Wakacje' },
        { id: 3, name: 'Revolut EUR' },
    ];
    inactiveAccounts = [{ id: 9, name: 'Zamknięte' }];
});

const summary = (konta, reszta = {}) => ({
    bank: 'ing', format: 'csv', rows_in_file: 10, saved: 8, duplicates: 2, skipped_foreign: 0,
    accounts: konta, ...reszta,
});

describe('podsumujPaczke', () => {
    it('liczy konta i łączny zakres tylko z udanych plików', () => {
        const p = podsumujPaczke([
            { ok: true, summary: summary([
                { account_id: 1, from: '2026-10-01', to: '2026-10-31', count: 5 },
                { account_id: 2, from: '2026-09-28', to: '2026-10-20', count: 3 },
            ]) },
            { ok: true, summary: summary([{ account_id: 1, from: '2026-11-01', to: '2026-11-05', count: 0 }], { saved: 0 }) },
            { ok: false, summary: null },
        ]);
        expect(p).toMatchObject({ pliki: 3, wgrane: 2, bledy: 1, od: '2026-09-28', doDnia: '2026-11-05', nowe: 8 });
        expect([...p.konta]).toEqual([1, 2]);
    });

    it('plik jeszcze w trakcie wgrywania nie jest błędem', () => {
        expect(podsumujPaczke([{ ok: null }]).bledy).toBe(0);
    });
});

describe('kontaBezWyciagu', () => {
    it('pokazuje konta z historią spoza paczki, z ostatnim dniem wyciągu', () => {
        const historia = [
            { account_id: 3, period_end: '2026-10-24' },
            { account_id: 3, period_end: '2026-09-30' },
            { account_id: 1, period_end: '2026-10-31' },
            { account_id: 9, period_end: '2026-01-31' },  // konto zamknięte — pomijamy
            { account_id: null, period_end: '2026-10-31' },
        ];
        expect(kontaBezWyciagu(historia, new Set([1]))).toEqual([
            { account_id: 3, nazwa: 'Revolut EUR', doDnia: '2026-10-24' },
        ]);
    });

    it('konto bez historii importów nie jest brakującym wyciągiem', () => {
        expect(kontaBezWyciagu([], new Set())).toEqual([]);
    });
});

describe('kartaPlikuHtml', () => {
    it('każde konto z pliku w osobnej linii, z zakresem i liczbą operacji', () => {
        document.body.insertAdjacentHTML('beforeend', '<div id="karta"></div>');
        const karta = document.getElementById('karta');
        karta.innerHTML = kartaPlikuHtml('wyciag.csv', { ok: true, summary: summary([
            { account_id: 1, from: '2026-10-01', to: '2026-10-31', count: 5 },
            { account_id: 2, from: '2026-10-03', to: '2026-10-03', count: 1 },
        ]) }, '14:32');
        const linie = [...karta.querySelectorAll('.space-y-0\\.5 > div')].map(d => d.textContent.replace(/\s+/g, ' ').trim());
        expect(linie).toEqual(['Moje ING 01.10–31.10.2026 5 operacji', 'Wakacje 03.10.2026 1 operacja']);
        expect(karta.textContent).toContain('ING · CSV · 14:32');
        expect(karta.textContent).toContain('w pliku 10 · nowych 8 · duplikaty 2');
        expect(karta.textContent).not.toContain('spoza aplikacji');
    });

    it('nazwa pliku i błąd są escapowane', () => {
        const html = kartaPlikuHtml('<img src=x>.csv', { ok: false, error: '<b>zły</b>' }, '09:05');
        expect(html).not.toContain('<img');
        expect(html).not.toContain('<b>');
        expect(html).toContain('09:05');
    });
});

describe('zgodność z base.html', () => {
    it('elementy używane przez 02_import.js istnieją w szablonie', () => {
        const szablon = readFileSync('app/templates/base.html', 'utf-8');
        expect(ID_STRONY.filter(id => !szablon.includes(`id="${id}"`))).toEqual([]);
    });
});
