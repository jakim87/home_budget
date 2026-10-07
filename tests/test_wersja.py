from pathlib import Path

import config


def test_wersja_aplikacji_pochodzi_z_version_txt():
    # version.txt podbija release-please; config ma go tylko czytać, nie dublować.
    plik = Path(config.__file__).parent / 'version.txt'
    assert config.Config.APP_VERSION == plik.read_text(encoding='utf-8').strip()


def test_stopka_linkuje_wersje_do_listy_zmian(client):
    html = client.get('/o-aplikacji').get_data(as_text=True)
    assert f'href="{config.Config.APP_RELEASES_URL}"' in html
    assert f'>{config.Config.APP_VERSION}</a>' in html


def test_wersja_ma_postac_semver(app):
    assert app.config['APP_VERSION'].count('.') == 2
    assert all(czesc.isdigit() for czesc in app.config['APP_VERSION'].split('.'))
