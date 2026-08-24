import os
import time
from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, current_user
from flask_marshmallow import Marshmallow
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from app.logging_config import configure_logging

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
ma = Marshmallow()
login_manager = LoginManager()

# Limity ruchu na wrażliwych endpointach (logowanie, rejestracja). Klucz = adres IP,
# więc SENSOWNIE DZIAŁA TYLKO przy TRUST_PROXY=1 — bez tego za nginx-em wszyscy
# użytkownicy wyglądają jak jeden klient (127.0.0.1) i limit obejmuje wszystkich naraz.
# ponytail: licznik w pamięci procesu — przy gunicornie z N workerami realny limit to
# N-krotność ustawionego. Wystarczy przeciw automatom; przy większym ruchu storage_uri
# na Redisa.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # limitujemy punktowo, nie globalnie
    storage_uri="memory://",  # jawnie: licznik w pamieci procesu (patrz uwaga wyzej)
)

# Import modeli bezpośrednio po utworzeniu db gwarantuje ich wykrycie przez Flask-Migrate
from app import models

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(models.User, int(user_id))

# Globalna obsługa braku autoryzacji dla zapytań API
@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'Nieautoryzowany dostęp. Proszę się zalogować.'}), 401

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    configure_logging(app)

    # Zaufanie nagłówkom proxy MUSI być opakowane przed obsługą żądań — inaczej
    # remote_addr pokazuje adres nginxa zamiast klienta (patrz TRUST_PROXY w config).
    if app.config.get('TRUST_PROXY'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db)
    ma.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Rejestracja komend CLI
    from app import cli
    cli.register_commands(app)
    # Rejestracja Blueprintów
    from app.blueprints.auth_bp import auth_bp
    from app.blueprints.home_bp import home_bp
    from app.blueprints.transactions_bp import transactions_bp
    from app.blueprints.accounts_bp import accounts_bp
    from app.blueprints.categories_bp import categories_bp
    from app.blueprints.contractors_bp import contractors_bp
    from app.blueprints.recurring_bp import recurring_bp # NEW
    from app.blueprints.planned_transactions_bp import planned_bp # NEW
    from app.blueprints.import_bp import import_bp
    from app.blueprints.legal_bp import legal_bp
    from app.blueprints.dev_bp import dev_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(contractors_bp)
    app.register_blueprint(recurring_bp) # NEW
    app.register_blueprint(planned_bp) # NEW
    app.register_blueprint(import_bp)
    app.register_blueprint(legal_bp)
    # dev_bp zawiera destrukcyjny endpoint resetu danych — rejestrujemy go tylko
    # w trybie debug/testów lub gdy jawnie włączony zmienną ENABLE_DEV_RESET.
    if app.debug or app.testing or os.getenv('ENABLE_DEV_RESET') == '1':
        app.register_blueprint(dev_bp)

    # --- Logowanie żądań HTTP ---
    # before_request/after_request to "haki", które Flask wywołuje odpowiednio
    # przed i po obsłużeniu KAŻDEGO żądania — niezależnie od blueprinta/route'a.
    # `g` to obiekt-"schowek" ważny tylko dla jednego żądania (odpowiednik
    # zmiennej lokalnej dla całego requestu), używamy go do przekazania
    # czasu startu z before_request do after_request.
    @app.before_request
    def _log_request_start():
        g._start_time = time.time()

    @app.after_request
    def _log_request_end(response):
        duration_ms = (time.time() - g.get('_start_time', time.time())) * 1000
        user = current_user.username if current_user.is_authenticated else '-'
        app.logger.info(
            "%s %s -> %s (%.1f ms) user=%s",
            request.method, request.path, response.status_code, duration_ms, user
        )
        return response

    # --- Globalny handler nieobsłużonych wyjątków ---
    # Odpowiednik ogólnego "CATCH" na końcu procedury składowanej: łapie
    # KAŻDY wyjątek, który nie został obsłużony wcześniej w blueprintach
    # (te zwykle łapią ValueError/ValidationError i zwracają czytelny JSON).
    # Tutaj zapisujemy pełny traceback do logu i zwracamy użytkownikowi
    # ogólny komunikat 500, zamiast zrzucać mu surowy błąd Pythona.
    @app.errorhandler(Exception)
    def _handle_unexpected_error(e):
        if isinstance(e, HTTPException):
            # Standardowe błędy HTTP (404, 401 itd.) — zostaw domyślną obsługę Flaska.
            return e
        app.logger.exception(
            "Nieobsłużony wyjątek podczas %s %s", request.method, request.path
        )
        return jsonify({'error': 'Wystąpił nieoczekiwany błąd serwera.'}), 500

    return app