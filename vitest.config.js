import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        // Moduly z app/static/js sa pisane pod przegladarke (globalne funkcje,
        // document, Chart.js) — bez jsdom nie da sie ich w ogole zaladowac.
        environment: 'jsdom',
        include: ['tests/js/**/*.test.js'],
    },
});
