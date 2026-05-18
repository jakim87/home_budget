from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager
from flask_marshmallow import Marshmallow

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
ma = Marshmallow()
login_manager = LoginManager()

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
    
    db.init_app(app)
    migrate.init_app(app, db)
    ma.init_app(app)
    login_manager.init_app(app)

    # Rejestracja Blueprintów
    from app.blueprints.auth_bp import auth_bp
    from app.blueprints.home_bp import home_bp
    from app.blueprints.transactions_bp import transactions_bp
    from app.blueprints.accounts_bp import accounts_bp
    from app.blueprints.categories_bp import categories_bp
    from app.blueprints.contractors_bp import contractors_bp
    from app.blueprints.import_bp import import_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(contractors_bp)
    app.register_blueprint(import_bp)

    # TYMCZASOWE: Automatyczne logowanie dla środowiska deweloperskiego
    @app.before_request
    def auto_login_dummy_user():
        from flask_login import current_user, login_user
        from datetime import date
        
        # Wymuszamy autologowanie i utworzenie jednego "domyślnego" użytkownika
        if not current_user.is_authenticated or getattr(current_user, 'username', '') != "default_user":
            user = db.session.query(models.User).filter_by(username="default_user").first()
            if not user:
                user = models.User(username="default_user", email="default@local", password_hash="dummy")
                db.session.add(user)
                db.session.commit()

                # --- WYGENEROWANIE DANYCH TESTOWYCH ---
                account = models.Account(name="Portfel", bank_name="Gotówka", balance=1500.0, user_id=user.id, is_default=True)
                db.session.add(account)
                db.session.commit()
                
                cat_income = models.Category(name="Wynagrodzenie", type="income")
                cat_expense = models.Category(name="Spożywcze", type="expense")
                db.session.add_all([cat_income, cat_expense])
                db.session.commit()

                # Dodajemy kontrahentów, aby słowniki nie były puste
                cont_employer = models.Contractor(name="Pracodawca", user_id=user.id, default_category_id=cat_income.id)
                cont_biedronka = models.Contractor(name="Biedronka", mapping_rules="biedronka, jeronimo", user_id=user.id, default_category_id=cat_expense.id)
                db.session.add_all([cont_employer, cont_biedronka])
                db.session.commit()

                tx1 = models.Transaction(
                    date=date.today(), title="Wypłata", amount=2000.0,
                    account_id=account.id, category_id=cat_income.id, user_id=user.id,
                    contractor_id=cont_employer.id # Powiązanie z kontrahentem
                )
                tx2 = models.Transaction(
                    date=date.today(), title="Zakupy Biedronka", amount=-150.50,
                    account_id=account.id, category_id=cat_expense.id, user_id=user.id,
                    contractor_id=cont_biedronka.id # Powiązanie z kontrahentem
                )
                db.session.add_all([tx1, tx2])
                db.session.commit()
                # ----------------------------------------

            login_user(user)

    @app.cli.command("cleanup-archive")
    def cleanup_archive():
        """Usuwa przestarzale logi z transaction_archive (> 60 dni)."""
        from app.models import TransactionArchive
        from datetime import datetime, timedelta, timezone
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        deleted = db.session.query(TransactionArchive).filter(TransactionArchive.deleted_at < cutoff).delete()
        db.session.commit()
        print(f"Pomyślnie usunięto {deleted} przestarzałych wpisów z archiwum.")

    return app