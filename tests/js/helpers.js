// Ladowanie modulow frontu do testow.
//
// Pliki w app/static/js nie sa modulami ES — to zwykle skrypty, ktore
// przegladarka wykonuje po kolei, a funkcje i zmienne laduja we wspolnym
// zasiegu globalnym (patrz CLAUDE.md: kolejnosc prefiksow 01_… 99_ ma
// znaczenie). Nie ma tam ani `export`, ani kroku budowania.
//
// Dlatego test nie importuje ich, tylko odtwarza to zachowanie: czyta plik
// i wykonuje jego tresc w kontekscie globalnym testu. Dzieki temu testujemy
// dokladnie ten kod, ktory trafia do przegladarki — bez przerabiania
// produkcyjnych plikow na moduly.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const KATALOG_JS = join(process.cwd(), 'app', 'static', 'js');

/**
 * Zamienia deklaracje z POCZATKU LINII (`let x = …`, `const y = …`) na zwykle
 * przypisania (`x = …`). Powod jest techniczny: `let` i `const` wykonane przez
 * eval traficaja do globalnego zasiegu leksykalnego, ktorego kod testu (modul ES)
 * nie widzi — `transactions` byloby "is not defined" mimo poprawnego zaladowania.
 * Przypisanie bez deklaracji tworzy zwykla wlasciwosc globalThis, wiec test i
 * testowany kod dzielia te sama zmienna, tak jak dzieje sie to w przegladarce.
 *
 * Dopasowanie tylko do kolumny 0 jest istotne: deklaracje WEWNATRZ funkcji sa
 * wciete, wiec zostaja nietkniete i zachowuja swoj lokalny zasieg.
 */
function naGlobalne(kod) {
    return kod.replace(/^(let|const)\s+/gm, '');
}

/** Wykonuje wskazane pliki JS w globalnym zasiegu testu, w podanej kolejnosci. */
export function zaladujModuly(...nazwyPlikow) {
    for (const nazwa of nazwyPlikow) {
        const kod = readFileSync(join(KATALOG_JS, nazwa), 'utf-8');
        // `indirect eval` wykonuje kod w zasiegu globalnym, a nie lokalnym
        // zasiegu tej funkcji — inaczej `function foo()` z pliku nie stalaby
        // sie globalna i testy jej nie zobaczyly.
        (0, eval)(naGlobalne(kod));
    }
}

/** Transakcja w ksztalcie, w jakim front dostaje ja z GET /api/init. */
export function tx({ id = 1, date = '2026-01-15', amount = -100, category = 'Zakupy',
                     account_id = 1, contractor_id = null, title = 'Test' } = {}) {
    return { id, date, amount, category, account_id, contractor_id, title };
}
