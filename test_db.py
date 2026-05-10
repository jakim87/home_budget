import os
import sys

# Upewnij się, że katalog główny projektu jest na samym początku ścieżki wyszukiwania
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Wykonanie niskopoziomowego zapytania SQL
        db.session.execute(text('SELECT 1'))
        print("✅ Połączenie z bazą 'budget_db' zakończone sukcesem!")
    except Exception as e:
        print("❌ Nie udało się połączyć z bazą danych.")
        print(f"Błąd: {e}")
        print("\nUpewnij się, że:")
        print("1. PostgreSQL jest uruchomiony.")
        print("2. DATABASE_URL w pliku .env jest poprawne.")