# Changelog

## [1.9.0](https://github.com/jakim87/home_budget/compare/v1.8.0...v1.9.0) (2026-11-20)


### Funkcje

* baner o zmianie dokumentów streszcza zmiany, a regulamin zapowiada je z 7-dniowym wyprzedzeniem ([#287](https://github.com/jakim87/home_budget/issues/287)) ([1a86f7a](https://github.com/jakim87/home_budget/commit/1a86f7a2f1c1d1999de2baed7814dbdb32ec934d))
* polityka prywatności opisuje zapis potwierdzenia zmian dokumentów ([#290](https://github.com/jakim87/home_budget/issues/290)) ([d362a7a](https://github.com/jakim87/home_budget/commit/d362a7a1d0ef77174f8c332835c07d25e6d8c4a0))
* robots.txt, sitemap.xml i metadane SEO publicznych stron ([#284](https://github.com/jakim87/home_budget/issues/284)) ([3de5e77](https://github.com/jakim87/home_budget/commit/3de5e777438a9eefb054cdda129dc10fee553a26))
* zapisujemy, kiedy użytkownik potwierdził zmiany dokumentów, i pokazujemy to w CLI ([#289](https://github.com/jakim87/home_budget/issues/289)) ([5e8a191](https://github.com/jakim87/home_budget/commit/5e8a1911d58cfd3bf71018e5b18e37e1ad421a9f))

## [1.8.0](https://github.com/jakim87/home_budget/compare/v1.7.0...v1.8.0) (2026-11-19)


### Funkcje

* baner po zalogowaniu informuje o zmianie regulaminu i polityki prywatności ([#283](https://github.com/jakim87/home_budget/issues/283)) ([b8268ce](https://github.com/jakim87/home_budget/commit/b8268ce4c2402c6f4e173c42c30e0de3f72c79e7))


### Poprawki

* interfejs nie łączy się z zewnętrznymi CDN — Tailwind, Chart.js, driver.js i czcionki serwowane z aplikacji ([#281](https://github.com/jakim87/home_budget/issues/281)) ([b4dfd1f](https://github.com/jakim87/home_budget/commit/b4dfd1ff577d1fab2799243239e91d45c8248296))
* polityka prywatności opisuje logi serwera i kopie zapasowe; licencja BSL spójna na stronach ([#279](https://github.com/jakim87/home_budget/issues/279)) ([4264ad4](https://github.com/jakim87/home_budget/commit/4264ad46b3c0f911c1937df61cbe55ee37db81ef))
* regulamin, polityka i strona O aplikacji bez wzmianek o niekomercyjności; łączniki zamiast pauz ([#282](https://github.com/jakim87/home_budget/issues/282)) ([949051f](https://github.com/jakim87/home_budget/commit/949051fd7a7e347ff0ba26b0c7ac478109dbf906))

## [1.7.0](https://github.com/jakim87/home_budget/compare/v1.6.0...v1.7.0) (2026-11-17)


### Funkcje

* import historii rachunku PKO BP z pliku CSV ([#273](https://github.com/jakim87/home_budget/issues/273)) ([52a35e2](https://github.com/jakim87/home_budget/commit/52a35e2e3a2f3fdae1e6ee51732320308e69b49d))
* komentarz do operacji w poczekalni importu ([#277](https://github.com/jakim87/home_budget/issues/277)) ([c3fd93f](https://github.com/jakim87/home_budget/commit/c3fd93f03e8bb0ac1b73f67696ced9666bcd4468))
* transakcje cykliczne i zaplanowane czekają na potwierdzenie zamiast księgować się same ([#276](https://github.com/jakim87/home_budget/issues/276)) ([79684de](https://github.com/jakim87/home_budget/commit/79684de9e264bed46b5fe68c72e57a93ed30d29a))


### Poprawki

* ikonka komentarza w poczekalni w kolorze ochry z palety Noble ([#278](https://github.com/jakim87/home_budget/issues/278)) ([a6a84bd](https://github.com/jakim87/home_budget/commit/a6a84bd63dd088d952e574ab8e281570b2389780))
* odrzucony import zostawia w logu bank, format i rodzaj błędu ([#275](https://github.com/jakim87/home_budget/issues/275)) ([cf399fd](https://github.com/jakim87/home_budget/commit/cf399fdef372198145924ae247a77e3241b000ed))

## [1.6.0](https://github.com/jakim87/home_budget/compare/v1.5.1...v1.6.0) (2026-11-16)


### Funkcje

* wyszukiwarka kontrahentów w Słownikach, szybka zmiana kategorii i przejście do Wniosków ([#271](https://github.com/jakim87/home_budget/issues/271)) ([9332844](https://github.com/jakim87/home_budget/commit/933284453979d3b2b7c528a5e6acb526a0f33a13))

## [1.5.1](https://github.com/jakim87/home_budget/compare/v1.5.0...v1.5.1) (2026-11-14)


### Poprawki

* wersja mobilna mieści się na ekranie 375 px (iPhone 13 mini) ([#267](https://github.com/jakim87/home_budget/issues/267)) ([cd198c4](https://github.com/jakim87/home_budget/commit/cd198c4378e15ac337b1ae1fcd8d3794ec86b6c8))
* Wnioski rozpoznają niepełny import, podwyżki stałych opłat mimo luki i nie biorą wypłat gotówki za zakupy ([#268](https://github.com/jakim87/home_budget/issues/268)) ([adaabd2](https://github.com/jakim87/home_budget/commit/adaabd2c7d76894e5ec6a9d18627cff9d086ba65))

## [1.5.0](https://github.com/jakim87/home_budget/compare/v1.4.2...v1.5.0) (2026-11-14)


### Funkcje

* zakładka Wnioski — wnioski z miesiąca i zapisywane widoki z filtrami ([#265](https://github.com/jakim87/home_budget/issues/265)) ([617fdcf](https://github.com/jakim87/home_budget/commit/617fdcf00cad4e692f704e928c63f957bf59be54))

## [1.4.2](https://github.com/jakim87/home_budget/compare/v1.4.1...v1.4.2) (2026-11-11)


### Poprawki

* poczekalnia pozwala zatwierdzić przelew mimo nieaktualnej nazwy kontrahenta konta ([#263](https://github.com/jakim87/home_budget/issues/263)) ([1b70f88](https://github.com/jakim87/home_budget/commit/1b70f889a169a8eaceeaa46bb4dd566bb9cd1720))
* zmiana nazwy konta zmienia też nazwę jego kontrahenta „Moje konto: …” ([#262](https://github.com/jakim87/home_budget/issues/262)) ([eaa3c63](https://github.com/jakim87/home_budget/commit/eaa3c636544791646d10445a3ba3fa0c2229b1e5))

## [1.4.1](https://github.com/jakim87/home_budget/compare/v1.4.0...v1.4.1) (2026-11-08)


### Poprawki

* **demo:** odtwarzanie konta demo nie przejmuje zwykłego konta o tej samej nazwie ([9fdaadc](https://github.com/jakim87/home_budget/commit/9fdaadc71affac746f129f39cd08571810af69e2))
* import wyciągu z bardzo długim opisem operacji nie kończy się już błędem serwera ([e2503df](https://github.com/jakim87/home_budget/commit/e2503df733e57e350a370a128fb0b4547d8c90ab))
* logi serwera nie zawierają kwot ani nazw kont i kategorii ([ce98b08](https://github.com/jakim87/home_budget/commit/ce98b0878c4039ba04ab9c2e4d0d35c87c75a48e))
* pierwsza transakcja cykliczna księguje się w wybranym dniu miesiąca lub tygodnia, a nie w dniu założenia ([e2503df](https://github.com/jakim87/home_budget/commit/e2503df733e57e350a370a128fb0b4547d8c90ab))
* podwójne „Zatwierdź” w poczekalni nie księguje operacji dwa razy ([ce98b08](https://github.com/jakim87/home_budget/commit/ce98b0878c4039ba04ab9c2e4d0d35c87c75a48e))
* poprawka opisu zwrotu w tabeli operacji nie zamienia go już w wydatek ([e2503df](https://github.com/jakim87/home_budget/commit/e2503df733e57e350a370a128fb0b4547d8c90ab))
* równoległe zapisy (podwójny Enter, dwie karty, nocny harmonogram) nie gubią już kwot na saldzie konta ([ce98b08](https://github.com/jakim87/home_budget/commit/ce98b0878c4039ba04ab9c2e4d0d35c87c75a48e))
* transakcje cykliczne i zaplanowane nie zatrzymują się po usunięciu kategorii, a archiwizacja konta wyłącza jego harmonogram ([e2503df](https://github.com/jakim87/home_budget/commit/e2503df733e57e350a370a128fb0b4547d8c90ab))
* uzgodnienie salda na dziś działa także zaraz po północy ([9fdaadc](https://github.com/jakim87/home_budget/commit/9fdaadc71affac746f129f39cd08571810af69e2))
* uzgodnienie salda na dziś nie tworzy fałszywej korekty, gdy na koncie są operacje z przyszłą datą ([e2503df](https://github.com/jakim87/home_budget/commit/e2503df733e57e350a370a128fb0b4547d8c90ab))


### Wydajność

* szybsze wczytywanie transakcji dzięki indeksom ([ce98b08](https://github.com/jakim87/home_budget/commit/ce98b0878c4039ba04ab9c2e4d0d35c87c75a48e))

## [1.4.0](https://github.com/jakim87/home_budget/compare/v1.3.0...v1.4.0) (2026-11-08)


### Funkcje

* import pokazuje przy każdym pliku konta, zakres dat i duplikaty ([#252](https://github.com/jakim87/home_budget/issues/252)) ([96b249c](https://github.com/jakim87/home_budget/commit/96b249c0e3cfa517a26d9a93eec85ed978776a93))
* odrzucanie z poczekalni pojedynczego wiersza, całego pliku albo konta ([#250](https://github.com/jakim87/home_budget/issues/250)) ([5eea527](https://github.com/jakim87/home_budget/commit/5eea5271444f872857e782affcd11265e1e193c5))


### Poprawki

* edycja opisu transakcji z podziałem nie zmienia już jej kategorii ([#254](https://github.com/jakim87/home_budget/issues/254)) ([891569c](https://github.com/jakim87/home_budget/commit/891569c2d551936e3e5ae4330f55a0a7d59eebf1))
* import Millennium rozdziela operacje z kilku rachunków na właściwe konta ([#246](https://github.com/jakim87/home_budget/issues/246)) ([d9cd5e3](https://github.com/jakim87/home_budget/commit/d9cd5e39ce21fe475651a439fe9ca1fb2d60aa14))
* import Millennium z kilku rachunków nie księguje operacji kartą na konto spoza wyciągu ([#255](https://github.com/jakim87/home_budget/issues/255)) ([7d55d18](https://github.com/jakim87/home_budget/commit/7d55d1891bb0da20843b70a7b4ae55201216c40d))
* import zestawienia operacji mBanku w HTML bierze kwotę zamiast salda ([#248](https://github.com/jakim87/home_budget/issues/248)) ([41da4dd](https://github.com/jakim87/home_budget/commit/41da4dd5d74f77c5a8d21fdb977879991bc4ce54))
* ręczny wybór mBank HTML dla zestawienia operacji bierze kwotę zamiast salda ([#251](https://github.com/jakim87/home_budget/issues/251)) ([fd83aa8](https://github.com/jakim87/home_budget/commit/fd83aa870cf4d6f746087ee23a080c6803230107))

## [1.3.0](https://github.com/jakim87/home_budget/compare/v1.2.1...v1.3.0) (2026-11-03)


### Funkcje

* zakładka Import — wgrywanie wyciągów i zatwierdzanie na jednej stronie ([#242](https://github.com/jakim87/home_budget/issues/242)) ([4f5b6c2](https://github.com/jakim87/home_budget/commit/4f5b6c272e152c21b85262e9d004f59d88acba8e))


### Poprawki

* samouczek importu ostrzega, że plik bez numeru rachunku trzeba wgrać osobno ([#240](https://github.com/jakim87/home_budget/issues/240)) ([f032238](https://github.com/jakim87/home_budget/commit/f03223863dffa41d37aff05cf943ed521d65f1bb))

## [1.2.1](https://github.com/jakim87/home_budget/compare/v1.2.0...v1.2.1) (2026-11-03)


### Poprawki

* edycja uzgodnienia salda nie zmienia już kategorii ani znaku kwoty ([#238](https://github.com/jakim87/home_budget/issues/238)) ([d313af9](https://github.com/jakim87/home_budget/commit/d313af9bf7a96dc14daea3234b73eb19386ce894))
* samouczek na telefonie przewija do podświetlonego elementu i nie zasłania go dymkiem ([#236](https://github.com/jakim87/home_budget/issues/236)) ([086ca17](https://github.com/jakim87/home_budget/commit/086ca171dc4b4467b014d153f3ed38e05f338767))

## [1.2.0](https://github.com/jakim87/home_budget/compare/v1.1.0...v1.2.0) (2026-10-18)


### Funkcje

* **demo:** konto demo z historią 19 miesięcy, kredytem gotówkowym i rachunkiem maklerskim ([5c89ff8](https://github.com/jakim87/home_budget/commit/5c89ff8531627cc1bcf1e6a3c8a74197599309a9))
* na telefonie przycisk „+” otwiera szybki wpis z każdej zakładki ([5c89ff8](https://github.com/jakim87/home_budget/commit/5c89ff8531627cc1bcf1e6a3c8a74197599309a9))
* nowy Dashboard — porównanie majątku z poprzednim miesiącem i rokiem, widok wg typu kont, wykres kategorii z przejściem do raportu ([5c89ff8](https://github.com/jakim87/home_budget/commit/5c89ff8531627cc1bcf1e6a3c8a74197599309a9))
* szybki wpis transakcji jedną linią („Biedronka 85,60 wczoraj”) z podpowiedziami kontrahentów, kategorii i kont ([5c89ff8](https://github.com/jakim87/home_budget/commit/5c89ff8531627cc1bcf1e6a3c8a74197599309a9))


### Poprawki

* domyślna data w formularzach transakcji to dzisiejszy dzień lokalny ([5c89ff8](https://github.com/jakim87/home_budget/commit/5c89ff8531627cc1bcf1e6a3c8a74197599309a9))

## [1.1.0](https://github.com/jakim87/home_budget/compare/v1.0.0...v1.1.0) (2026-10-07)


### Funkcje

* **stopka:** numer wersji w stopce prowadzi do listy zmian ([3c19060](https://github.com/jakim87/home_budget/commit/3c19060a848a2dcb038edb7b549afa38034ed436))
