// Testy podziału poczekalni importu na przelewy i operacje kont (03_staging.js).
//
// Zakładka Import pokazuje parę przelewu z jednego importu jako JEDEN wiersz,
// wydatki i przychody grupuje po kontach, a „Zatwierdź gotowe" pomija możliwe
// duplikaty. Te decyzje zapadają w czystych funkcjach — tu sprawdzamy, że łączą
// tylko to, co serwer sparował, i że nic nie ginie przy podziale.

import { readFileSync } from 'node:fs';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

// Elementy, których dotyka renderStaging(). Osobny test pilnuje, żeby lista
// nie rozjechała się z base.html.
const ID_STRONY = [
    'staging-list', 'staging-empty', 'staging-badge', 'staging-filters', 'staging-summary', 'approve-all-btn',
    'sf-all', 'sf-ready', 'sf-todo', 'sf-duplicate', 'sf-transfer',
    'sf-count-all', 'sf-count-ready', 'sf-count-todo', 'sf-count-dup', 'sf-count-transfer',
];

function zbudujDom() {
    document.body.innerHTML = `<div id="toast-container"></div>` +
        ID_STRONY.map(id => (id.startsWith('sf-count') ? `<span id="${id}"></span>` : `<div id="${id}"></div>`)).join('');
    document.getElementById('approve-all-btn').outerHTML = '<button id="approve-all-btn"></button>';
}

/** Wiersz poczekalni w kształcie z GET /api/staging/pending. */
function stg({ id, account_id = 1, amount = -100, date = '2026-09-30', title = 'Operacja',
               proposed_category = 'Zakupy', proposed_contractor_id = 10,
               duplicate_candidates = [], ...reszta }) {
    return { id, account_id, amount, date, title, contractor: '', proposed_category,
             proposed_contractor_id, suggested_contractor_name: '', duplicate_candidates, ...reszta };
}

/** Noga przelewu: kategoria transferu, kontrahent „Moje konto: X". */
function noga({ id, account_id, amount, pair = 'staging', pair_id = null, cont = 21, ...reszta }) {
    return stg({ id, account_id, amount, proposed_category: 'Przelew wewnętrzny',
                 proposed_contractor_id: cont, transfer_pair: pair, transfer_pair_id: pair_id, ...reszta });
}

beforeAll(() => {
    zaladujModuly('01_state.js', '04_helpers.js', '03_staging.js');
    // Opcje list wyboru buduje 07_categories.js, który przy ładowaniu wymaga
    // formularzy z innych zakładek — tu wystarczą proste odpowiedniki.
    globalThis.getDestAccountOptionsHtml = () => '';
    globalThis.getContractorOptionsHtml = () => '';
    globalThis.getCategoryOptionsHtml = () => '';
});

beforeEach(() => {
    categories = [
        { id: 1, name: 'Zakupy', type: 'expense' },
        { id: 2, name: 'Przelew wewnętrzny', type: 'transfer' },
    ];
    accounts = [
        { id: 1, name: 'Moje ING', bank_name: 'ING', account_number: '45109010140000071219812874', currency: 'PLN' },
        { id: 2, name: 'Wakacje', bank_name: 'ING', account_number: '61109010140000071219812222', currency: 'PLN' },
        { id: 3, name: 'Revolut EUR', bank_name: 'Revolut', account_number: '', currency: 'EUR' },
    ];
    contractors = [
        { id: 10, name: 'Biedronka' },
        { id: 21, name: 'Moje konto: Wakacje' },
        { id: 22, name: 'Moje konto: Moje ING' },
    ];
    transactions = [];
});

describe('podzielPoczekalnie', () => {
    it('para z tej samej poczekalni to jeden przelew, wypływ pierwszy', () => {
        const wplyw = noga({ id: 2, account_id: 2, amount: 800, pair_id: 1, cont: 22 });
        const wyplyw = noga({ id: 1, account_id: 1, amount: -800, pair_id: 2 });
        const { przelewy, operacje } = podzielPoczekalnie([wplyw, wyplyw]);
        expect(przelewy).toHaveLength(1);
        expect(przelewy[0].map(t => t.id)).toEqual([1, 2]);
        expect(operacje).toEqual([]);
    });

    it('partner spoza listy albo niewskazujący z powrotem — noga zostaje sama', () => {
        const a = noga({ id: 1, account_id: 1, amount: -800, pair_id: 99 });
        const b = noga({ id: 2, account_id: 2, amount: 800, pair_id: 3, cont: 22 });
        const { przelewy } = podzielPoczekalnie([a, b]);
        expect(przelewy.map(p => p.map(t => t.id))).toEqual([[1], [2]]);
    });

    it('„Rozdziel" pokazuje obie nogi osobno', () => {
        const a = noga({ id: 1, account_id: 1, amount: -800, pair_id: 2, _rozdziel: true });
        const b = noga({ id: 2, account_id: 2, amount: 800, pair_id: 1, cont: 22, _rozdziel: true });
        expect(podzielPoczekalnie([a, b]).przelewy).toHaveLength(2);
    });

    it('noga, której kategorię zmieniono na zwykłą, trafia do operacji swojego konta', () => {
        const t = noga({ id: 1, account_id: 1, amount: -800, pair: 'mirror' });
        t.proposed_category = 'Zakupy';
        const { przelewy, operacje } = podzielPoczekalnie([t]);
        expect(przelewy).toEqual([]);
        expect(operacje.map(o => o.id)).toEqual([1]);
    });

    it('nic nie ginie: każdy wiersz trafia dokładnie w jedno miejsce', () => {
        const lista = [
            noga({ id: 1, account_id: 1, amount: -800, pair_id: 2 }),
            noga({ id: 2, account_id: 2, amount: 800, pair_id: 1, cont: 22 }),
            noga({ id: 3, account_id: 1, amount: -50, pair: 'missing' }),
            stg({ id: 4 }),
            stg({ id: 5, account_id: 2, amount: 120, proposed_category: '' }),
        ];
        const { przelewy, operacje } = podzielPoczekalnie(lista);
        const ids = [...przelewy.flat(), ...operacje].map(t => t.id).sort();
        expect(ids).toEqual([1, 2, 3, 4, 5]);
    });
});

describe('grupujPoKontach', () => {
    it('kolejność kont jak w słowniku, wiersz bez znanego konta na końcu', () => {
        const grupy = grupujPoKontach([stg({ id: 1, account_id: 2 }), stg({ id: 2, account_id: null }), stg({ id: 3, account_id: 1 })]);
        expect(grupy.map(([konto, wiersze]) => [konto, wiersze.map(t => t.id)])).toEqual([[1, [3]], [2, [1]], [null, [2]]]);
    });
});

describe('statusPozycji', () => {
    it('kompletna operacja jest gotowa, bez kontrahenta — do uzupełnienia', () => {
        expect(statusPozycji([stg({ id: 1 })])).toBe('ready');
        expect(statusPozycji([stg({ id: 1, proposed_contractor_id: null })])).toBe('todo');
    });

    it('możliwy duplikat nie jest gotowy, dopóki użytkownik go nie rozstrzygnie', () => {
        const t = stg({ id: 1, duplicate_candidates: [{ id: 7, origin: 'manual', days_diff: 0 }] });
        expect(statusPozycji([t])).toBe('dup');
        t._nie_duplikat = true;
        expect(statusPozycji([t])).toBe('ready');
    });

    it('lustro na koncie nogi przelewu nie jest duplikatem — zatwierdzenie je zastąpi', () => {
        const t = noga({ id: 1, account_id: 2, amount: 800, pair: 'booked', cont: 22,
                         duplicate_candidates: [{ id: 7, origin: 'mirror', days_diff: 1 }] });
        expect(statusPozycji([t])).toBe('ready');
    });

    it('przelew bez drugiej strony da się zatwierdzić — brak to ostrzeżenie, nie blokada', () => {
        expect(statusPozycji([noga({ id: 1, account_id: 1, amount: -50, pair: 'missing' })])).toBe('ready');
    });
});

describe('licznikiFiltrow', () => {
    it('para liczy się jako jeden wiersz, a przelewy osobno', () => {
        const { przelewy, operacje } = podzielPoczekalnie([
            noga({ id: 1, account_id: 1, amount: -800, pair_id: 2 }),
            noga({ id: 2, account_id: 2, amount: 800, pair_id: 1, cont: 22 }),
            stg({ id: 3 }),
            stg({ id: 4, proposed_category: '' }),
            stg({ id: 5, duplicate_candidates: [{ id: 9, origin: 'manual', days_diff: 2 }] }),
        ]);
        expect(licznikiFiltrow(przelewy, operacje)).toEqual({ all: 4, ready: 2, todo: 1, dup: 1, transfer: 1 });
    });
});

describe('etykietaKierunku', () => {
    it('wypływ wskazuje konto docelowe, wpływ — źródłowe', () => {
        expect(etykietaKierunku(stg({ id: 1, amount: -800 }))).toBe('Na konto');
        expect(etykietaKierunku(stg({ id: 1, amount: 800 }))).toBe('Z konta');
    });
});

describe('opisDrugiejStrony', () => {
    it('para: obie operacje w tym imporcie', () => {
        const para = podzielPoczekalnie([
            noga({ id: 1, account_id: 1, amount: -800, pair_id: 2 }),
            noga({ id: 2, account_id: 2, amount: 800, pair_id: 1, cont: 22 }),
        ]).przelewy[0];
        expect(opisDrugiejStrony(para).glowne).toBe('Obie operacje są w tym imporcie');
    });

    it('brak drugiej strony mówi, z którego konta zaimportować wyciąg', () => {
        const opis = opisDrugiejStrony([noga({ id: 1, account_id: 1, amount: -50, pair: 'missing' })]);
        expect(opis.klasa).toBe('bad');
        expect(opis.glowne).toBe('Brak — zaimportuj wyciąg z konta Wakacje');
    });

    it('lustro: dopisze ją aplikacja, z nazwą konta', () => {
        const opis = opisDrugiejStrony([noga({ id: 1, account_id: 1, amount: -50, pair: 'mirror' })]);
        expect(opis.glowne).toBe('Dopisze ją aplikacja');
        expect(opis.opis).toContain('Wakacje');
    });

    it('konto zmienione w tej sesji: stan ustali zatwierdzenie, nie stary stan z serwera', () => {
        const t = noga({ id: 1, account_id: 1, amount: -50, pair: 'missing', _dest_account_id: '3' });
        expect(opisDrugiejStrony([t]).klasa).toBe('info');
    });
});

describe('kwotaPrzelewu', () => {
    it('para w jednej walucie — jedna kwota', () => {
        const para = [noga({ id: 1, account_id: 1, amount: -800 }), noga({ id: 2, account_id: 2, amount: 800 })];
        expect(kwotaPrzelewu(para)).toBe('800,00 PLN');
    });

    it('wymiana walut — dwie kwoty w walutach kont', () => {
        const para = [noga({ id: 1, account_id: 1, amount: -430 }), noga({ id: 2, account_id: 3, amount: 100 })];
        expect(kwotaPrzelewu(para)).toBe('430,00 PLN → 100,00 EUR');
    });
});

describe('oknoDuplikatu', () => {
    it('tylko konto wiersza i dokładnie ±4 dni, kandydaci w kolejności z serwera', () => {
        transactions = [
            { id: 1, account_id: 1, date: '2026-09-21', amount: -23.4 },  // 5 dni wcześniej — poza
            { id: 2, account_id: 1, date: '2026-09-22', amount: -23.4 },  // granica okna
            { id: 3, account_id: 1, date: '2026-09-25', amount: -10 },
            { id: 4, account_id: 2, date: '2026-09-26', amount: -23.4 },  // inne konto
            { id: 5, account_id: 1, date: '2026-09-30', amount: -23.4 },  // granica okna
            { id: 6, account_id: 1, date: '2026-10-01', amount: -23.4 },  // 5 dni później — poza
        ];
        const t = stg({ id: 9, account_id: 1, date: '2026-09-26', amount: -23.4,
                        duplicate_candidates: [{ id: 5, days_diff: 4 }, { id: 2, days_diff: 4 }] });
        const okno = oknoDuplikatu(t);
        expect(okno.od).toBe('2026-09-22');
        expect(okno.do).toBe('2026-09-30');
        expect(okno.wiersze.map(h => h.id)).toEqual([2, 3, 5]);
        expect(okno.kandydaci).toEqual([5, 2]);
    });
});

describe('renderStaging', () => {
    const para = () => [
        noga({ id: 1, account_id: 1, amount: -800, pair_id: 2, title: 'Wakacje' }),
        noga({ id: 2, account_id: 2, amount: 800, pair_id: 1, cont: 22, title: 'Wakacje' }),
    ];
    const wiersze = () => [...document.querySelectorAll('#staging-list tbody > tr')];
    const tekst = () => document.getElementById('staging-list').textContent;

    beforeEach(() => {
        zbudujDom();
        stagingFilter = 'all';
        globalThis.showToast = vi.fn();
    });

    it('para to jeden wiersz z „Zatwierdź obie", a licznik w menu liczy obie operacje', () => {
        pendingStaging = [...para(), stg({ id: 3 })];
        renderStaging();
        expect(wiersze()).toHaveLength(2);
        expect(tekst()).toContain('Zatwierdź obie');
        expect(document.getElementById('staging-badge').innerText).toBe(3);
        expect(document.getElementById('sf-count-all').textContent).toBe('2');
        expect(document.getElementById('staging-summary').textContent).toBe('Na zatwierdzenie czekają 3 operacje z 2 kont.');
    });

    it('„To nie przelew" przenosi operację do grupy jej konta, bez kontrahenta „Moje konto"', () => {
        pendingStaging = [noga({ id: 1, account_id: 1, amount: -50, pair: 'mirror', title: 'Kino' })];
        renderStaging();
        toNiePrzelew(1);
        expect(tekst()).not.toContain('Przelewy między Twoimi kontami');
        expect(tekst()).toContain('Moje ING');
        expect(tekst()).toContain('Uzupełnij kontrahenta i kategorię');
        expect(pendingStaging[0].proposed_contractor_id).toBe('');
    });

    it('możliwy duplikat nie liczy się do „Zatwierdź gotowe"', () => {
        pendingStaging = [stg({ id: 1 }), stg({ id: 2, duplicate_candidates: [{ id: 9, origin: 'manual', days_diff: 0 }] })];
        renderStaging();
        expect(document.getElementById('approve-all-btn').textContent).toBe('Zatwierdź gotowe (1)');
    });

    it('tytuł z banku trafia na stronę jako tekst, nie HTML', () => {
        pendingStaging = [stg({ id: 1, title: '<img src=x onerror=alert(1)>' })];
        renderStaging();
        expect(document.querySelector('#staging-list img')).toBeNull();
    });
});

describe('pliki poczekalni', () => {
    it('liczy wiersze per plik i pomija wiersze bez pliku', () => {
        const lista = [
            stg({ id: 1, import_batch_id: 'a', import_filename: 'ing.csv' }),
            stg({ id: 2, import_batch_id: 'a', import_filename: 'ing.csv' }),
            stg({ id: 3, import_batch_id: 'b', import_filename: 'mbank.html' }),
            stg({ id: 4 }),
        ];
        expect(plikiPoczekalni(lista)).toEqual([
            { id: 'a', nazwa: 'ing.csv', liczba: 2 },
            { id: 'b', nazwa: 'mbank.html', liczba: 1 },
        ]);
    });

    it('pasek plików pojawia się dopiero przy dwóch źródłach', () => {
        pendingStaging = [stg({ id: 1, import_batch_id: 'a', import_filename: 'ing.csv' })];
        renderStaging();
        expect(document.getElementById('staging-list').textContent).not.toContain('Odrzuć plik');

        pendingStaging.push(stg({ id: 2 }));
        renderStaging();
        expect(document.getElementById('staging-list').textContent).toContain('Odrzuć plik');
    });

    it('nazwa pliku trafia na stronę jako tekst, nie HTML', () => {
        pendingStaging = [stg({ id: 1, import_batch_id: 'a', import_filename: '<img src=x>' }), stg({ id: 2 })];
        renderStaging();
        expect(document.querySelector('#staging-list img')).toBeNull();
    });
});

describe('zgodność z base.html', () => {
    it('każdy element, którego dotyka renderStaging, istnieje w szablonie', () => {
        const szablon = readFileSync('app/templates/base.html', 'utf-8');
        expect(ID_STRONY.filter(id => !szablon.includes(`id="${id}"`))).toEqual([]);
    });
});