"""Raport dobowy z odwiedzin (deploy/analityka/raport_dobowy.py) — treść, bez wysyłki."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'deploy' / 'analityka'))
import raport_dobowy

CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
NASZA = 'https://ilemamkasy.pl/'
TERAZ = datetime(2026, 10, 8, 5, 0, tzinfo=timezone.utc)


def linia(ip, czas, zadanie, status, odsylacz='-'):
    return f'{ip} - - [{czas} +0000] "{zadanie} HTTP/1.1" {status} 100 "{odsylacz}" "{CHROME}"'


def test_raport_obejmuje_ostatnia_dobe_i_oddziela_wlasciciela_od_obcych():
    log = [
        # przedwczoraj — poza oknem 24 h
        linia('1.1.1.1', '06/Oct/2026:10:00:00', 'GET /', 200),
        linia('1.1.1.1', '06/Oct/2026:10:00:01', 'GET /static/landing/landing.js', 200, NASZA),
        # obcy w oknie: wizytówka → demo
        linia('2.2.2.2', '07/Oct/2026:18:00:00', 'GET /', 200),
        linia('2.2.2.2', '07/Oct/2026:18:00:01', 'GET /static/landing/landing.js', 200, NASZA),
        linia('2.2.2.2', '07/Oct/2026:18:00:30', 'GET /login?demo=1', 200, NASZA),
        linia('2.2.2.2', '07/Oct/2026:18:00:31', 'POST /api/login', 200, NASZA),
        # właściciel w oknie
        linia('9.9.9.9', '07/Oct/2026:19:00:00', 'GET /static/landing/landing.js', 200, NASZA),
        # skaner w oknie
        linia('3.3.3.3', '08/Oct/2026:01:00:00', 'GET /.env', 404),
        linia('3.3.3.3', '08/Oct/2026:01:00:01', 'GET /.git/config', 404),
    ]

    temat, tekst, html = raport_dobowy.zbuduj(log, TERAZ, moje=['9.9.9.9'])

    assert temat.startswith('Ile mam kasy: 1 obca wizyta (')
    for tresc in (tekst, html):
        assert '2.2.2.2' in tresc
        assert 'Strona główna → demo' in tresc
        assert 'wszedł w demo' in tresc
        assert 'Ty: 1 wizyta' in tresc
        # własne wizyty zwinięte do jednej linii, bez szczegółów
        assert '9.9.9.9' not in tresc
        assert '1.1.1.1' not in tresc
        assert '3.3.3.3' not in tresc
        assert '7 żądań w tym czasie, z tego 5 od' in tresc


def test_pusta_doba_tez_daje_raport():
    """Mail przychodzi codziennie — cisza ma znaczyć awarię, nie brak gości."""
    temat, tekst, html = raport_dobowy.zbuduj([], TERAZ)

    assert temat.startswith('Ile mam kasy: brak obcych wizyt (')
    assert 'Nikt obcy nie zajrzał' in tekst and 'Nikt obcy nie zajrzał' in html


def test_tresc_z_logu_nie_wstrzykuje_html_do_maila():
    """Ścieżkę i odsyłacz ustala gość — w mailu HTML muszą być escapowane."""
    log = [
        linia('2.2.2.2', '07/Oct/2026:18:00:00', 'GET /<img/src=x>', 200, 'https://zly.example/<b>'),
        linia('2.2.2.2', '07/Oct/2026:18:00:01', 'GET /static/landing/landing.js', 200, NASZA),
    ]

    _, _, html = raport_dobowy.zbuduj(log, TERAZ)

    assert '<img' not in html and '<b>' not in html
    assert '&lt;img/src=x&gt;' in html


def test_odmiana_liczebnikow():
    odmien = raport_dobowy.odmien
    formy = ('wizyta', 'wizyty', 'wizyt')
    assert [odmien(n, *formy) for n in (1, 2, 5, 12, 22, 25)] == [
        'wizyta', 'wizyty', 'wizyt', 'wizyt', 'wizyty', 'wizyt']


def test_siec_slowami():
    siec = raport_dobowy.siec
    assert siec('public-gprs545899.centertel.pl') == 'Orange komórkowy'
    assert 'automat' in siec('ec2-54-198-26-9.compute-1.amazonaws.com')
    assert siec('host.nieznany.example') == 'host.nieznany.example'
    assert siec('-') == 'sieć nieznana'
