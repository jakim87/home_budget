"""Formatter logów odporny na wstrzyknięcie znaku nowej linii (A3 z audytu 2026-09-13).

Pole logowania trafia do logu jako argument (`auth_bp.py:39`), a JSON dopuszcza
`\n` w nazwie użytkownika. Bez ochrony jedno żądanie mogłoby dopisać do app.log
kilka linii wyglądających jak osobne wpisy — po wdrożeniu jaila fail2ban
`budget-auth` filtr policzyłby je jako nieudane próby z podanego adresu i zbanował
dowolne IP. Traceback (wieloliniowy, z exc_info) musi przy tym zostać nietknięty.
"""
import logging
from logging.handlers import RotatingFileHandler, WatchedFileHandler

from app.logging_config import ControlSafeFormatter


def _rekord(msg, args=None, exc_info=None):
    return logging.LogRecord(
        name='app.blueprints.auth_bp', level=logging.WARNING,
        pathname=__file__, lineno=1, msg=msg, args=args, exc_info=exc_info,
    )


def test_escapuje_nowa_linie_w_komunikacie():
    fmt = ControlSafeFormatter('%(levelname)s [%(name)s] %(message)s')
    # Atakujący próbuje wstrzyknąć drugi, sfałszowany wpis przez nazwę użytkownika.
    wstrzyk = "ofiara'\nWARNING [app.blueprints.auth_bp] Nieudana proba: 'x' (IP=9.9.9.9)"
    out = fmt.format(_rekord("Nieudana proba logowania: '%s' (IP=%s)", (wstrzyk, '1.2.3.4')))

    assert '\\n' in out, "znak nowej linii ma być widoczny, nie wykonany"
    # Sedno: cały wstrzyk zostaje w JEDNEJ linii. Filtr fail2ban dopasowuje wpis
    # od początku linii (datepattern), więc payload wewnątrz linii go nie uruchomi.
    assert len(out.splitlines()) == 1, "wstrzyknięty tekst nie może utworzyć drugiej linii"


def test_zachowuje_wieloliniowy_traceback():
    fmt = ControlSafeFormatter('%(levelname)s %(message)s')
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        out = fmt.format(_rekord("cos poszlo nie tak", exc_info=sys.exc_info()))

    # Traceback z exc_info to legalna wielolinijkowość — nie wolno jej zabić.
    assert 'Traceback' in out
    assert '\n' in out


def _handlery_plikowe():
    # nie logging.FileHandler: pytest podpina własny, piszący donikąd
    return [h for h in logging.getLogger().handlers
            if isinstance(h, (WatchedFileHandler, RotatingFileHandler))]


def test_plik_logu_nie_rotuje_sie_w_procesie(tmp_path, monkeypatch):
    """Rotacja w każdym workerze gunicorna osobno gubi historię — robi ją logrotate."""
    from flask import Flask
    from app import logging_config
    monkeypatch.setattr(logging_config, 'LOG_DIR', str(tmp_path))
    monkeypatch.setattr(logging_config, 'LOG_FILE', str(tmp_path / 'app.log'))
    przed = _handlery_plikowe()
    nowe = []
    try:
        logging_config.configure_logging(Flask('poza_testami'))
        nowe = [h for h in _handlery_plikowe() if h not in przed]
        assert [type(h) for h in nowe] == [WatchedFileHandler]
    finally:
        for h in nowe:
            logging.getLogger().removeHandler(h)
            h.close()


def test_aplikacja_testowa_nie_podpina_pliku_logu(app):
    """Każdy test woła create_app() — handlery mnożyłyby się, a wpisy z pytest
    zalewałyby logs/app.log, który służy do diagnostyki ręcznej pracy."""
    assert _handlery_plikowe() == []
