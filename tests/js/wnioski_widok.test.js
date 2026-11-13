// Widoki zakładki Wnioski (23_wnioski.js) na prawdziwym fragmencie base.html i danych z makiety.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { htmlWnioskow, zaladujModuly } from './helpers.js';
import { KATEGORIE, KONTA, zbudujTransakcje } from './wnioski_dane.js';

let DANE;
beforeAll(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 10, 1, 12));
    zaladujModuly('01_state.js', '04_helpers.js', '13_dashboard.js', '22_wnioski_reguly.js', '23_wnioski.js');
    globalThis.switchTab = (nazwa) => { if (nazwa === 'wnioski') renderWnioski(); };
    DANE = zbudujTransakcje();
});
afterAll(() => vi.useRealTimers());

beforeEach(() => {
    document.body.innerHTML = htmlWnioskow();
    transactions = DANE.transakcje.map(t => ({ ...t }));
    categories = KATEGORIE;
    accounts = KONTA.map(a => ({ ...a }));
    inactiveAccounts = [];
    contractors = [...DANE.kontrahenci].map(([name, id]) => ({ id, name }));
    savedViews = [];
    currencies = {}; monthlyRates = {};
    wnYm = null; wnAktywnyId = 'w1'; wnCfg = { ...WN_PUSTY }; wnSciezka = []; wnKartaKat = null; wnTabela = 'zestawienie';
    renderWnioski();
});

const kat = nazwa => KATEGORIE.find(c => c.name === nazwa).id;
const sumy = () => wnSumy(wnFiltruj(wnCfg, wnZakres(wnCfg)));
const ustaw = zmiana => { Object.assign(wnCfg, zmiana); renderWidok(); };

it('każdy element, którego szuka 23_wnioski.js, istnieje w base.html', () => {
    const kod = readFileSync(join(process.cwd(), 'app', 'static', 'js', '23_wnioski.js'), 'utf-8');
    const html = htmlWnioskow();
    const ids = [...kod.matchAll(/wn\$\('([a-z0-9-]+)'\)/g)].map(m => m[1]);
    const dynamiczne = ['wn-do-poprz', 'wn-wszystkie', 'wn-zapis-blad', 'wn-nazwa-widoku', 'wn-zapis-anuluj', 'wn-puste', 'wn-karta-wszystkie', 'wn-karta-wykres'];
    ids.filter(id => !dynamiczne.includes(id)).forEach(id => expect(html, id).toContain(`id="${id}"`));
});

it('otwiera się na ostatnim pełnym miesiącu z wnioskami', () => {
    expect(wnYm).toBe('2026-10');
    expect(document.querySelectorAll('#wn-lista .wn-ins').length).toBe(WN_NA_KARCIE);
    expect(document.getElementById('wn-mies-next').disabled).toBe(false);
});

describe('liczby widoku', () => {
    it('„Miesiąc w liczbach” = przychody i wydatki miesiąca bez przelewów (jak Raporty)', () => {
        const oct = transactions.filter(t => t.date.startsWith('2026-10') && t.category !== 'Przelew wewnętrzny');
        const s = sumy();
        expect(s.inc).toBeCloseTo(oct.filter(t => t.amount > 0).reduce((a, t) => a + t.amount, 0));
        expect(s.exp).toBeCloseTo(-oct.filter(t => t.amount < 0).reduce((a, t) => a + t.amount, 0));
    });

    it('filtr kont i „Tylko ulubione” zawężają operacje', () => {
        ustaw({ konta: [3] });
        expect(wnFiltruj(wnCfg, wnZakres(wnCfg)).every(o => o.konto === 3)).toBe(true);
        ustaw({ konta: [], ulubione: true });
        const konta = new Set(wnFiltruj(wnCfg, wnZakres(wnCfg)).map(o => o.konto));
        expect([...konta].every(k => [1, 2, 9].includes(k))).toBe(true);
        expect(konta.has(3)).toBe(false);
    });

    it('„Wszystkie” czyści wybór, w kontach także „Tylko ulubione”', () => {
        ustaw({ konta: [1], ulubione: true });
        const wsz = document.getElementById('wn-wsz-konta');
        expect(wsz.checked).toBe(false);
        wsz.checked = true; wsz.dispatchEvent(new Event('change', { bubbles: true }));
        expect(wnCfg.konta).toEqual([]);
        expect(wnCfg.ulubione).toBe(false);
    });

    it('„Wyklucz” zostawia sumę równą całości minus wykluczony element', () => {
        ustaw({ liczy: 'wydatki' });
        const calosc = sumy().exp;
        const jedzenie = wnSumy(wnFiltruj({ ...wnCfg, kategorie: [kat('Jedzenie')] }, wnZakres(wnCfg))).exp;
        const [, , f] = wnAkcjeDla({ typ: 'kategoria', v: kat('Jedzenie'), nazwa: 'Jedzenie' }, wnZakres(wnCfg)).find(a => a[0] === 'Wyklucz z widoku');
        wnDrill('bez: Jedzenie', { f });
        expect(sumy().exp).toBeCloseTo(calosc - jedzenie);
    });

    it('rozbicie miesiąca przestawia miesiąc zakładki, a ścieżka cofa filtry, tabelę i miesiąc', () => {
        ustaw({ okres: { typ: 'n', n: 6 }, pokaz: 'czas' });
        const przed = JSON.stringify(wnCfg);
        const [, et, f, extra] = wnAkcjeDla({ typ: 'miesiac', v: wnD().idx.get('2026-07') }, wnZakres(wnCfg)).find(a => a[0] === 'Pokaż operacje');
        wnDrill(et, { f, ...extra });
        expect(wnYm).toBe('2026-07');
        expect(wnTabela).toBe('operacje');
        expect(document.getElementById('wn-sciezka').hidden).toBe(false);
        document.querySelector('#wn-sciezka [data-i="0"]').click();
        expect(wnYm).toBe('2026-10');
        expect(JSON.stringify(wnCfg)).toBe(przed);
        expect(wnTabela).toBe('zestawienie');
    });

    it('karta kategorii zgadza się z widokiem „ta kategoria, 12 miesięcy”', () => {
        const id = kat('Restauracje');
        const k = wnDaneKarty(id);
        const widok = wnSumy(wnFiltruj({ ...WN_PUSTY, kategorie: [id], okres: { typ: 'n', n: 12 } }, wnZakres({ okres: { typ: 'n', n: 12 } })));
        expect(k.rok).toBeCloseTo(widok.exp);
        expect(k.ops12.length).toBe(widok.n);
        wnDrill('Karta: Restauracje', { karta: id });
        expect(document.getElementById('wn-karta').hidden).toBe(false);
        expect(document.getElementById('wn-karta').textContent).toContain('Najwięksi kontrahenci');
    });

    it('„Pokaż operacje” we wniosku pokazuje operację, która go tworzy', () => {
        const x = wnWnioskiZa(wnD(), '2026-10').lista.find(w => w.tytul === 'Media Expert');
        wnPokazZWniosku(x);
        expect(wnAktywnyId).toBeNull();
        expect(document.getElementById('wn-tabela').textContent).toContain('Laptop Lenovo IdeaPad');
    });
});

describe('salda kont', () => {
    it('suma sald na koniec miesiąca równa Majątkowi netto z Dashboardu', () => {
        computeNetWorthSeries();
        const i = wnD().idx.get('2026-09');
        const majatek = netWorthSeriesFull.find(p => p.month === '2026-09').value;
        expect(wnSumaSald(accounts, i)).toBeCloseTo(majatek, 1);
    });

    it('przelew wewnętrzny zmienia salda obu kont, a nie ich sumę', () => {
        const i = wnD().idx.get('2026-10');
        const przed = [1, 2].map(id => wnSaldo(id, i));
        transactions = [...transactions,
            { id: 9001, date: '2026-10-30', amount: -500, desc: 'x', category: 'Przelew wewnętrzny', account_id: 1 },
            { id: 9002, date: '2026-10-30', amount: 500, desc: 'x', category: 'Przelew wewnętrzny', account_id: 2 }];
        const po = [1, 2].map(id => wnSaldo(id, i));
        expect(po[0]).toBeCloseTo(przed[0] - 500);
        expect(po[1]).toBeCloseTo(przed[1] + 500);
        expect(po[0] + po[1]).toBeCloseTo(przed[0] + przed[1]);
    });

    it('konto w EUR wycenione po kursie z końca miesiąca, konto zamknięte poza widokiem', () => {
        accounts = [...accounts, { id: 20, name: 'EUR', currency: 'EUR', account_type: 'ROR' }];
        inactiveAccounts = [{ id: 21, name: 'Stare', currency: 'PLN' }];
        transactions = [...transactions,
            { id: 9100, date: '2026-09-03', amount: 100, desc: 'Start', category: 'Uzgadnianie salda', account_id: 20 },
            { id: 9101, date: '2026-09-03', amount: 999, desc: 'Start', category: 'Uzgadnianie salda', account_id: 21 }];
        monthlyRates = { EUR: { '2026-09': 4.25, '2026-10': 4.3 } };
        const eur = accounts.find(a => a.id === 20);
        expect(wnSaldoPLN(eur, wnD().idx.get('2026-09'))).toBeCloseTo(425);
        expect(wnSaldoPLN(eur, wnD().idx.get('2026-10'))).toBeCloseTo(430);
        expect(wnKontaWZakresie(WN_PUSTY).some(a => a.id === 21)).toBe(false);
    });

    it('do 10 kont domyślnie „Wg kont”, przy większej liczbie „Razem” bez opcji „Wg kont”', () => {
        expect(wnTrybSald(WN_PUSTY)).toBe('konta');
        accounts = [...accounts, ...Array.from({ length: 6 }, (_, k) => ({ id: 100 + k, name: `K${k}`, currency: 'PLN' }))];
        expect(wnOpcjeSald(WN_PUSTY)).toEqual(['razem', 'typy']);
        expect(wnTrybSald({ ...WN_PUSTY, sald: 'konta' })).toBe('razem');
        expect(wnOpcjeSald({ ...WN_PUSTY, ulubione: true })).toContain('konta');
    });

    it('suma grup tabeli równa wierszowi „Razem”, konto z zerem przez cały okres ukryte', () => {
        accounts = [...accounts, { id: 30, name: 'Puste', currency: 'PLN' }];
        wnWybierzWidok('w3');
        const tab = document.getElementById('wn-tabela');
        expect(tab.textContent).toContain('Pokaż konta z zerowym saldem (1)');
        expect(tab.textContent).not.toContain('Puste');
        const razem = [...tab.querySelectorAll('tr.wn-sum td')][1].textContent;
        expect(razem).toBe(wnZl2(wnSumaSald(wnKontaWZakresie(wnCfg), wnI())));
    });
});

describe('zapisywanie widoków', () => {
    it('zapis wysyła konfigurację bez filtra dnia, a zapisany widok odtwarza tryb sald i ulubione', async () => {
        const wyslane = [];
        globalThis.fetch = vi.fn(async (url, opcje) => {
            const body = JSON.parse(opcje.body);
            wyslane.push(body);
            return { ok: true, json: async () => ({ id: 5, name: body.name, config: body.config }) };
        });
        wnCfg = { ...WN_PUSTY, pokaz: 'salda', sald: 'typy', ulubione: true, dzien: 4 };
        wnAktywnyId = null;
        renderWidok();
        wnTryb = 'zapis'; renderAkcji();
        await wnZapiszNowy('Moje salda');
        expect(wyslane[0].config.dzien).toBeUndefined();
        expect(savedViews).toHaveLength(1);
        wnWybierzWidok('w1');
        wnWybierzWidok('s5');
        expect(wnCfg.sald).toBe('typy');
        expect(wnCfg.ulubione).toBe(true);
    });

    it('ósmy własny widok odrzucony bez wysyłania', async () => {
        globalThis.fetch = vi.fn();
        savedViews = Array.from({ length: 7 }, (_, k) => ({ id: k + 1, name: `W${k}`, config: {} }));
        wnTryb = 'zapis'; renderAkcji();
        await wnZapiszNowy('Ósmy');
        expect(globalThis.fetch).not.toHaveBeenCalled();
        expect(document.getElementById('wn-zapis-blad').textContent).toContain('Usuń któryś');
    });

    it('usunięty z czasem kontrahent wypada z filtra zapisanego widoku z notką', () => {
        savedViews = [{ id: 1, name: 'Stary', config: { kontrahenci: [99999] } }];
        wnWybierzWidok('s1');
        expect(wnCfg.kontrahenci).toEqual([]);
        expect(document.getElementById('wn-note').textContent).toContain('pominięto');
    });
});

describe('dymek „i” i menu rozbijania', () => {
    it('dymek zamyka kliknięcie obok i Esc', () => {
        document.querySelector('.wn-info-btn').click();
        expect(document.getElementById('wn-info-widoki')).not.toBeNull();
        document.body.click();
        expect(document.getElementById('wn-info-widoki')).toBeNull();
        document.querySelector('.wn-info-btn').click();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(document.getElementById('wn-info-widoki')).toBeNull();
    });

    it('menu otwiera się z przycisku w tabeli, strzałki przechodzą po pozycjach, Esc oddaje fokus', () => {
        const przycisk = document.querySelector('#wn-tabela button.wn-drill');
        przycisk.click();
        const menu = document.getElementById('wn-drill-menu');
        expect(menu.hidden).toBe(false);
        const pozycje = [...menu.querySelectorAll('[role="menuitem"]')];
        expect(document.activeElement).toBe(pozycje[0]);
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
        expect(document.activeElement).toBe(pozycje[1]);
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(menu.hidden).toBe(true);
        expect(document.activeElement).toBe(przycisk);
    });

    it('bez akcji i komunikatu nie ma pustych elementów między chipami a filtrami', () => {
        expect(document.getElementById('wn-akcje').innerHTML).toBe('');
        expect(document.getElementById('wn-note').textContent).toBe('');
    });
});
