# Dokumentacja Modułu Blueprints

Ten folder zawiera moduły (Blueprints) aplikacji Flask, które grupują powiązane ze sobą endpointy (trasy URL). Użycie blueprintów pozwala na zachowanie porządku i modułowości w projekcie.

## Jak dodać nowy Blueprint?

Aby dodać nową grupę endpointów (np. dla przyszłego panelu analitycznego), postępuj zgodnie z poniższymi krokami.

### Krok 1: Utwórz plik dla nowego Blueprintu

W folderze `app/blueprints/` utwórz nowy plik Python, którego nazwa kończy się na `_bp.py`.

Przykład: `dashboard_bp.py`

### Krok 2: Zdefiniuj Blueprint w nowym pliku

W pliku `dashboard_bp.py` umieść poniższy kod jako szablon startowy. Pamiętaj, aby dostosować nazwę blueprintu i ewentualny prefiks URL.

```python
from flask import Blueprint, jsonify

# 1. Zdefiniuj blueprint. Nazwa 'dashboard' będzie używana wewnątrz Flaska.
#    url_prefix sprawi, że wszystkie trasy w tym pliku będą zaczynać się od /api/dashboard
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('/summary', methods=['GET'])
def get_dashboard_summary():
    """
    Przykładowy endpoint, który w przyszłości zwróci dane
    dla głównego panelu analitycznego.
    """
    # Tutaj znajdzie się logika pobierania i agregowania danych
    summary_data = {
        'total_net_worth': 150000.75,
        'monthly_change': 1250.20
    }
    return jsonify(summary_data)

```

### Krok 3: Zarejestruj nowy Blueprint w aplikacji

Ostatnim, kluczowym krokiem jest poinformowanie aplikacji Flask o istnieniu nowego blueprintu. Otwórz plik `app/__init__.py` i zaimportuj, a następnie zarejestruj swój nowy moduł.

```python
# app/__init__.py

def create_app(config_class=Config):
    # ... istniejący kod ...

    # Rejestracja blueprintów
    from app.blueprints.home_bp import home_bp
    # ... inne importy ...
    # >>> DODAJ IMPORT NOWEGO BLUEPRINTU PONIŻEJ <<<
    from app.blueprints.dashboard_bp import dashboard_bp

    app.register_blueprint(home_bp)
    # ... inne rejestracje ...
    # >>> ZAREJESTRUJ NOWY BLUEPRINT PONIŻEJ <<<
    app.register_blueprint(dashboard_bp)

    return app
```

Gotowe! Nowe endpointy są teraz aktywne w aplikacji.