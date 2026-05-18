from flask import Flask
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

    return app