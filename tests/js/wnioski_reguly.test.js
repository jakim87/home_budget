// Reguły wniosków (22_wnioski_reguly.js) na danych z makiety: 19 miesięcy historii.
// Sprawdzamy zdarzenia, które makieta pokazuje, i progi, które mają je odsiać.

import { beforeAll, describe, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';
import { DZIS, KATEGORIE, KONTA, zbudujTransakcje } from './wnioski_dane.js';

beforeAll(() => {
    zaladujModuly('04_helpers.js', '22_wnioski_reguly.js');
});

const kursStaly = (kursy = {}) => (waluta, ym) => (waluta === 'PLN' ? 1 : (kursy[waluta] && kursy[waluta][ym]) ?? null);

function przygotuj({ transakcje = zbudujTransakcje().transakcje, konta = KONTA, kurs = kursStaly(), dzis = DZIS } = {}) {
    return wnPrzygotuj({ transakcje, kategorie: KATEGORIE, konta, kurs, dzis });
}
const wnioski = (ym, opcje) => wnWnioskiZa(przygotuj(opcje), ym);
const znajdz = (lista, poczatek) => lista.find(x => x.klucz.startsWith(poczatek));
const klucze = lista => lista.map(x => x.klucz.split('@')[0]);

describe('październik 2026 (jak w makiecie)', () => {
    const w = () => wnioski('2026-10');

    it('liczy wnioski z 6 poprzednich miesięcy', () => {
        expect(w().stan).toBe('ok');
        expect(w().okno).toBe(6);
    });

    it('Media Expert to jednorazowe zdarzenie, a nie trend Elektroniki', () => {
        const { lista } = w();
        const zakup = lista.find(x => x.plakietka === 'jednorazowo' && x.tytul === 'Media Expert');
        expect(zakup).toBeTruthy();
        expect(zakup.kwota).toBe('3 499,00 zł');
        expect(znajdz(lista, 'trend-Elektronika')).toBeUndefined();
    });

    it('bilans wskazuje zakup jako główną przyczynę', () => {
        const bilans = znajdz(w().lista, 'bilans');
        expect(bilans.ton).toBe('gorzej');
        expect(bilans.opis).toContain('Główna przyczyna: Media Expert');
    });

    it('OLX jako dodatkowy wpływ; przychody bez osobnego wniosku, bo wyjaśnia je ten wpływ', () => {
        const { lista } = w();
        expect(lista.find(x => x.plakietka === 'dodatkowy wpływ' && x.tytul === 'OLX')).toBeTruthy();
        expect(znajdz(lista, 'przychody')).toBeUndefined();
    });

    it('podwyżka Netflixa z kwotą w skali roku', () => {
        const netflix = w().lista.find(x => x.klucz.startsWith('zmiana-') && x.tytul === 'Netflix');
        expect(netflix.plakietka).toBe('podwyżka');
        expect(netflix.waga).toBeCloseTo(11 * 12);
    });

    it('restauracje rosnące od 3 miesięcy', () => {
        const r = znajdz(w().lista, 'trend-Restauracje');
        expect(r.ton).toBe('gorzej');
        expect(r.opis).toContain('Rośnie od 3 miesięcy');
    });

    it('wnioski od największej kwoty', () => {
        const wagi = w().lista.map(x => x.waga);
        expect(wagi).toEqual([...wagi].sort((a, b) => b - a));
    });
});

describe('stałe opłaty', () => {
    const cityFit = ym => wnioski(ym).lista.find(x => x.klucz.startsWith('znikla-') && x.tytul === 'CityFit');
    const disney = ym => wnioski(ym).lista.find(x => x.klucz.startsWith('nowa-') && x.tytul === 'Disney+');

    it('CityFit „przestała się pojawiać” dopiero po 2 pustych miesiącach', () => {
        expect(cityFit('2026-09')).toBeUndefined();
        expect(cityFit('2026-10')).toBeTruthy();
    });

    it('Disney+ „nowa” przy 2–3 płatnościach, nie przy pierwszej', () => {
        expect(disney('2026-08')).toBeUndefined();
        expect(disney('2026-09')).toBeTruthy();
        expect(disney('2026-10')).toBeTruthy();
    });

    it('podwyżka czynszu w styczniu', () => {
        const czynsz = wnioski('2026-01').lista.find(x => x.klucz.startsWith('zmiana-') && x.tytul === 'SM Zacisze');
        expect(czynsz.plakietka).toBe('podwyżka');
        expect(czynsz.opis).toContain('40,00');
    });

});

describe('kiedy wniosków nie ma', () => {
    it('bieżący miesiąc trwa', () => {
        expect(wnioski('2026-11')).toEqual({ stan: 'trwa', lista: [] });
    });

    it('historia krótsza niż 3 miesiące', () => {
        expect(wnioski('2025-04').stan).toBe('malo');
        expect(wnioski('2025-06').stan).toBe('malo');
        expect(wnioski('2025-07').stan).toBe('ok');
    });

    it('„pierwszy raz” dopiero od 6 miesięcy historii', () => {
        const wcz = ['2025-07', '2025-08', '2025-09'].flatMap(ym => wnioski(ym).lista);
        expect(wcz.some(x => x.plakietka === 'pierwszy raz')).toBe(false);
        expect(wnioski('2026-10').lista.some(x => x.plakietka === 'pierwszy raz' && x.tytul === 'Gabinet weterynaryjny Azor')).toBe(true);
    });

    it('historia liczy się od pierwszej operacji, nie od uzgodnień salda z migracji', () => {
        // Lata samych uzgodnień salda (migracja historii sald), potem pierwsze wyciągi.
        const uzgodnienia = Array.from({ length: 24 }, (_, k) => ({
            id: 8000 + k, date: `${2023 + Math.floor(k / 12)}-${String(k % 12 + 1).padStart(2, '0')}-28`,
            amount: 100, desc: 'Uzgadnianie salda', category: 'Uzgadnianie salda', account_id: 1,
        }));
        const transakcje = [...uzgodnienia, ...zbudujTransakcje().transakcje];
        expect(wnioski('2025-04', { transakcje }).stan).toBe('malo');
        expect(wnioski('2025-06', { transakcje }).stan).toBe('malo');
        const wczesne = ['2025-07', '2025-08', '2025-09'].flatMap(ym => wnioski(ym, { transakcje }).lista);
        expect(wczesne.some(x => x.plakietka === 'pierwszy raz')).toBe(false);
    });

    it('miesiąc bez żadnej operacji w środku danych to luka, a nie „zero wydatków”', () => {
        // Trzeci miesiąc danych: za wcześnie na regułę „konto nagle bez operacji” (3 miesiące wstecz).
        const transakcje = zbudujTransakcje().transakcje.filter(t => !t.date.startsWith('2025-06'));
        // (konto osobiste łapie też reguła „ułamek zwykłej liczby operacji”, więc lista kont nie jest pusta)
        expect(wnioski('2025-06', { transakcje }).stan).toBe('luka');
        expect(wnioski('2025-07', { transakcje }).stan).toBe('malo');
        expect(wnioski('2025-08', { transakcje })).toMatchObject({ stan: 'ok', okno: 3 });
    });

    it('miesiąc bez wyciągu z konta nie daje wniosków i wypada z okna mediany', () => {
        const transakcje = zbudujTransakcje().transakcje.filter(t => !(t.account_id === 1 && t.date.startsWith('2026-09')));
        expect(wnioski('2026-09', { transakcje })).toMatchObject({ stan: 'luka', konta: [1] });
        expect(wnioski('2026-10', { transakcje }).okno).toBe(5);
    });
});

describe('przelewy, uzgodnienia, gotówka, waluty', () => {
    it('przelewy między własnymi kontami nie zmieniają żadnego wniosku', () => {
        const { transakcje } = zbudujTransakcje();
        const z = [...transakcje,
            { id: 9001, date: '2026-10-05', amount: -50000, desc: 'Na lokatę', category: 'Przelew wewnętrzny', account_id: 1, contractor_id: null },
            { id: 9002, date: '2026-10-05', amount: 50000, desc: 'Na lokatę', category: 'Przelew wewnętrzny', account_id: 2, contractor_id: null }];
        expect(JSON.stringify(wnioski('2026-10', { transakcje: z }))).toBe(JSON.stringify(wnioski('2026-10', { transakcje })));
    });

    it('uzgodnienie salda nie jest wydatkiem, nawet z kategorią wydatkową', () => {
        const { transakcje } = zbudujTransakcje();
        const z = [...transakcje, { id: 9003, date: '2026-10-30', amount: -5000, desc: 'Uzgadnianie salda', category: 'Dom', account_id: 1 }];
        expect(JSON.stringify(wnioski('2026-10', { transakcje: z }))).toBe(JSON.stringify(wnioski('2026-10', { transakcje })));
    });

    it('comiesięczna wypłata gotówki nie wychodzi jako jednorazowy wydatek', () => {
        const { transakcje } = zbudujTransakcje();
        const z = [...transakcje];
        ['2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'].forEach((ym, k) => z.push(
            { id: 9100 + k, date: `${ym}-0${k + 1}`, amount: -1500, desc: 'Wypłata z bankomatu', category: 'Inne', account_id: 1, contractor_name: `Bankomat ${k}` }));
        expect(wnioski('2026-10', { transakcje: z }).lista.some(x => x.tytul === 'Wypłaty gotówki')).toBe(false);
    });

    it('konto w EUR przeliczone po kursie z końca miesiąca; bez kursu wypada jawnie', () => {
        const eur = { id: 20, name: 'Konto EUR', account_type: 'ROR', currency: 'EUR' };
        const t = { id: 9200, date: '2026-10-07', amount: -100, desc: 'Hotel', category: 'Podróże', account_id: 20, contractor_id: 999, contractor_name: 'Hotel' };
        const d = przygotuj({ transakcje: [t], konta: [...KONTA, eur], kurs: kursStaly({ EUR: { '2026-10': 4.3 } }) });
        expect(d.ops[0].kwota).toBe(-430);
        const bez = przygotuj({ transakcje: [t], konta: [...KONTA, eur] });
        expect(bez.ops).toEqual([]);
        expect([...bez.brakKursu]).toEqual(['EUR']);
    });
});

describe('poprawki po symulacji na prawdziwych danych (dane syntetyczne o tym samym kształcie)', () => {
    const bezCzesci = (filtr) => zbudujTransakcje().transakcje.filter(t => !filtr(t));

    it('niepełny import konta (ułamek zwykłej liczby operacji) to luka, a nie miesiąc z niskimi wydatkami', () => {
        // Z sierpnia konta osobistego zostają tylko 3 operacje (zwykle ~25).
        let zostaw = 3;
        const transakcje = bezCzesci(t => t.account_id === 1 && t.date.startsWith('2026-08') && zostaw-- <= 0);
        expect(wnioski('2026-08', { transakcje })).toMatchObject({ stan: 'luka', konta: [1] });
        expect(wnioski('2026-10', { transakcje }).okno).toBe(5);
    });

    it('podwyżka stałej opłaty wychodzi także wtedy, gdy miesiąc wcześniej był luką w imporcie', () => {
        const transakcje = bezCzesci(t => t.date.startsWith('2026-09'));
        const lista = wnioski('2026-10', { transakcje }).lista;
        const netflix = lista.find(x => x.klucz.startsWith('zmiana-') && x.tytul === 'Netflix');
        expect(netflix && netflix.plakietka).toBe('podwyżka');
        expect(netflix.opis).toContain('49,00');
    });

    it('wypłata gotówki nigdy nie jest „jednorazowym zdarzeniem”, a na karcie nie ma nazwy bankomatu', () => {
        const transakcje = [...zbudujTransakcje().transakcje,
            { id: 9300, date: '2026-07-04', amount: -2500, desc: 'Wypłata z bankomatu', category: 'Inne', account_id: 1, contractor_name: 'Bank X bankomat 17' },
            { id: 9301, date: '2026-10-04', amount: -2500, desc: 'Wypłata z bankomatu', category: 'Inne', account_id: 1, contractor_name: 'Bank X bankomat 17' }];
        const lista = wnioski('2026-10', { transakcje }).lista;
        expect(lista.some(x => x.plakietka === 'jednorazowo' && /bankomat|gotówki/i.test(x.tytul))).toBe(false);
        expect(lista.some(x => /Bank X/.test(x.tytul + x.opis))).toBe(false);
    });

    it('przychody wyżej o 8% to szum, o kilkanaście procent — wniosek', () => {
        expect(znajdz(wnioski('2026-07').lista, 'przychody')).toBeUndefined();  // pensja 8400 → 9100
        const transakcje = [...zbudujTransakcje().transakcje,
            { id: 9400, date: '2026-01-20', amount: 1500, desc: 'Premia', category: 'Wynagrodzenie', account_id: 1, contractor_id: zbudujTransakcje().kontrahenci.get('Pracodawca sp. z o.o.'), contractor_name: 'Pracodawca sp. z o.o.' }];
        expect(znajdz(wnioski('2026-01', { transakcje }).lista, 'przychody').ton).toBe('lepiej');
    });

    it('trend od prawie zerowej podstawy bez absurdalnego procentu', () => {
        const transakcje = [...zbudujTransakcje().transakcje];
        ['2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09'].forEach((ym, k) => transakcje.push(
            { id: 9500 + k, date: `${ym}-09`, amount: -10, desc: 'Drobiazg', category: 'Hobby', account_id: 1, contractor_id: 777, contractor_name: 'Sklep hobby' }));
        [0, 1, 2].forEach(k => transakcje.push(
            { id: 9510 + k, date: `2026-10-0${k + 2}`, amount: -150, desc: 'Zakupy', category: 'Hobby', account_id: 1, contractor_id: 777, contractor_name: 'Sklep hobby' }));
        const hobby = znajdz(wnioski('2026-10', { transakcje }).lista, 'trend-Hobby');
        expect(hobby.ton).toBe('gorzej');
        expect(hobby.delta).toBe('');
        expect(hobby.krotko + hobby.opis).not.toMatch(/%|×/);
        expect(hobby.opis).toContain('prawie nic');
    });
});

describe('wspólny format ciekawostki', () => {
    it('każdy wniosek ma pola, których potrzebują karty i belka', () => {
        const lista = ['2026-01', '2026-07', '2026-10'].flatMap(ym => wnioski(ym).lista);
        expect(lista.length).toBeGreaterThan(5);
        lista.forEach(x => {
            expect(x.zrodlo).toBe('miesiac');
            expect(x.krotko.length).toBeLessThanOrEqual(50);
            expect(['gorzej', 'lepiej', 'info']).toContain(x.ton);
            expect(['kategoria', 'kontrahent', 'ogolny']).toContain(x.temat.typ);
            expect(x.pokaz.cfg).toBeTruthy();
            expect(typeof x.waga).toBe('number');
        });
        expect(new Set(lista.map(x => x.klucz)).size).toBe(lista.length);
    });

    it('„Pokaż operacje” wskazuje kategorie i kontrahentów po ID', () => {
        const { lista } = wnioski('2026-10');
        const elektronika = KATEGORIE.find(c => c.name === 'Elektronika').id;
        expect(lista.find(x => x.tytul === 'Media Expert').pokaz.cfg.kategorie).toEqual([elektronika]);
        const { kontrahenci } = zbudujTransakcje();
        expect(lista.find(x => x.tytul === 'Netflix').pokaz.cfg.kontrahenci).toEqual([kontrahenci.get('Netflix')]);
    });

    it('lista WN_REGULY to cztery rodzaje wniosków', () => {
        expect(WN_REGULY).toHaveLength(4);
        const rodzaje = new Set(['2026-01', '2026-07', '2026-10'].flatMap(ym => wnioski(ym).lista.map(x => x.rodzaj)));
        expect([...rodzaje].sort()).toEqual(['Bilans', 'Jednorazowe zdarzenie', 'Stała opłata', 'Trend kategorii']);
    });
});

it('klucze pomocnicze', () => {
    expect(klucze([{ klucz: 'a@2026-10' }])).toEqual(['a']);
});
