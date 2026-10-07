"""Reguła „prawdopodobnie człowiek” w deploy/analityka/goscie.py."""
import runpy
from pathlib import Path

goscie = runpy.run_path(str(Path(__file__).parents[1] / 'deploy' / 'analityka' / 'goscie.py'))

CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'


def linia(ip, czas, zadanie, status, odsylacz='-', ua=CHROME):
    return f'{ip} - - [02/Oct/2026:{czas} +0000] "{zadanie} HTTP/1.1" {status} 100 "{odsylacz}" "{ua}"'


def test_czlowiek_przechodzi_a_skanery_odpadaja():
    nasza = 'https://ilemamkasy.pl/'
    log = [
        # człowiek: strona, statyki z odsyłaczem, favicon (404 niewinne), demo
        linia('1.1.1.1', '08:00:01', 'GET /', 200, 'https://teams.example/'),
        linia('1.1.1.1', '08:00:02', 'GET /static/landing/landing.js', 200, nasza),
        linia('1.1.1.1', '08:00:03', 'GET /favicon.ico', 404, nasza),
        linia('1.1.1.1', '08:01:16', 'GET /login?demo=1', 200, nasza),
        linia('1.1.1.1', '08:01:17', 'POST /api/login', 200, nasza),
        # ten sam człowiek po dwóch godzinach — osobna wizyta
        linia('1.1.1.1', '10:30:00', 'GET /', 200),
        linia('1.1.1.1', '10:30:01', 'GET /static/landing/landing.js', 304, nasza),
        # skaner pobierający skrypty bez odsyłacza
        linia('2.2.2.2', '08:00:00', 'GET /', 200),
        linia('2.2.2.2', '08:00:01', 'GET /static/js/01_state.js', 200),
        # skaner z odsyłaczem, ale szukający cudzych plików
        linia('3.3.3.3', '08:00:00', 'GET /static/js/01_state.js', 200, nasza),
        linia('3.3.3.3', '09:00:00', 'GET /.env', 404),
        # robot, który się przedstawia
        linia('4.4.4.4', '08:00:00', 'GET /static/js/01_state.js', 200, nasza, 'Mozilla/5.0 (compatible; GPTBot/1.0)'),
        'śmieci, których nie da się sparsować',
    ]

    wynik = goscie['wizyty'](log, 'ilemamkasy.pl')

    assert [w['ip'] for w in wynik] == ['1.1.1.1', '1.1.1.1']
    pierwsza, druga = wynik
    assert pierwsza['strony'] == ['/', '/login?demo=1']
    assert pierwsza['zalogowany'] and not druga['zalogowany']
    assert pierwsza['skad'] == 'https://teams.example/'
    assert pierwsza['urzadzenia'] == ['Windows, Chrome']
    assert pierwsza['akcje'] == ['wszedł w demo'] and druga['akcje'] == []
