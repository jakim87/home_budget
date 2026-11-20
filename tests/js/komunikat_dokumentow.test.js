// Baner o zmianie dokumentow prawnych (24_komunikat_dokumentow.js): widocznosc i streszczenie zmian.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

beforeEach(() => {
    document.body.innerHTML = '<div id="legal-notice" class="hidden"><span id="legal-notice-count"></span><div id="legal-notice-changes"></div></div>';
    globalThis.showToast = vi.fn();
    zaladujModuly('24_komunikat_dokumentow.js');
});

const baner = () => document.getElementById('legal-notice');

describe('czyPokazacKomunikatPrawny', () => {
    it('pokazuje tylko gdy serwer kaze', () => {
        expect(czyPokazacKomunikatPrawny({ show: true })).toBe(true);
        expect(czyPokazacKomunikatPrawny({ show: false })).toBe(false);
        expect(czyPokazacKomunikatPrawny(undefined)).toBe(false);
        expect(czyPokazacKomunikatPrawny(null)).toBe(false);
    });
});

describe('liczbaZmianTekst', () => {
    it('odmienia po polsku', () => {
        const f = n => liczbaZmianTekst(n);
        expect([f(1), f(2), f(4), f(5), f(12), f(14), f(22), f(25)]).toEqual(
            ['1 zmiana', '2 zmiany', '4 zmiany', '5 zmian', '12 zmian', '14 zmian', '22 zmiany', '25 zmian']);
    });
});

describe('renderKomunikatPrawny', () => {
    it('odslania baner z liczba zmian i lista pogrupowana datami', () => {
        renderKomunikatPrawny({ show: true, changes: [
            { date: '20 listopada 2026', od: '27 listopada 2026', punkty: ['a', 'b'] },
            { date: '19 listopada 2026', od: null, punkty: ['c'] },
        ] });
        expect(baner().classList.contains('hidden')).toBe(false);
        expect(document.getElementById('legal-notice-count').textContent).toBe('3 zmiany od Twojej ostatniej wizyty');
        const naglowki = [...document.querySelectorAll('#legal-notice-changes h4')].map(h => h.textContent);
        expect(naglowki).toEqual(['20 listopada 2026 (obowiązuje od 27 listopada 2026)', '19 listopada 2026']);
        expect(document.querySelectorAll('#legal-notice-changes li').length).toBe(3);
    });

    it('tresc punktu trafia jako tekst, nie jako HTML', () => {
        renderKomunikatPrawny({ show: true, changes: [{ date: 'd', od: null, punkty: ['<img src=x onerror=alert(1)>'] }] });
        expect(document.querySelector('#legal-notice-changes img')).toBeNull();
    });

    it('chowa baner, gdy nie ma czego pokazac (stary serwer bez pola)', () => {
        renderKomunikatPrawny({ show: true });
        renderKomunikatPrawny(undefined);
        expect(baner().classList.contains('hidden')).toBe(true);
    });
});

describe('potwierdzKomunikatPrawny', () => {
    it('po udanym zapisie chowa baner', async () => {
        renderKomunikatPrawny({ show: true });
        globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });
        await potwierdzKomunikatPrawny();
        expect(fetch).toHaveBeenCalledWith('/api/legal-ack', { method: 'POST' });
        expect(baner().classList.contains('hidden')).toBe(true);
    });

    it('po bledzie zostawia baner i pokazuje komunikat', async () => {
        renderKomunikatPrawny({ show: true });
        globalThis.fetch = vi.fn().mockResolvedValue({ ok: false });
        await potwierdzKomunikatPrawny();
        expect(baner().classList.contains('hidden')).toBe(false);
        expect(showToast).toHaveBeenCalled();
    });
});
