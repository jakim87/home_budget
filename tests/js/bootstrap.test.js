// Wejscie z wizytowki: /login?demo=1 i /login?rejestracja=1 obsluguje 99_bootstrap.js.
// To jedyna droga z wizytowki do aplikacji, a pytest tej sciezki nie dotyka.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

function start(adres, { przyciskDemo = true } = {}) {
    document.body.innerHTML = '<input id="tx-date">' + (przyciskDemo ? '<button id="demo-login-btn"></button>' : '');
    window.history.replaceState(null, '', adres);
    zaladujModuly('99_bootstrap.js');
}

beforeEach(() => {
    for (const nazwa of ['initContractorCombobox', 'fetchInitialData', 'loginAsDemo', 'showLoginModal', 'showAuthView']) {
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
