# Dokumentacja Modułu Migracji

Ten folder jest zarządzany przez **Flask-Migrate** (nakładkę na **Alembic**) i służy do wersjonowania schematu bazy danych. Każda zmiana w modelach (`app/models.py`), która wpływa na strukturę bazy (np. dodanie tabeli, nowej kolumny), musi zostać odzwierciedlona w postaci skryptu migracyjnego.

## Struktura folderu

*   `versions/`: Zawiera poszczególne skrypty migracyjne. Każdy plik to jedna, konkretna zmiana w bazie.
*   `env.py`: Główny plik konfiguracyjny Alembica, który mówi, jak połączyć się z bazą i jakie modele wziąć pod uwagę.
*   `alembic.ini`: Plik konfiguracyjny dla narzędzia CLI Alembic.

## Podstawowe komendy

Wszystkie komendy należy wykonywać z głównego folderu projektu.

### 1. Generowanie nowej migracji

Po dokonaniu zmian w pliku `app/models.py`, wygeneruj nowy skrypt migracyjny:

```bash
flask db migrate -m "Krótki opis wprowadzonych zmian"
```

**Ważne:** Zawsze sprawdzaj wygenerowany plik w folderze `versions/`, aby upewnić się, że Alembic poprawnie zinterpretował Twoje zmiany.

### 2. Aplikowanie migracji

Aby zastosować oczekujące migracje na bazie danych (np. po pobraniu zmian z repozytorium):

```bash
flask db upgrade
```

### 3. Wycofywanie migracji

Aby cofnąć ostatnią migrację (przydatne podczas developmentu):

```bash
flask db downgrade
```

### 4. Sprawdzanie historii

Aby zobaczyć historię wszystkich migracji i która jest aktualnie zastosowana:

```bash
flask db history
```