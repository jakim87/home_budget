"""Front nie ładuje niczego z zewnętrznych hostów.

Każdy skrypt, arkusz stylów czy czcionka z CDN to adres IP użytkownika wysłany obcemu
dostawcy (często poza EOG) — polityka prywatności tego nie przewiduje. Tailwind, Chart.js,
driver.js i czcionki leżą w app/static; ten test pilnuje, żeby nikt nie dołożył z powrotem
<script src="https://..."> ani @import z Google Fonts.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / 'app'

ZEWNETRZNY_ZASOB = re.compile(
    r'<script[^>]*\ssrc=["\']?(?:https?:)?//'
    r'|<link[^>]*\shref=["\']?(?:https?:)?//'
    r'|@import\s+(?:url\()?["\']?(?:https?:)?//'
    r'|url\(["\']?(?:https?:)?//',
    re.IGNORECASE,
)


def _pliki():
    yield from (APP / 'templates').rglob('*.html')
    for css in (APP / 'static').rglob('*.css'):
        if 'vendor' not in css.parts:
            yield css


def test_szablony_i_style_nie_laduja_zasobow_z_zewnetrznych_hostow():
    naruszenia = []
    for plik in _pliki():
        for nr, linia in enumerate(plik.read_text(encoding='utf-8').splitlines(), 1):
            if ZEWNETRZNY_ZASOB.search(linia):
                naruszenia.append(f'{plik.relative_to(APP)}:{nr}: {linia.strip()[:120]}')
    assert not naruszenia, 'Zasoby z zewnętrznych hostów:\n' + '\n'.join(naruszenia)


def test_lokalne_zasoby_z_szablonow_istnieja():
    # url_for('static', filename=...) nie sprawdza, czy plik istnieje — literówka dałaby 404
    # i aplikację bez stylów, a testy przeszłyby na zielono.
    sciezki = set()
    for szablon in (APP / 'templates').rglob('*.html'):
        sciezki |= set(re.findall(r"url_for\('static',\s*filename='([^']+)'\)", szablon.read_text(encoding='utf-8')))
    brak = sorted(s for s in sciezki if not (APP / 'static' / s).is_file())
    assert not brak, f'Brak plików w app/static: {brak}'
