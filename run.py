import os

# python run.py to zawsze lokalny serwer deweloperski (app.run(debug=True) poniżej) —
# ustawiamy FLASK_DEBUG PRZED importem app/config, żeby Flask() i config.py widziały
# spójny stan debug od samego startu (m.in. fallback SECRET_KEY, flagi ciasteczka sesji).
os.environ.setdefault('FLASK_DEBUG', '1')

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)