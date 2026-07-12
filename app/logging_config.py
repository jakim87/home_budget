"""
Konfiguracja logowania dla całej aplikacji.

Kilka pojęć, jeśli logging w Pythonie jest dla Ciebie nowy (dla kogoś z SQL-a
najbliższa analogia to chyba tabela audytowa, do której RÓŻNE procedury dopisują
wiersze, każdy oznaczony poziomem ważności):

- "logger" to obiekt, który przyjmuje wiadomości (logger.info("coś się stało")).
  Każdy plik może mieć swój logger o nazwie = ścieżka modułu, np.
  "app.services.budget_service". Loggery są ułożone w hierarchię po kropkach,
  podobnie jak schema.tabela w SQL-u.
- "handler" decyduje GDZIE trafia wiadomość (u nas: do pliku logs/app.log).
- "poziom" (DEBUG < INFO < WARNING < ERROR < CRITICAL) to filtr — ustawiając
  poziom na INFO, mówimy "ignoruj wiadomości DEBUG, zapisuj INFO i wyżej".
- Loggery domyślnie "propagują" (przekazują) swoje wiadomości do loggera-rodzica,
  aż do "root loggera" na samej górze hierarchii. Dlatego wystarczy podpiąć
  nasz handler plikowy RAZ do root loggera, a złapie wiadomości ze WSZYSTKICH
  modułów aplikacji.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # katalog główny projektu
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'app.log')


def configure_logging(app):
    """Wywoływane raz, przy starcie aplikacji (w create_app())."""
    os.makedirs(LOG_DIR, exist_ok=True)

    log_level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # RotatingFileHandler = plik, który sam się "obraca": gdy app.log urośnie
    # do 2 MB, zostaje przemianowany na app.log.1 (a stary .1 na .2, itd.),
    # zapis zaczyna się od nowa w pustym app.log. Trzymamy max. 5 starych
    # plików, więc logi nie rosną w nieskończoność i nie zajmą całego dysku.
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    # Root logger zostaje na WARNING, żeby biblioteki zewnętrzne (SQLAlchemy,
    # urllib3 itp.) nie zasypywały pliku swoimi wiadomościami DEBUG/INFO.
    root_logger.setLevel(logging.WARNING)

    # app.logger to wbudowany logger Flaska — jego nazwa to "app" (bo Flask
    # tworzony jest jako Flask(__name__), a __name__ pliku app/__init__.py to "app").
    # Moduły w app/services/*.py i app/blueprints/*.py, które użyją
    # logging.getLogger(__name__), dostaną nazwy typu "app.services.budget_service"
    # — czyli są "dziećmi" loggera "app". Ustawiając poziom TUTAJ, obejmujemy
    # od razu całą aplikację, bez ustawiania poziomu w każdym pliku osobno.
    app.logger.setLevel(log_level)

    # Serwer deweloperski (werkzeug) sam loguje każde żądanie na poziomie INFO,
    # dodatkowo kolorując status kodami ANSI (czytelne w terminalu, ale
    # nieczytelne "znaczki" w pliku tekstowym). Mamy już własny, czytelniejszy
    # log żądań w before_request/after_request (app/__init__.py), więc te
    # zdublowane wpisy wyciszamy — zostają tylko WARNING/ERROR od werkzeuga
    # (np. "Debugger is active"). Trzeba ustawić TO PRZED app.run(), inaczej
    # werkzeug sam ustawi sobie poziom INFO przy starcie serwera.
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app.logger.info(
        "Logowanie skonfigurowane (poziom=%s, plik=%s)", log_level_name, LOG_FILE
    )
