# Podejście do testowania w projekcie

W tym projekcie stosujemy podejście **Test-Driven Development (TDD)**. Oznacza to, że testy nie są pisane po stworzeniu funkcjonalności, ale **przed** nią.

## Cykl TDD (Red - Green - Refactor)

Każda nowa funkcja, moduł, czy parser (np. dla plików ING) musi być tworzona według następujących kroków:

1. **RED (Czerwony):**
   * Najpierw napisz test dla funkcji, która jeszcze nie istnieje lub nie działa.
   * Uruchom test i upewnij się, że **nie przechodzi** (zgłasza błąd). To dowodzi, że test faktycznie coś sprawdza.

2. **GREEN (Zielony):**
   * Napisz *najprostszy możliwy kod*, który sprawi, że test przejdzie.
   * Nie przejmuj się na tym etapie idealną strukturą czy optymalizacją. Cel to "zaliczenie" testu.

3. **REFACTOR (Refaktoryzacja):**
   * Popraw napisany kod (np. zmień nazwy zmiennych, zoptymalizuj pętle, przenieś kod do odpowiedniego pliku).
   * Uruchom testy ponownie, aby upewnić się, że Twoje zmiany niczego nie zepsuły.

## Wymogi techniczne

* **Narzędzie:** Używamy frameworka `pytest`.
* **Struktura:** Wszystkie testy muszą znajdować się w folderze `tests/`.
* **Nazewnictwo:** 
  * Pliki testowe muszą zaczynać się od `test_` (np. `test_models.py`, `test_ing_parser.py`).
  * Funkcje testowe wewnątrz plików muszą zaczynać się od `test_` (np. `def test_transaction_creation():`).

## Baza danych w testach

Testy **nie powinny** modyfikować głównej bazy danych (`budget_db`). Do celów testowych używamy osobnej konfiguracji w `tests/conftest.py`, która domyślnie korzysta z izolowanej bazy w pamięci RAM (`sqlite:///:memory:`). Dzięki temu testy są szybkie i powtarzalne.

## Uruchamianie testów

Aby uruchomić wszystkie testy, wpisz w terminalu:
```bash
pytest
```