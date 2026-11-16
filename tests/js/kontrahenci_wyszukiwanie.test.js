// Wyszukiwarka słownika kontrahentów (filtrujKontrahentow z 04_helpers.js).

import { beforeAll, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';

beforeAll(() => zaladujModuly('01_state.js', '04_helpers.js'));

const LISTA = [
    { id: 1, name: 'Biedronka', rules: 'biedronka, jeronimo', default_category_name: 'Jedzenie' },
    { id: 2, name: 'Żabka', rules: 'zabka', default_category_name: null },
    { id: 3, name: 'Orlen', rules: '', default_category_name: 'Paliwo' },
];

it('pusta fraza zwraca całą listę', () => {
    expect(filtrujKontrahentow(LISTA, '')).toEqual(LISTA);
    expect(filtrujKontrahentow(LISTA, '   ')).toEqual(LISTA);
});

it('szuka po nazwie bez rozróżniania wielkości liter i polskich znaków', () => {
    expect(filtrujKontrahentow(LISTA, 'ZABKA').map(c => c.id)).toEqual([2]);
    expect(filtrujKontrahentow(LISTA, 'żab').map(c => c.id)).toEqual([2]);
});

it('szuka po regułach i po nazwie kategorii', () => {
    expect(filtrujKontrahentow(LISTA, 'jeronimo').map(c => c.id)).toEqual([1]);
    expect(filtrujKontrahentow(LISTA, 'paliwo').map(c => c.id)).toEqual([3]);
});

it('brak trafień daje pustą listę, a kontrahent bez reguł i kategorii nie wywala', () => {
    expect(filtrujKontrahentow(LISTA, 'xyz')).toEqual([]);
    expect(filtrujKontrahentow([{ id: 9, name: 'A' }], 'a').length).toBe(1);
});

const KATEGORIE = [
    { id: 1, name: 'Jedzenie', type: 'expense' },
    { id: 2, name: 'Wypłata', type: 'income' },
    { id: 3, name: 'Przelew wewnętrzny', type: 'transfer' },
];

it('kategorie: szuka po nazwie i po typie, bez rozróżniania polskich znaków', () => {
    expect(filtrujKategorie(KATEGORIE, '')).toEqual(KATEGORIE);
    expect(filtrujKategorie(KATEGORIE, 'wyplata').map(c => c.id)).toEqual([2]);
    expect(filtrujKategorie(KATEGORIE, 'przychód').map(c => c.id)).toEqual([2]);
    expect(filtrujKategorie(KATEGORIE, 'wydatek').map(c => c.id)).toEqual([1]);
    expect(filtrujKategorie(KATEGORIE, 'xyz')).toEqual([]);
});
