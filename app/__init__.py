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
    app.register_blueprint(dev_bp)

    @app.cli.command("seed")
    def seed_db():
        """Seeds the database with initial dummy data for development."""
        from app.models import User, Account, Category, Contractor, Transaction
        from werkzeug.security import generate_password_hash
        from datetime import date

        print("Seeding database...")
        user = db.session.query(User).filter_by(username="default_user").first()
        if not user:
            user = User(username="default_user", email="default@local", password_hash=generate_password_hash("password"))
            db.session.add(user)
            db.session.commit()
            print("Created default_user with password 'password'.")

            # --- Generowanie danych deweloperskich ---
            account = Account(name="Portfel", bank_name="Gotówka", balance=1500.0, user_token=user.token, is_default=True)
            db.session.add(account)

            cat_income = Category(name="Wynagrodzenie", type="income")
            cat_expense = Category(name="Spożywcze", type="expense")
            reconciliation_cat = Category(name="Uzgadnianie salda", type="system_reconciliation", is_system_category=True)
            db.session.add_all([cat_income, cat_expense, reconciliation_cat])
            db.session.commit()

            cont_employer = Contractor(name="Pracodawca", user_token=user.token, default_category_id=cat_income.id)
            cont_biedronka = Contractor(name="Biedronka", mapping_rules="biedronka, jeronimo", user_token=user.token, default_category_id=cat_expense.id)
            db.session.add_all([cont_employer, cont_biedronka])
            db.session.commit()

            tx1 = Transaction(
                date=date.today(), title="Wypłata", amount=2000.0,
                account_id=account.id, category_id=cat_income.id, user_token=user.token,
                contractor_id=cont_employer.id
            )
            tx2 = Transaction(
                date=date.today(), title="Zakupy Biedronka", amount=-150.50,
                account_id=account.id, category_id=cat_expense.id, user_token=user.token,
                contractor_id=cont_biedronka.id
            )
            db.session.add_all([tx1, tx2])
            db.session.commit()
            print("Database seeded successfully.")
        else:
            print("Default user already exists. Skipping seed.")

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