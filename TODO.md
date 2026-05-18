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

## ⏳ Do zrobienia (Backend & API)
- [ ] API: Miękkie usuwanie (soft delete) kategorii (`is_active = False`).
- [ ] Skrypt CLI (`flask cleanup-archive`) usuwający przestarzałe logi z `transaction_archive` (> 60 dni).
- [ ] Rozbudowa zapisu (`POST /api/transactions`) i bazy o "Rozbijanie transakcji" (Splits) – w HTML to jest, backend to ignoruje.
- [ ] Backendowa obsługa "Transakcji Cyklicznych" (przeniesienie logiki z `base.html` JS do backendu np. zadań w tle).
- [ ] Endpointy CRUD dla kont bankowych (dodawanie, usuwanie, edycja salda).
- [ ] Autoryzacja: Logowanie użytkowników (rejestracja, haszowanie haseł).
- [ ] API: Usunięcie "mockowanego" użytkownika - przypisywanie transakcji do faktycznie zalogowanej sesji.

## 🖥️ Do zrobienia (Frontend & UI)
- [ ] Podpięcie przycisku usunięcia kategorii (w zakładce Kategorie) pod zapytanie `DELETE` z API (obecnie JS usuwa tylko z lokalnej tablicy).
- [ ] Dashboard - Główny panel pokazujący całkowitą wartość netto (Net Worth) połączoną ze wszystkich kont.
- [ ] Wizualizacja Danych: Zastąpienie prostych tekstowych podsumowań interaktywnymi wykresami (Chart.js).

## 🚀 Funkcjonalności Biznesowe (zgodnie z README.md)
- [ ] Moduł importu transakcji z plików bankowych CSV (Priorytet: ING Bank Śląski).
- [ ] Wsparcie dla innych banków (Millennium, mBank, Pekao, Revolut).
- [ ] Algorytm autokategoryzacji przy imporcie (oparty na słowach kluczowych w opisie).
- [ ] Obsługa wpisów gotówkowych (Manual cash entries).
- [ ] Moduł planowania budżetu miesięcznego (`Budget`).
- [ ] Zaawansowana analityka i raportowanie wydatków.
- [ ] Obsługa kredytów hipotecznych (traktowanych w bilansie jako zobowiązania / wartości ujemne).
- [ ] Moduł rozpoznawania i skanowania paragonów z użyciem OCR.
- [ ] Gotowość API pod przyszłą integrację z aplikacją mobilną (iOS / Android).