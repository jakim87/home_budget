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
from flask_login import login_required, current_user

from app.services.your_service import summarize_net_worth

# 1. Zdefiniuj blueprint. Nazwa 'dashboard' będzie używana wewnątrz Flaska.
#    url_prefix sprawi, że wszystkie trasy w tym pliku będą zaczynać się od /api/dashboard
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('/summary', methods=['GET'])
@login_required
def get_dashboard_summary():
    """
    Przykładowy endpoint, który zwraca dane dla panelu analitycznego.

    Dwie rzeczy obowiązkowe w każdym endpoincie: `@login_required` oraz
    przekazanie `current_user.token` do serwisu. Blueprint sam nie sięga do bazy
    — liczy serwis, a token jest tym, co ogranicza wynik do danych właściciela.
    """
    return jsonify(summarize_net_worth(current_user.token))

```

> Endpoint przyjmujący ID w URL (`/items/<int:item_id>`) dostaje test IDOR
> w `tests/test_authorization.py` — sprawdzający, że właściciel dostaje 200,
> a obcy użytkownik 403/404. To konwencja projektu, nie sugestia.

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