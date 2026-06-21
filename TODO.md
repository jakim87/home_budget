# Lista zadań (TODO) - Home Budget App

## ✅ Zrealizowane (Zrobione)

- [X] Backendowa obsługa transakcji cyklicznych i zaplanowanych (`recurring_service.py`, `planned_transaction_service.py`, `recurring_bp.py`, `planned_transactions_bp.py`).
- [X] Dashboard — panel Net Worth, wykresy miesięczne/roczne (Chart.js), zakładka domyślna.
- [X] Inicjalizacja projektu Flask (App Factory) i konfiguracja.
- [X] Utworzenie podstawowych modeli (User, Account, Category, Transaction, Budget, TransactionArchive).
- [X] Refaktoryzacja modeli (SQLAlchemy 2.0, typowanie `Mapped`).
- [X] Skrypt do weryfikacji bazy (`test_db.py`) i konfiguracja migracji (Alembic).
- [X] Konfiguracja TDD (`pytest`, izolowana baza w RAM w `conftest.py`).
- [X] API: Odczyt danych startowych (`GET /api/init`) z optymalizacją N+1 (JOIN).
- [X] API: Zapis transakcji (`POST /api/transactions`) ze sztucznym mockowaniem usera/konta.
- [X] API: Zapis kategorii (`POST /api/categories`).
- [X] Architektura bazy: Tabela cieni (`TransactionArchive`) do zachowania historii usuniętych faktów.
- [X] API: Hard Delete transakcji + zapis do archiwum (`DELETE /api/transactions/<id>`).
- [X] Frontend: Interfejs w Tailwind CSS, dynamiczna komunikacja (Fetch API) dla zapisów i listowania.
- [X] Autoryzacja: Logowanie użytkowników (rejestracja, haszowanie haseł) - zaimplementowane, ale tymczasowo omijane na rzecz `default_user`.
- [X] API: Usunięcie "mockowanego" użytkownika - wszystkie operacje są teraz przypisywane do jednego, globalnego `default_user`.
- [X] API: Miękkie usuwanie (soft delete) kategorii (`is_active = False`).
- [X] Endpointy CRUD dla kont bankowych (dodawanie, usuwanie, edycja salda).
- [X] Frontend: Podpięcie przycisku usunięcia kategorii pod API.
- [X] Skrypt CLI (`flask cleanup-archive`) usuwający przestarzałe logi z `transaction_archive` (> 60 dni).
- [X] Rozbudowa zapisu (`POST /api/transactions`) i bazy o "Rozbijanie transakcji" (Splits) – w HTML to jest, backend to ignoruje.
- [X] Moduł importu transakcji z plików CSV (ING Bank Śląski).
- [X] Architektura importu: Tabela tymczasowa (`TransactionStaging`) i proces weryfikacji.
- [X] Algorytm autokategoryzacji przy imporcie (oparty na słowach kluczowych i przelewach wewnętrznych).

## ⏳ Do zrobienia (Frontend & UI)

- [ ] Tryb edycji zbiorczej transakcji: checkbox przy każdej transakcji + "zaznacz wszystkie", akcje na zaznaczonych: usuń, zmień kategorię.

## 🚀 Funkcjonalności Biznesowe (zgodnie z README.md)

- [ ] Wsparcie dla innych banków (Millennium, mBank, Pekao, Revolut).
- [ ] Obsługa wpisów gotówkowych (Manual cash entries).
- [ ] Moduł planowania budżetu miesięcznego (`Budget`).
- [ ] Zaawansowana analityka i raportowanie wydatków.
- [ ] Obsługa kredytów hipotecznych (traktowanych w bilansie jako zobowiązania / wartości ujemne).
- [ ] Moduł rozpoznawania i skanowania paragonów z użyciem OCR.
- [ ] Gotowość API pod przyszłą integrację z aplikacją mobilną (iOS / Android).
- [ ] Nie można usunąć transakcji cyklicznej. Jeśli użytkownik chce to zrobić, to tylko poprzez edytowanie daty zakończenia.
