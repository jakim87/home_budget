"""robots.txt i sitemap.xml - pliki dla wyszukiwarek.

Trasy publiczne, bez bazy i bez logowania. Adres bierzemy z config.SITE_URL, więc
instancja pod inną domeną (SITE_URL w .env) nie wskaże robotom cudzego adresu.
"""
from xml.sax.saxutils import escape

from flask import Blueprint, Response, current_app

from app.services import legal_notice_service

seo_bp = Blueprint('seo', __name__)

# Strony do indeksu: (ścieżka, czy lastmod = data zmiany dokumentów).
# lastmod podajemy tylko tam, gdzie znamy prawdziwą datę zmiany treści - Google
# ignoruje lastmod, który za każdym razem pokazuje "dziś".
_STRONY = (
    ('/', False),
    ('/regulamin', True),
    ('/polityka-prywatnosci', True),
    ('/o-aplikacji', True),
    ('/kalkulator-kredytu', False),
)


@seo_bp.route('/robots.txt')
def robots():
    # /login celowo NIE jest tu zablokowany: robot musi pobrać stronę, żeby zobaczyć
    # jej meta noindex. /api/ jest zablokowane - to JSON, nie strony.
    tresc = (
        'User-agent: *\n'
        'Allow: /\n'
        'Disallow: /api/\n'
        '\n'
        f"Sitemap: {current_app.config['SITE_URL']}/sitemap.xml\n"
    )
    return Response(tresc, headers={'Content-Type': 'text/plain; charset=utf-8'})


@seo_bp.route('/sitemap.xml')
def sitemap():
    baza = current_app.config['SITE_URL']
    data = legal_notice_service.DOCS_LAST_UPDATED_DATE.isoformat()
    wpisy = []
    for sciezka, z_data in _STRONY:
        lastmod = f'<lastmod>{data}</lastmod>' if z_data else ''
        wpisy.append(f'<url><loc>{escape(baza + sciezka)}</loc>{lastmod}</url>')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(wpisy)
        + '\n</urlset>\n'
    )
    return Response(xml, headers={'Content-Type': 'application/xml; charset=utf-8'})
