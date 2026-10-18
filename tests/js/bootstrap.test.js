// Wejscie z wizytowki: /login?demo=1 i /login?rejestracja=1 obsluguje 99_bootstrap.js.
// To jedyna droga z wizytowki do aplikacji, a pytest tej sciezki nie dotyka.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

function start(adres, { przyciskDemo = true } = {}) {
    document.body.innerHTML = '<input id="tx-date">' + (przyciskDemo ? '<button id="demo-login-btn"></button>' : '');
    window.history.replaceState(null, '', adres);
    zaladujModuly('04_helpers.js', '99_bootstrap.js');
}

beforeEach(() => {
    for (const nazwa of ['initContractorCombobox', 'initSzybkiWpis', 'fetchInitialData', 'loginAsDemo', 'showLoginModal', 'showAuthView']) {
        globalThis[nazwa] = vi.fn();
    }
});

describe('start aplikacji', () => {
    it('bez parametrow pobiera dane i niczego nie otwiera', () => {
        start('/login');
        expect(fetchInitialData).toHaveBeenCalledOnce();
        expect(loginAsDemo).not.toHaveBeenCalled();
        expect(showAuthView).not.toHaveBeenCalled();
    });

    it('?demo=1 loguje na demo bez rownoleglego pobierania danych i czysci adres', () => {
        start('/login?demo=1');
        expect(loginAsDemo).toHaveBeenCalledOnce();
        expect(fetchInitialData).not.toHaveBeenCalled();
        expect(window.location.search).toBe('');
    });

    it('?demo=1 bez przycisku demo (DEMO_ENABLED wylaczone) konczy sie zwyklym startem', () => {
        start('/login?demo=1', { przyciskDemo: false });
        expect(loginAsDemo).not.toHaveBeenCalled();
        expect(fetchInitialData).toHaveBeenCalledOnce();
    });

    it('?rejestracja=1 otwiera widok rejestracji', () => {
        start('/login?rejestracja=1');
        expect(fetchInitialData).toHaveBeenCalledOnce();
        expect(showLoginModal).toHaveBeenCalledOnce();
        expect(showAuthView).toHaveBeenCalledWith('register');
        expect(window.location.search).toBe('');
    });
});

describe('domyslna data w formularzu transakcji', () => {
    // Strefa ustawiona na sztywno: w CI (UTC) blad liczenia daty w UTC bylby niewidoczny.
    const strefa = process.env.TZ;
    beforeEach(() => { process.env.TZ = 'Europe/Warsaw'; });
    afterEach(() => { vi.useRealTimers(); process.env.TZ = strefa; });

    it('tuz po polnocy jest dzisiejsza data lokalna, nie wczorajsza z UTC', () => {
        vi.useFakeTimers({ toFake: ['Date'] });
        vi.setSystemTime(new Date('2026-03-15T23:30:00Z')); // w Warszawie juz 16 marca, 0:30
        start('/login');
        expect(document.getElementById('tx-date').value).toBe('2026-03-16');
    });
});
