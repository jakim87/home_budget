import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-123')
    # Poziom logowania: DEBUG (szczegółowo, dev) / INFO / WARNING / ERROR (produkcja).
    # Ustawiane w .env, żeby zmieniać bez ruszania kodu.
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')