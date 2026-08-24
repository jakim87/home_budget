# Wdrożenie wyglądu Classical w Budżecie domowym

Wygląd wchodzi jako **warstwa nadpisująca** — nie trzeba ruszać `base.html`
poza dwiema linijkami w `<head>`. Wszystkie zakładki (Dashboard, Transakcje,
Do weryfikacji, Podsumowanie, Słowniki, Raporty) zmieniają się naraz.

## Instalacja

1. Skopiuj `classical.css` do `app/static/classical.css`.
2. W `app/templates/base.html`, w `<head>`, **po** linii z `style.css` dodaj:

```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static', filename='classical.css') }}">
```

3. Odśwież z twardym cache (Ctrl+Shift+R).

Wycofanie: usuń te dwie linijki. Nic innego nie jest dotknięte.

## Co robi

| Obszar | Przed | Po |
| --- | --- | --- |
| Typografia | Inter | Cormorant Garamond (nagłówki) + Lora (tekst) |
| Akcent | niebieski #3b82f6 | złoto #b68235 |
| Tło | #f8fafc (chłodne) | #f3f2f2 (ciepłe, papierowe) |
| Przyciski | wypełnione kolorem | obrys na przezroczystym tle |
| Gradient „Net Worth" | niebieski gradient | ciepła czerń ze złotym obrysem |
| Promienie | 8–24 px | 4 px |
| Cienie | wyraźne | szept |
| Tabele | linie Tailwinda | kapitaliki w nagłówku, kreski między wierszami |
| Liczby | proporcjonalne | tabularne (kolumny kwot się zgadzają) |

## Czego CSS nie zrobi — trzy patche w `patches/`

Każdy jest niezależny i można je wdrażać po kolei, od najbezpieczniejszego:

| Patch | Czego dotyczy | Ryzyko |
| --- | --- | --- |
| `patch-1-wykresy.md` + `00_classical_charts.js` | kolory i typografia Chart.js | niskie — nowy plik + 8 podmian literałów |
| `patch-2-sumy-dnia.md` | nagłówki dni z sumą, zwijanie dnia | średnie — wnętrze `renderTransactions()` |
| `patch-3-panel-szczegolow.md` | panel szczegółów po prawej + nakładka na wąskim ekranie | wyższe — kontener w `base.html` i nowy plik JS |

Patch 3 warto robić na osobnej gałęzi. W dwóch miejscach trzeba potwierdzić
nazwy z istniejącego kodu (metoda i URL zapisu, nazwa funkcji przeładowania
listy) — jest to zaznaczone w treści patcha.

## Podglądy

- `Transakcje - prototyp v2 (styl 2a).dc.html` — docelowy wygląd zakładki Transakcje
- `Transakcje - przebudowa.dc.html` — warianty układu (1a, 1b, 2a)
