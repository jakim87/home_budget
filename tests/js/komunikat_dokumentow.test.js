// Baner o zmianie dokumentow prawnych (24_komunikat_dokumentow.js): widocznosc wg /api/init.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { zaladujModuly } from './helpers.js';

beforeEach(() => {
    document.body.innerHTML = '<div id="legal-notice" class="hidden"><span id="legal-notice-date"></span></div>';
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

describe('renderKomunikatPrawny', () => {
    it('odslania baner z data zmiany', () => {
        renderKomunikatPrawny({ show: true, updated: '19 listopada 2026' });
        expect(baner().classList.contains('hidden')).toBe(false);
        expect(document.getElementById('legal-notice-date').textContent).toBe('19 listopada 2026');
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
