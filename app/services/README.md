# Dokumentacja Modułu Usług (Services)

Ten folder zawiera kluczową logikę biznesową aplikacji. Warstwa usług oddziela operacje na danych i złożone procesy od warstwy prezentacji (Blueprintów), co czyni kod bardziej przejrzystym, łatwiejszym do testowania i ponownego użycia.

## Główne zasady

1.  **Separacja od web:** Funkcje w tej warstwie **nie powinny** mieć dostępu do obiektów Flaska, takich jak `request` czy `session`. Powinny przyjmować jako argumenty proste typy danych (np. `user_id`, słowniki z danymi) i zwracać obiekty modeli lub rzucać wyjątki.
2.  **Transakcyjność:** Każda funkcja, która modyfikuje dane, jest odpowiedzialna za zarządzanie własną transakcją bazodanową. Oznacza to, że musi zawierać `db.session.commit()` w przypadku sukcesu i `db.session.rollback()` w razie błędu.
3.  **Obsługa błędów:** Zamiast zwracać kody błędów HTTP, funkcje serwisowe powinny rzucać wyjątki (najczęściej `ValueError`) z czytelnym komunikatem. Obsługa tych wyjątków i zamiana ich na odpowiedź HTTP (np. 400, 404) jest zadaniem Blueprintu.

## Jak dodać nową funkcję serwisową?

### Krok 1: Wybierz lub utwórz odpowiedni plik

Grupuj powiązane ze sobą funkcje w jednym pliku. Na przykład:
*   `transaction_service.py` - operacje na transakcjach (usuwanie, edycja).
*   `budget_service.py` - logika związana z budżetem, importem i analizą.
*   `category_service.py` - zarządzanie kategoriami.

### Krok 2: Zaimplementuj funkcję zgodnie ze wzorcem

Użyj poniższego szablonu jako punktu wyjścia. Gwarantuje on poprawną obsługę transakcji i błędów.

```python
from app import db
from app.models import YourModel, SomeOtherModel
from decimal import Decimal

def your_new_service_function(user_id: int, data: dict) -> YourModel:
    """
    Zwięzły opis, co robi ta funkcja.
    Przyjmuje proste typy danych, zwraca obiekt modelu lub rzuca wyjątek.
    """
    try:
        # 1. Walidacja danych wejściowych
        required_field = data.get('required_field')
        if not required_field:
            raise ValueError("Pole 'required_field' jest wymagane.")

        # 2. Interakcja z bazą danych (odczyt, zapis)
        related_object = db.session.get(SomeOtherModel, data.get('related_id'))
        if not related_object:
            raise ValueError("Obiekt powiązany nie istnieje.")

        new_object = YourModel(
            user_id=user_id,
            some_field=required_field,
            # ... inne pola
        )
        db.session.add(new_object)

        # 3. Zatwierdzenie transakcji
        db.session.commit()
        
        return new_object

    except Exception as e:
        # 4. Wycofanie zmian w razie błędu
        db.session.rollback()
        # Rzuć wyjątek dalej, aby obsłużyć go w warstwie wyżej (w blueprincie)
        raise ValueError(f"Błąd podczas wykonywania operacji: {e}")
```

### Krok 3: Użyj serwisu w Blueprincie

Blueprint jest odpowiedzialny za wywołanie serwisu i przetworzenie jego wyniku na odpowiedź HTTP.

```python
# w pliku app/blueprints/some_bp.py

from flask import request, jsonify
from app.services.your_service import your_new_service_function

@some_bp.route('/items', methods=['POST'])
def create_item():
    user_id = get_current_user_id() # Funkcja pomocnicza
    try:
        # Blueprint przekazuje dane do serwisu i obsługuje odpowiedź
        new_item = your_new_service_function(user_id, request.get_json())
        return jsonify({'id': new_item.id, 'message': 'Utworzono pomyślnie'}), 201
    except ValueError as e:
        # Serwis rzucił błąd, blueprint zwraca go jako odpowiedź 400
        return jsonify({'error': str(e)}), 400
```