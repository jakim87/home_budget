"""Indeksowanie: robots.txt, sitemap.xml, canonical, noindex na widokach prywatnych."""
import xml.etree.ElementTree as ET

from app.services import legal_notice_service

NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
PUBLICZNE = ['/', '/regulamin', '/polityka-prywatnosci', '/o-aplikacji', '/kalkulator-kredytu']


def test_robots_txt_wskazuje_sitemape_i_blokuje_api(client):
    r = client.get('/robots.txt')
    assert r.status_code == 200
    assert r.headers['Content-Type'] == 'text/plain; charset=utf-8'
    tekst = r.get_data(as_text=True)
    assert 'Sitemap: https://ilemamkasy.pl/sitemap.xml' in tekst
    assert 'Disallow: /api/' in tekst
    # /login musi być crawlowalny, inaczej robot nie zobaczy jego noindex
    assert 'Disallow: /login' not in tekst


def test_sitemap_to_poprawny_xml_z_publicznymi_adresami(client):
    r = client.get('/sitemap.xml')
    assert r.status_code == 200
    assert r.headers['Content-Type'] == 'application/xml; charset=utf-8'
    korzen = ET.fromstring(r.data)
    adresy = [u.find('s:loc', NS).text for u in korzen.findall('s:url', NS)]
    assert adresy == ['https://ilemamkasy.pl' + p for p in PUBLICZNE]


def test_sitemap_lastmod_z_daty_dokumentow(client):
    korzen = ET.fromstring(client.get('/sitemap.xml').data)
    lastmod = {
        u.find('s:loc', NS).text: u.find('s:lastmod', NS)
        for u in korzen.findall('s:url', NS)
    }
    data = legal_notice_service.DOCS_LAST_UPDATED_DATE.isoformat()
    assert lastmod['https://ilemamkasy.pl/regulamin'].text == data
    assert lastmod['https://ilemamkasy.pl/'] is None


def test_publiczne_strony_maja_200_canonical_i_opis_bez_noindex(client):
    for sciezka in PUBLICZNE:
        r = client.get(sciezka)
        assert r.status_code == 200, sciezka
        html = r.get_data(as_text=True)
        assert f'<link rel="canonical" href="https://ilemamkasy.pl{sciezka}">' in html, sciezka
        assert html.count('<meta name="description"') == 1, sciezka
        assert 'noindex' not in html, sciezka


def test_canonical_ignoruje_parametry_zapytania(client):
    html = client.get('/regulamin?utm_source=x').get_data(as_text=True)
    assert 'rel="canonical" href="https://ilemamkasy.pl/regulamin"' in html


def test_login_jest_noindex_z_canonical_na_strone_glowna(client):
    html = client.get('/login?demo=1').get_data(as_text=True)
    assert '<meta name="robots" content="noindex,follow">' in html
    assert 'rel="canonical" href="https://ilemamkasy.pl/"' in html


def test_api_ma_naglowek_noindex(client):
    r = client.get('/api/init')
    assert r.status_code == 401
    assert r.headers['X-Robots-Tag'] == 'noindex, nofollow'


def test_strony_publiczne_nie_maja_naglowka_noindex(client):
    assert 'X-Robots-Tag' not in client.get('/regulamin').headers
