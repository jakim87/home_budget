// Kalkulator kredytu (/kalkulator-kredytu) — liczy wylacznie w przegladarce,
// wiec cala matematyka jest pokryta tutaj, nie w pytest.
//
// Punkt odniesienia to prawdziwy kredyt hipoteczny z Pekao (raty rowne,
// odsetki = saldo * stopa / 12): wzor ma odtworzyc raty banku co do kilku groszy.

import { beforeAll, describe, expect, it } from 'vitest';
import { zaladujModuly } from './helpers.js';

beforeAll(() => {
    zaladujModuly('kalkulator_kredytu.js');
});

const suma = (raty, pole) => Math.round(raty.reduce((s, r) => s + r[pole], 0) * 100) / 100;

describe('raty rowne', () => {
    it('odtwarza rate banku z harmonogramu Pekao (2016 i 2026)', () => {
        // saldo i stopa po zmianie oprocentowania, pozostaly okres; rata z wyciagu banku
        expect(harmonogram({ kwota: 272486.37, miesiace: 359, oprocentowanie: 3.18 }).raty[0].rata)
            .toBeCloseTo(1177.40, 1);
        const plan = harmonogram({ kwota: 17306.50, miesiace: 13, oprocentowanie: 5.27 });
        expect(Math.abs(plan.raty[0].rata - 1372.50)).toBeLessThanOrEqual(0.10);
        // bank: rata 1372,50 - spadek kapitalu 1296,49 = 76,01 zl (zawiera zaokraglenie raty)
        expect(plan.raty[0].odsetki).toBeCloseTo(76.01, 1);
    });

    it('splaca dokladnie kwote kredytu i konczy saldem zero', () => {
        const { raty } = harmonogram({ kwota: 273500, miesiace: 360, oprocentowanie: 4.18 });
        expect(raty).toHaveLength(360);
        expect(suma(raty, 'kapital')).toBe(273500);
        expect(raty.at(-1).saldo).toBe(0);
    });

    it('przy zerowym oprocentowaniu dzieli kwote po rowno', () => {
        const { raty, sumaOdsetek } = harmonogram({ kwota: 1200, miesiace: 12, oprocentowanie: 0 });
        expect(raty.every(r => r.rata === 100)).toBe(true);
        expect(sumaOdsetek).toBe(0);
    });
});

describe('raty malejace', () => {
    it('stala czesc kapitalowa, malejaca rata, mniej odsetek niz przy rownych', () => {
        const param = { kwota: 300000, miesiace: 300, oprocentowanie: 7 };
        const malejace = harmonogram({ ...param, rodzaj: 'malejace' });
        expect(malejace.raty[0].kapital).toBe(1000);
        expect(malejace.raty[0].rata).toBeGreaterThan(malejace.raty[1].rata);
        expect(suma(malejace.raty, 'kapital')).toBe(300000);
        expect(malejace.sumaOdsetek).toBeLessThan(harmonogram(param).sumaOdsetek);
    });
});

describe('nadplaty', () => {
    const param = { kwota: 200000, miesiace: 240, oprocentowanie: 6, nadplatyJednorazowe: [{ miesiac: 12, kwota: 50000 }] };

    it('tryb "okres" zostawia rate i skraca kredyt', () => {
        const bazowy = harmonogram({ ...param, nadplatyJednorazowe: [] });
        const plan = harmonogram({ ...param, trybNadplaty: 'okres' });
        expect(plan.raty[20].rata).toBe(bazowy.raty[20].rata);
        expect(plan.raty.length).toBeLessThan(240);
        expect(plan.sumaNadplat).toBe(50000);
        expect(plan.sumaOdsetek).toBeLessThan(bazowy.sumaOdsetek);
    });

    it('tryb "rata" zostawia okres i obniza rate', () => {
        const plan = harmonogram({ ...param, trybNadplaty: 'rata' });
        expect(plan.raty).toHaveLength(240);
        expect(plan.raty[12].rata).toBeLessThan(plan.raty[11].rata);
        expect(plan.raty.at(-1).saldo).toBe(0);
    });

    it('nadplata cykliczna nie przekracza salda', () => {
        const plan = harmonogram({ kwota: 10000, miesiace: 120, oprocentowanie: 5, nadplataMiesieczna: 3000 });
        expect(plan.raty.at(-1).saldo).toBe(0);
        expect(suma(plan.raty, 'kapital') + plan.sumaNadplat).toBeCloseTo(10000, 2);
    });
});

describe('RRSO i koszt calkowity', () => {
    it('bez oplat RRSO to efektywna stopa roczna', () => {
        const wynik = policzKredyt({ kwota: 300000, miesiace: 300, oprocentowanie: 7 });
        expect(wynik.rrso).toBeCloseTo((Math.pow(1 + 0.07 / 12, 12) - 1) * 100, 1);
    });

    it('prowizja i oplaty miesieczne podnosza RRSO i koszt', () => {
        const bez = policzKredyt({ kwota: 300000, miesiace: 300, oprocentowanie: 7 });
        const z = policzKredyt({ kwota: 300000, miesiace: 300, oprocentowanie: 7, prowizjaProcent: 2, oplataMiesieczna: 50 });
        expect(z.prowizja).toBe(6000);
        expect(z.rrso).toBeGreaterThan(bez.rrso);
        expect(z.kosztCalkowity).toBeCloseTo(bez.kosztCalkowity + 6000 + 50 * 300, 2);
    });

    it('prowizja doliczona do kredytu powieksza kwote, od ktorej licza sie odsetki', () => {
        const wynik = policzKredyt({ kwota: 100000, miesiace: 120, oprocentowanie: 6, prowizjaProcent: 3, prowizjaKredytowana: true });
        expect(suma(wynik.plan.raty, 'kapital')).toBe(103000);
    });

    it('do oddania bankowi = suma rat i nadplat (kapital + odsetki)', () => {
        const wynik = policzKredyt({ kwota: 200000, miesiace: 240, oprocentowanie: 6, prowizjaProcent: 2,
            prowizjaKredytowana: true, nadplatyJednorazowe: [{ miesiac: 12, kwota: 30000 }] });
        expect(wynik.doOddania).toBeCloseTo(suma(wynik.plan.raty, 'rata') + wynik.plan.sumaNadplat, 2);
        expect(wynik.doOddania).toBeCloseTo(204000 + wynik.plan.sumaOdsetek, 2);
    });

    it('test stop pokazuje wyzsza rate przy wyzszym oprocentowaniu', () => {
        const { testStop } = policzKredyt({ kwota: 300000, miesiace: 300, oprocentowanie: 7 });
        expect(testStop.map(t => t.oprocentowanie)).toEqual([8, 9, 10]);
        expect(testStop[2].rata).toBeGreaterThan(testStop[0].rata);
    });
});

describe('okres slownie', () => {
    it('odmienia lata i miesiace', () => {
        expect(okresSlownie(12)).toBe('1 rok');
        expect(okresSlownie(55)).toBe('4 lata 7 miesięcy');
        expect(okresSlownie(300)).toBe('25 lat');
        expect(okresSlownie(158)).toBe('13 lat 2 miesiące');
        expect(okresSlownie(1)).toBe('1 miesiąc');
    });
});

describe('miesiac raty', () => {
    it('liczy miesiac kolejnej raty przez granice roku', () => {
        expect(miesiacRaty('2015-12', 1)).toBe('12.2015');
        expect(miesiacRaty('2015-12', 2)).toBe('01.2016');
        expect(miesiacRaty('2026-10', 360)).toBe('09.2056');
    });
});
