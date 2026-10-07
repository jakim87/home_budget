"""Raport dobowy z odwiedzin (deploy/analityka/raport_dobowy.py) — treść, bez wysyłki."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'deploy' / 'analityka'))
import raport_dobowy

CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
NASZA = 'https://ilemamkasy.pl/'


def linia(ip, czas, zadanie, status, odsylacz='-'):
    return f'{ip} - - [{czas} +0000] "{zadanie} HTTP/1.1" {status} 100 "{odsylacz}" "{CHROME}"'


def test_raport_obejmuje_ostatnia_dobe_i_oddziela_wlasciciela_od_obcych():
    teraz = datetime(2026, 10, 8, 5, 0, tzinfo=timezone.utc)
    log = [
        # przedwczoraj — poza oknem 24 h
        linia('1.1.1.1', '06/Oct/2026:10:00:00', 'GET /', 200),
        linia('1.1.1.1', '06/Oct/2026:10:00:01', 'GET /static/landing/landing.js', 200, NASZA),
        # obcy w oknie
        linia('2.2.2.2', '07/Oct/2026:18:00:00', 'GET /', 200),
        linia('2.2.2.2', '07/Oct/2026:18:00:01', 'GET /static/landing/landing.js', 200, NASZA),
        # właściciel w oknie
        linia('9.9.9.9', '07/Oct/2026:19:00:00', 'GET /static/landing/landing.js', 200, NASZA),
        # skaner w oknie
        linia('3.3.3.3', '08/Oct/2026:01:00:00', 'GET /.env', 404),
        linia('3.3.3.3', '08/Oct/2026:01:00:01', 'GET /.git/config', 404),
    ]

    temat, tresc = raport_dobowy.zbuduj(log, teraz, moje=['9.9.9.9'])

    assert temat == 'Ile mam kasy: odwiedziny z doby (1)'
    assert '2.2.2.2' in tresc
    assert '9.9.9.9' in tresc and '(TY)' in tresc
    assert '1.1.1.1' not in tresc
    assert '3.3.3.3' not in tresc
    assert 'Żądań w tym czasie: 5' in tresc
    assert 'reszta (2)' in tresc


def test_pusta_doba_tez_daje_raport():
    """Mail przychodzi codziennie — cisza ma znaczyć awarię, nie brak gości."""
    temat, tresc = raport_dobowy.zbuduj([], datetime(2026, 10, 8, 5, 0, tzinfo=timezone.utc))

    assert temat == 'Ile mam kasy: odwiedziny z doby (0)'
    assert 'Nikt nie zajrzał' in tresc
