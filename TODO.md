# Lista zadań (TODO) - Home Budget App

## ✅ Zrealizowane (Zrobione)
- [x] Inicjalizacja projektu Flask (App Factory) i konfiguracja.
- [x] Utworzenie podstawowych modeli (User, Account, Category, Transaction, Budget, TransactionArchive).
- [x] Refaktoryzacja modeli (SQLAlchemy 2.0, typowanie `Mapped`).
- [x] Skrypt do weryfikacji bazy (`test_db.py`) i konfiguracja migracji (Alembic).
- [x] Konfiguracja TDD (`pytest`, izolowana baza w RAM w `conftest.py`).
- [x] API: Odczyt danych startowych (`GET /api/init`) z optymalizacją N+1 (JOIN).
- [x] API: Zapis transakcji (`POST /api/transactions`) ze sztucznym mockowaniem usera/konta.
- [x] API: Zapis kategorii (`POST /api/categories`).
- [x] Architektura bazy: Tabela cieni (`TransactionArchive`) do zachowania historii usuniętych faktów.
- [x] API: Hard Delete transakcji + zapis do archiwum (`DELETE /api/transactions/<id>`).
- [x] Frontend: Interfejs w Tailwind CSS, dynamiczna komunikacja (Fetch API) dla zapisów i listowania.
- [x] Autoryzacja: Logowanie użytkowników (rejestracja, haszowanie haseł) - zaimplementowane, ale tymczasowo omijane na rzecz `default_user`.
- [x] API: Usunięcie "mockowanego" użytkownika - wszystkie operacje są teraz przypisywane do jednego, globalnego `default_user`.
- [x] API: Miękkie usuwanie (soft delete) kategorii (`is_active = False`).
- [x] Endpointy CRUD dla kont bankowych (dodawanie, usuwanie, edycja salda).
- [x] Frontend: Podpięcie przycisku usunięcia kategorii pod API.
- [x] Skrypt CLI (`flask cleanup-archive`) usuwający przestarzałe logi z `transaction_archive` (> 60 dni).
- [x] Rozbudowa zapisu (`POST /api/transactions`) i bazy o "Rozbijanie transakcji" (Splits) – w HTML to jest, backend to ignoruje.
- [x] Moduł importu transakcji z plików CSV (ING Bank Śląski).
- [x] Architektura importu: Tabela tymczasowa (`TransactionStaging`) i proces weryfikacji.
- [x] Algorytm autokategoryzacji przy imporcie (oparty na słowach kluczowych i przelewach wewnętrznych).

## ⏳ Do zrobienia (Backend & API)
- [ ] Backendowa obsługa "Transakcji Cyklicznych" (przeniesienie logiki z `base.html` JS do backendu np. zadań w tle).

## 🖥️ Do zrobienia (Frontend & UI)
- [ ] Dashboard - Główny panel pokazujący całkowitą wartość netto (Net Worth) połączoną ze wszystkich kont.
- [ ] Wizualizacja Danych: Zastąpienie prostych tekstowych podsumowań interaktywnymi wykresami (Chart.js).

## 🚀 Funkcjonalności Biznesowe (zgodnie z README.md)
- [ ] Wsparcie dla innych banków (Millennium, mBank, Pekao, Revolut).
- [ ] Obsługa wpisów gotówkowych (Manual cash entries).
- [ ] Moduł planowania budżetu miesięcznego (`Budget`).
- [ ] Zaawansowana analityka i raportowanie wydatków.
- [ ] Obsługa kredytów hipotecznych (traktowanych w bilansie jako zobowiązania / wartości ujemne).
- [ ] Moduł rozpoznawania i skanowania paragonów z użyciem OCR.
- [ ] Gotowość API pod przyszłą integrację z aplikacją mobilną (iOS / Android).