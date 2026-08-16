import os
from dotenv import load_dotenv

load_dotenv()

# Sygnał trybu deweloperskiego, spójny w całej aplikacji: run.py i tests/conftest.py
# ustawiają FLASK_DEBUG=1 PRZED importem tego modułu (Flask() sam czyta tę zmienną
# przy tworzeniu instancji — patrz komentarz w run.py). Poza tymi dwoma ścieżkami
# (czyli w każdym realnym wdrożeniu) zmienna nie jest ustawiona.
_IS_DEBUG = os.getenv('FLASK_DEBUG') == '1'

_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if _IS_DEBUG:
        _secret_key = 'dev-key-123'
    else:
        raise RuntimeError(
            "SECRET_KEY nie jest ustawiony w środowisku. Wymagany poza trybem debug "
            "(FLASK_DEBUG=1) — bez niego sesje logowania Flask-Login byłyby podpisywane "
            "znanym, publicznym kluczem, co pozwala sfałszować sesję dowolnego użytkownika."
        )

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = _secret_key
    # Poziom logowania: DEBUG (szczegółowo, dev) / INFO / WARNING / ERROR (produkcja).
    # Ustawiane w .env, żeby zmieniać bez ruszania kodu.
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Ciasteczko sesji Flask-Login. SECURE wyłączony tylko w debugu — lokalny serwer
    # dev działa po zwykłym http://localhost, więc ciasteczko oznaczone Secure w ogóle
    # by tam nie doszło (przeglądarka nie wysyła Secure-cookies po http).
    SESSION_COOKIE_SECURE = not _IS_DEBUG
    SESSION_COOKIE_HTTPONLY = True
    # Lax blokuje wysłanie ciasteczka sesji przy prostym cross-site POST (np. formularz
    # z obcej strony) — domyka lukę CSRF na endpointach importu (multipart/form-data),
    # które nie mają preflightu CORS jak żądania JSON.
    SESSION_COOKIE_SAMESITE = 'Lax'