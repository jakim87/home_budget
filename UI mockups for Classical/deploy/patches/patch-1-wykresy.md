# Patch 1 — kolory wykresów

Dwa kroki.

## Krok 1: nowy plik

Skopiuj `00_classical_charts.js` do `app/static/js/`. Numer `00` jest istotny —
plik musi się wczytać przed `13_dashboard.js` i `16_reports.js`. Ustawia
czcionki, siatkę, tooltipy i wystawia globalną paletę `CLASSICAL`.

## Krok 2: podmiana literałów kolorów

### `13_dashboard.js`

Linia 173–174 (wykres salda w czasie):

```js
// przed
borderColor: 'rgba(37, 99, 235, 1)',
backgroundColor: 'rgba(37, 99, 235, 0.08)',
// po
borderColor: CLASSICAL.accent,
backgroundColor: 'rgba(182, 130, 53, 0.10)',
```

Linia 268–269 (przychody):

```js
// przed
backgroundColor: 'rgba(16, 185, 129, 0.75)',
borderColor: 'rgba(16, 185, 129, 1)',
// po
backgroundColor: CLASSICAL.income.fill,
borderColor: CLASSICAL.income.line,
```

Linia 276–277 (wydatki):

```js
// przed
backgroundColor: 'rgba(244, 63, 94, 0.75)',
borderColor: 'rgba(244, 63, 94, 1)',
// po
backgroundColor: CLASSICAL.expense.fill,
borderColor: CLASSICAL.expense.line,
```

### `16_reports.js`

Linia 259–260 → `CLASSICAL.income.fill` / `CLASSICAL.income.line`
Linia 267–268 → `CLASSICAL.expense.fill` / `CLASSICAL.expense.line`
Linia 306–307 → `CLASSICAL.accent` / `'rgba(182, 130, 53, 0.10)'`
Linia 317–318 → `CLASSICAL.neutral600` / `'transparent'`

Linie 278 i 330 (`labels: { font: { size: 12 }, boxWidth: 12 }`) można usunąć —
`00_classical_charts.js` ustawia to globalnie.

## Wykresy kołowe / kategorie

Jeśli któryś wykres dostaje tablicę kolorów na kategorie, użyj:

```js
backgroundColor: CLASSICAL.series
```

Paleta ma 6 pozycji ułożonych od najmocniejszej; przy większej liczbie
kategorii zwiń resztę w „Pozostałe" — Classical nie lubi tęczy.
