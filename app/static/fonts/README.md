# Czcionki

Lora i Cormorant Garamond z Google Fonts, serwowane z aplikacji zamiast z `fonts.googleapis.com`
(adres IP użytkownika nie trafia do Google). Fonty zmienne — jeden plik `.woff2` na podzbiór znaków
obejmuje cały zakres grubości. Zostawione podzbiory: `latin`, `latin-ext` (polskie znaki), `math`
i `symbols` (strzałki, znaki matematyczne); cyrylica, greka i wietnamski pominięte.

Licencja obu krojów: SIL Open Font License 1.1 — https://openfontlicense.org

`fonts.css` ładują `base.html`, `legal_base.html` oraz (przez `@import`) `landing/classical.css`.
