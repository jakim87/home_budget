"""Formatter logów odporny na wstrzyknięcie znaku nowej linii (A3 z audytu 2026-09-13).

Pole logowania trafia do logu jako argument (`auth_bp.py:39`), a JSON dopuszcza
`\n` w nazwie użytkownika. Bez ochrony jedno żądanie mogłoby dopisać do app.log
kilka linii wyglądających jak osobne wpisy — po wdrożeniu jaila fail2ban
`budget-auth` filtr policzyłby je jako nieudane próby z podanego adresu i zbanował
dowolne IP. Traceback (wieloliniowy, z exc_info) musi przy tym zostać nietknięty.
"""
import logging

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
