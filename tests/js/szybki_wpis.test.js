// Szybki wpis transakcji: rozkład jednej linii tekstu na pola formularza i podpowiedzi.
//
// To jedyne miejsce, w którym aplikacja zgaduje kwotę, datę i konto z tekstu — błąd
// tutaj zapisuje transakcję na złe konto albo z dnia, którego nikt nie wpisał.
// Dlatego każda reguła z planu (docs/plany/poprawka-wizualna-aplikacji.md, sekcja 2)
// ma tu swój przypadek.

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { tx, zaladujModuly } from './helpers.js';

const DZIS = new Date(2026, 9, 18);  // 18 października 2026, czas lokalny

beforeAll(() => {
    document.body.innerHTML = '<form id="contractor-form"></form>';
    zaladujModuly('01_state.js', '04_helpers.js', '10_contractors.js', '21_szybki_wpis.js');
});

beforeEach(() => {
    accounts = [
        { id: 1, name: 'Konto osobiste', is_default: true },
        { id: 2, name: 'Konto oszczędnościowe' },
        { id: 3, name: 'Karta kredytowa' },
        { id: 4, name: 'Gotówka' },
    ];
    categories = [
        { id: 1, name: 'Zakupy spożywcze', type: 'expense' },
        { id: 2, name: 'Paliwo', type: 'expense' },
        { id: 3, name: 'Wynagrodzenie', type: 'income' },
        { id: 4, name: 'Przelew wewnętrzny', type: 'transfer' },
        { id: 5, name: 'Uzgadnianie salda', type: 'system_reconciliation', is_system_category: true },
    ];
    contractors = [
        { id: 10, name: 'Biedronka', rules: 'biedronka, jeronimo martins', default_category_name: 'Zakupy spożywcze' },
        { id: 11, name: 'Bielenda', rules: '', default_category_name: 'Zakupy spożywcze' },
        { id: 12, name: 'Żabka', rules: 'zabka', default_category_name: 'Zakupy spożywcze' },
        { id: 13, name: 'Orlen', rules: 'orlen', default_category_name: 'Paliwo' },
        { id: 14, name: 'Pracodawca sp. z o.o.', rules: 'pensja, wynagrodzenie', default_category_name: 'Wynagrodzenie' },
        { id: 15, name: 'Moje konto: Gotówka', rules: '', default_category_name: 'Przelew wewnętrzny' },
    ];
});

describe('dopasujKontrahenta (wspólne dla formularzy)', () => {
    it('znajduje po nazwie zawartej w tekście i po regule', () => {
        expect(dopasujKontrahenta('zakupy BIEDRONKA 4021').id).toBe(10);
        expect(dopasujKontrahenta('JERONIMO MARTINS POLSKA').id).toBe(10);
    });

    it('nie rozróżnia polskich znaków', () => {
        expect(dopasujKontrahenta('zabka z7481').id).toBe(12);
        expect(dopasujKontrahenta('ŻABKA').id).toBe(12);
    });

    it('krótki tekst niczego nie dopasowuje', () => {
        expect(dopasujKontrahenta('b')).toBeNull();
        expect(dopasujKontrahenta('nic takiego')).toBeNull();
    });

    it('handleAutoFill nadal ustawia kontrahenta i kategorię', () => {
        document.body.innerHTML += '<input id="k"><input id="k-input"><select id="c"><option>Zakupy spożywcze</option><option>Paliwo</option></select>';
        const k = document.getElementById('k'), c = document.getElementById('c');
        c.value = 'Zakupy spożywcze';
        handleAutoFill('tankowanie ORLEN', k, c);
        expect(k.value).toBe('13');
        expect(document.getElementById('k-input').value).toBe('Orlen');
        expect(c.value).toBe('Paliwo');
    });
});

describe('rozlozWpis', () => {
    const r = (tekst) => rozlozWpis(tekst, DZIS);

    it('kontrahent, kwota z przecinkiem i data słowem', () => {
        const p = r('Biedronka 85,60 wczoraj');
        expect(p.kwota).toBe(85.6);
        expect(p.data).toBe('2026-10-17');
        expect(p.kontrahent.id).toBe(10);
        expect(p.kategoria).toBe('Zakupy spożywcze');
        expect(p.nazwa).toBe('Biedronka');
    });

    it('sama kategoria bez kontrahenta; bez daty = brak daty (formularz wstawi dziś)', () => {
        const p = r('paliwo 235.6');
        expect(p.kwota).toBe(235.6);
        expect(p.kontrahent).toBeNull();
        expect(p.kategoria).toBe('Paliwo');
        expect(p.data).toBeNull();
    });

    it('samo 12.10 to kwota, a nie data', () => {
        const p = r('Orlen 12.10');
        expect(p.kwota).toBe(12.1);
        expect(p.data).toBeNull();
    });

    it('liczba z kropką obok osobnej kwoty to data; przyszła data cofa się o rok', () => {
        expect(r('Orlen 43 9.10').data).toBe('2026-10-09');
        expect(r('Orlen 43 9.10').kwota).toBe(43);
        expect(r('Orlen 43 25.12').data).toBe('2025-12-25');
        expect(r('Orlen 43 31.02').data).toBeNull();  // nie ma takiego dnia
    });

    it('@konto wskazuje konto, gdy fragment jest jednoznaczny', () => {
        expect(r('Orlen 240 @karta').konto.id).toBe(3);
        expect(r('Orlen 240 @konto').konto).toBeNull();   // pasuje do dwóch kont
        expect(r('Orlen 240 @gotowka').konto.id).toBe(4);  // bez polskich znaków
        expect(r('Orlen 240 @karta').nazwa).toBe('Orlen');
    });

    it('>konto to przelew własny z pierwszą kategorią typu przelew', () => {
        const p = r('>oszcz 500');
        expect(p.docelowe.id).toBe(2);
        expect(p.kategoria).toBe('Przelew wewnętrzny');
        expect(p.kontrahent).toBeNull();
        expect(p.kwota).toBe(500);
    });

    it('nieznany kontrahent zostaje tekstem nazwy bez kontrahenta i kategorii', () => {
        const p = r('Nowy sklep 12');
        expect(p.nazwa).toBe('Nowy sklep');
        expect(p.kontrahent).toBeNull();
        expect(p.kategoria).toBeNull();
    });

    it('kategorie systemowe i przelewy nie podpowiadają się jako kategoria tekstu', () => {
        expect(r('uzgadnianie 10').kategoria).toBeNull();
        expect(r('przelew 10').kategoria).toBeNull();
    });
});

describe('tytulWpisu (decyzja T1)', () => {
    it('tekst nazwy, a gdy pusty — nazwa kategorii', () => {
        expect(tytulWpisu(rozlozWpis('Biedronka 85,60', DZIS), 'Zakupy spożywcze')).toBe('Biedronka');
        expect(tytulWpisu(rozlozWpis('>oszcz 500', DZIS), 'Przelew wewnętrzny')).toBe('Przelew wewnętrzny');
    });
});

describe('sugestieWpisu', () => {
    const nazwy = (tekst) => sugestieWpisu(tekst, 1).map(s => s.nazwa);

    it('po pierwszych literach: kontrahenci, potem kategorie; bez kont „Moje konto"', () => {
        expect(nazwy('bi')).toEqual(['Biedronka', 'Bielenda']);
        expect(nazwy('pa')).toEqual(['Paliwo']);
        expect(nazwy('moje')).not.toContain('Moje konto: Gotówka');
    });

    it('nieznana nazwa (min. 3 znaki) dostaje pozycję „Dodaj kontrahenta" (decyzja T2)', () => {
        expect(nazwy('Nowy sklep')).toEqual(['Dodaj kontrahenta „Nowy sklep”']);
        expect(sugestieWpisu('Nowy sklep', 1)[0].typ).toBe('nowy');
    });

    it('nie podpowiada po spacji ani po pełnej nazwie', () => {
        expect(nazwy('bi ')).toEqual([]);
        expect(nazwy('Biedronka')).toEqual([]);
    });

    it('po „>" lista kont bez konta źródłowego, po „@" wszystkie', () => {
        expect(nazwy('>')).toEqual(['Konto oszczędnościowe', 'Karta kredytowa', 'Gotówka']);
        expect(nazwy('orlen 240 @')).toHaveLength(4);
        expect(nazwy('>k')).toEqual(['Konto oszczędnościowe', 'Karta kredytowa']);
    });
});

describe('najczestsiKontrahenci (decyzja T12)', () => {
    it('pięciu z największą liczbą transakcji z 90 dni, bez „Moje konto"', () => {
        transactions = [
            ...[1, 2, 3].map(i => ({ ...tx({ id: i, date: '2026-10-01' }), contractor_id: 13 })),
            ...[4, 5].map(i => ({ ...tx({ id: i, date: '2026-09-01' }), contractor_id: 10 })),
            ...[6, 7, 8, 9].map(i => ({ ...tx({ id: i, date: '2026-10-02' }), contractor_id: 15 })),
            ...[10, 11, 12, 13, 14, 15].map(i => ({ ...tx({ id: i, date: '2026-06-01' }), contractor_id: 12 })),  // starsze niż 90 dni
        ];
        expect(najczestsiKontrahenci(DZIS).map(c => c.name)).toEqual(['Orlen', 'Biedronka']);
    });
});

// Przebieg w formularzu: fragment formularza wziety wprost z base.html, wiec test pilnuje
// tez, zeby id uzywane przez 21_szybki_wpis.js istnialy w szablonie.
describe('formularz z szybkim wpisem', () => {
    beforeEach(async () => {
        const { readFileSync } = await import('node:fs');
        const szablon = readFileSync('app/templates/base.html', 'utf-8');
        const formularz = szablon.match(/<form id="transaction-form"[\s\S]*?<\/form>/)[0];
        document.body.innerHTML = '<form id="category-form"><input id="cat-name"><select id="cat-type"></select></form>' + formularz;
        zaladujModuly('07_categories.js');
        updateCategorySelects();
        updateAccountSelects();
        initSzybkiWpis();
    });

    const q = () => document.getElementById('tx-desc');
    const wpisz = (tekst) => { q().value = tekst; q().dispatchEvent(new Event('input')); };
    const klawisz = (key) => q().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));

    it('Tab dokańcza kontrahenta, a pola pokazują rozpoznany wpis', () => {
        q().focus();
        wpisz('bi');
        expect(document.getElementById('tx-quick-ghost').textContent).toContain('edronka');
        klawisz('Tab');
        expect(q().value).toBe('Biedronka ');
        wpisz('Biedronka 85,60 wczoraj');
        expect(document.getElementById('tx-amount').value).toBe('85.60');
        expect(document.getElementById('tx-contractor').value).toBe('10');
        expect(document.getElementById('tx-category').value).toBe('Zakupy spożywcze');
        expect(document.getElementById('tx-account').value).toBe('1');
        expect(document.getElementById('tx-quick-summary').textContent).toContain('−85,60 PLN · Biedronka');
    });

    it('wybór konta po „>" zostawia w tekście znacznik konta i ustawia przelew', () => {
        q().focus();
        wpisz('500 >k');
        klawisz('ArrowDown');
        klawisz('Tab');
        // Znacznik zostaje widoczny — bez niego wybór wyglądał jak wyczyszczenie wpisu.
        expect(q().value).toBe('500 >Karta kredytowa ');
        expect(document.getElementById('tx-category').value).toBe('Przelew wewnętrzny');
        expect(document.getElementById('tx-dest-account').value).toBe('3');
        expect(document.getElementById('tx-amount').value).toBe('500.00');
        expect(document.getElementById('tx-quick-ghost').textContent).toContain('data');
    });

    it('pełna nazwa konta ze spacjami: wybór z listy i rozpoznanie najdłuższej pasującej nazwy', () => {
        accounts.push({ id: 5, name: 'Poduszka Finansowa' }, { id: 6, name: 'Konto osobiste 2' });
        q().focus();
        wpisz('>pod');
        klawisz('Tab');
        expect(q().value).toBe('>Poduszka Finansowa ');
        wpisz('>Poduszka Finansowa 300');
        expect(document.getElementById('tx-dest-account').value).toBe('5');
        expect(document.getElementById('tx-amount').value).toBe('300.00');
        expect(rozlozWpis('>Poduszka Finansowa 300').nazwa).toBe('');      // słowa nazwy konta nie trafiają do tytułu
        expect(rozlozWpis('@Konto osobiste 2 50').konto.id).toBe(6);         // najdłuższa pasująca nazwa
        expect(rozlozWpis('@Konto osobiste 50').konto.id).toBe(1);           // dokładna nazwa wygrywa z prefiksem
        expect(rozlozWpis('@Konto osobiste 50').kwota).toBe(50);
    });

    it('wyczyszczenie pola zdejmuje rozpoznane wartości, ręczne zostają', () => {
        wpisz('Orlen 240');
        document.getElementById('tx-comment').value = 'x';
        wpisz('');
        expect(document.getElementById('tx-amount').value).toBe('');
        expect(document.getElementById('tx-category').value).toBe('');
    });

    it('nazwa kontrahenta z kodem HTML trafia na listę jako tekst', () => {
        contractors.push({ id: 99, name: 'Bi<img src=x onerror=alert(1)>', rules: '' });
        q().focus();
        wpisz('bi');
        expect(document.querySelector('#tx-quick-sugg img')).toBeNull();
        expect(document.getElementById('tx-quick-sugg').textContent).toContain('<img');
    });
});

describe('panel szybkiego wpisu na telefonie', () => {
    beforeEach(async () => {
        const { readFileSync } = await import('node:fs');
        const szablon = readFileSync('app/templates/base.html', 'utf-8');
        const formularz = szablon.match(/<form id="transaction-form"[\s\S]*?<\/form>/)[0];
        const panel = szablon.match(/<button type="button" id="tx-fab"[\s\S]*?<div id="tx-sheet-body"><\/div>\s*<\/div>/)[0];
        document.body.innerHTML = '<form id="category-form"><input id="cat-name"><select id="cat-type"></select></form>'
            + panel + `<div id="tab-transactions"><div id="tx-form-card">${formularz}</div></div>`;
        window.matchMedia = () => ({ matches: true });  // urządzenie dotykowe
        zaladujModuly('07_categories.js');
        updateCategorySelects();
        updateAccountSelects();
        initSzybkiWpis();
    });
    afterEach(() => { delete window.matchMedia; });

    it('„+" przenosi ten sam formularz do panelu, a zamknięcie oddaje go zakładce', () => {
        document.getElementById('tx-fab').click();
        expect(document.getElementById('tx-sheet-body').contains(document.getElementById('transaction-form'))).toBe(true);
        expect(document.querySelectorAll('#transaction-form')).toHaveLength(1);
        expect(document.activeElement.id).toBe('tx-desc');

        document.getElementById('tx-sheet-zamknij').click();
        expect(document.getElementById('tab-transactions').contains(document.getElementById('transaction-form'))).toBe(true);
        expect(document.getElementById('tx-sheet').classList.contains('hidden')).toBe(true);
    });

    it('po zapisie panel się zamyka, a z „Zachowaj" zostaje otwarty', () => {
        document.getElementById('tx-fab').click();
        document.getElementById('tx-quick-sticky').checked = true;
        poZapisieSzybkiegoWpisu();
        expect(panelWpisuOtwarty()).toBe(true);
        document.getElementById('tx-quick-sticky').checked = false;
        poZapisieSzybkiegoWpisu();
        expect(panelWpisuOtwarty()).toBe(false);
    });

    it('„+" nie pokazuje się na zakładce Transakcje ani na komputerze', () => {
        odswiezPrzyciskWpisu('dashboard');
        expect(document.getElementById('tx-fab').classList.contains('hidden')).toBe(false);
        odswiezPrzyciskWpisu('transactions');
        expect(document.getElementById('tx-fab').classList.contains('hidden')).toBe(true);
        window.matchMedia = () => ({ matches: false });
        odswiezPrzyciskWpisu('dashboard');
        expect(document.getElementById('tx-fab').classList.contains('hidden')).toBe(true);
    });
});
