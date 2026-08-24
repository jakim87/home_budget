# Patch 2 — sumy dnia i zwijanie dni w historii operacji

Plik: `app/static/js/11_transactions.js`, funkcja `renderTransactions()` (linia 182).

Zmiana dokłada wiersz-nagłówek przed pierwszą operacją każdego dnia:
nazwa dnia, kreska, liczba operacji i suma dnia. Kliknięcie w ten wiersz
zwija/rozwija operacje z tego dnia.

## Krok 1: stan zwinięcia

Na początku pliku (przed `renderTransactions`) dodaj:

```js
// Zwinięte dni w historii operacji — klucz to data ISO (YYYY-MM-DD).
const collapsedDays = new Set();

function toggleDay(date) {
    if (collapsedDays.has(date)) collapsedDays.delete(date);
    else collapsedDays.add(date);
    renderTransactions();
}

// Odmiana rzeczownika po liczbie: 1 operacja / 2–4 operacje / 5+ operacji
function operacjeLabel(n) {
    if (n === 1) return 'operacja';
    const d = n % 10, s = n % 100;
    return (d >= 2 && d <= 4 && (s < 10 || s >= 20)) ? 'operacje' : 'operacji';
}

const DNI_TYGODNIA = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota'];
const MIESIACE_DOP = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
                      'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];
```

## Krok 2: liczba kolumn

W `renderTransactions()`, zaraz po linii:

```js
const showAccountColumn = !globalAccountFilter;
```

dodaj:

```js
// data, [konto], kontrahent, kategoria, opis, komentarz, kwota, akcje
const colCount = showAccountColumn ? 8 : 7;
let lastRenderedDate = null;
```

## Krok 3: wiersz-nagłówek dnia

W pętli `filtered.forEach(t => {` — **jako pierwsze linijki w środku pętli**,
przed `const isSplit = …`:

```js
            // Nagłówek dnia — raz na datę, z sumą i liczbą operacji
            if (t.date !== lastRenderedDate) {
                lastRenderedDate = t.date;
                const ofDay = filtered.filter(x => x.date === t.date);
                const sumOfDay = ofDay.reduce((acc, x) => acc + x.amount, 0);
                const d = new Date(t.date + 'T00:00:00');
                const label = `${DNI_TYGODNIA[d.getDay()]}, ${d.getDate()} ${MIESIACE_DOP[d.getMonth()]}`;
                const sumText = `${sumOfDay < 0 ? '−' : '+'}${Math.abs(sumOfDay).toFixed(2)}`;
                const chevron = collapsedDays.has(t.date) ? '▸' : '▾';

                const dayRow = document.createElement('tr');
                dayRow.className = 'cursor-pointer';
                dayRow.setAttribute('onclick', `toggleDay('${t.date}')`);
                dayRow.innerHTML = `
                    <td colspan="${colCount}" class="pt-4 pb-1.5 px-2" style="border-bottom:1px solid var(--color-accent-300)">
                        <div class="flex items-baseline gap-2.5">
                            <span class="tabular-nums" style="width:9px;font-size:10px;color:var(--color-accent)">${chevron}</span>
                            <span style="font-family:var(--font-heading);font-weight:600;font-size:15px">${label}</span>
                            <span class="flex-1" style="height:1px;background:var(--color-divider)"></span>
                            <span class="tabular-nums text-sm" style="color:var(--color-neutral-700)">${ofDay.length} ${operacjeLabel(ofDay.length)} · suma dnia ${sumText}</span>
                        </div>
                    </td>
                `;
                list.appendChild(dayRow);
            }

            // Dzień zwinięty — pomijamy jego operacje
            if (collapsedDays.has(t.date)) return;
```

## Krok 4: kolumna daty w wierszach

Data jest teraz w nagłówku dnia, więc w wierszu operacji można ją wyciszyć.
W **TRYBIE WIDOKU** podmień pierwszą komórkę:

```js
// przed
<td class="p-4 border-b border-slate-100 text-sm text-slate-500 whitespace-nowrap">${t.date}</td>
// po
<td class="p-4 border-b border-slate-100 text-xs whitespace-nowrap" style="color:var(--color-neutral-500)">${t.date.slice(8)}</td>
```

(zostaje sam dzień miesiąca jako dyskretna kotwica — pełna data jest w nagłówku)

## Uwaga o funkcji globalnej

`toggleDay` jest wywoływane z atrybutu `onclick`, więc musi być w zasięgu
globalnym. Jeśli `99_bootstrap.js` owija pliki w IIFE, dopisz:

```js
window.toggleDay = toggleDay;
```
