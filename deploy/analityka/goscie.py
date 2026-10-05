"""Prawdopodobne wizyty ludzi na podstawie logu dostępowego nginx (format combined).

    sudo zcat -f /var/log/nginx/access.log* | TZ=Europe/Warsaw python3 goscie.py --moje 1.2.3.4

Godziny są w strefie maszyny, na której działa skrypt — stąd TZ= na serwerze (stoi w UTC).

Reguła (dobrana na logach z 21.09–05.10.2026, gdzie ~85% żądań to skanery):
  1. przeglądarka pobrała statyki strony z odsyłaczem z naszej domeny — skanery pobierają
     skrypty bez nagłówka Referer albo wcale,
  2. adres nigdy nie pytał o nieistniejącą stronę (poza favicon itp.) — skaner robi to setki razy,
  3. identyfikator przeglądarki nie przyznaje się do bycia robotem.
To heurystyka: przepuszcza roboty renderujące stronę w prawdziwej przeglądarce z chmury
(podglądy linków, skanery poczty). Odsiewa je --dns: nazwa hosta zdradza amazonaws/googleusercontent.
"""
import argparse
import re
import socket
import sys
from collections import defaultdict
from datetime import datetime, timedelta

LINIA = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) \S+ "([^"]*)" "([^"]*)"'
)
ROBOT = re.compile(r'bot|crawl|spider|compatible;|headless|scan|research|curl|wget|python|powershell|go-http|^-?$', re.I)
NIEWINNE_404 = re.compile(r'favicon|apple-touch-icon|robots\.txt|sitemap\.xml|\.well-known')
PRZERWA = timedelta(minutes=30)  # dłuższa cisza = nowa wizyta


def urzadzenie(ua):
    system = next((n for z, n in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'),
                                  ('Windows', 'Windows'), ('Mac OS X', 'Mac'), ('Linux', 'Linux'))
                   if z in ua), '?')
    # kolejność ma znaczenie: Edge i Chrome na iOS też mają w nazwie „Safari”
    przegladarka = next((n for z, n in (('FBAN', 'aplikacja Facebooka'), ('Edg', 'Edge'),
                                        ('Firefox', 'Firefox'), ('CriOS', 'Chrome'),
                                        ('Chrome', 'Chrome'), ('Safari', 'Safari'))
                         if z in ua), '?')
    return f'{system}, {przegladarka}'


def wizyty(linie, domena):
    """Zwraca listę wizyt uznanych za ludzkie, od najstarszej."""
    zadania = defaultdict(list)
    skanery = set()
    for linia in linie:
        m = LINIA.match(linia)
        if not m:
            continue
        ip, czas, metoda, sciezka, status, odsylacz, ua = m.groups()
        if status == '404' and not NIEWINNE_404.search(sciezka):
            skanery.add(ip)
        if ROBOT.search(ua):
            continue  # np. curl właściciela po wdrożeniu — nie może skreślić całej wizyty
        zadania[ip].append((datetime.strptime(czas, '%d/%b/%Y:%H:%M:%S %z'),
                            metoda, sciezka, status, odsylacz, ua))

    wynik = []
    for ip, lista in zadania.items():
        if ip in skanery:
            continue
        lista.sort(key=lambda z: z[0])
        sesja = []
        for zadanie in lista + [None]:
            if sesja and (zadanie is None or zadanie[0] - sesja[-1][0] > PRZERWA):
                wizyta = _opisz(ip, sesja, domena)
                if wizyta:
                    wynik.append(wizyta)
                sesja = []
            if zadanie:
                sesja.append(zadanie)
    return sorted(wynik, key=lambda w: w['start'])


def _opisz(ip, sesja, domena):
    ok = [z for z in sesja if z[3] in ('200', '304')]
    statyki = [z for z in ok if z[2].startswith('/static/') and domena in z[4]]
    if not statyki:
        return None
    strony = []
    for z in ok:
        if z[1] == 'GET' and not z[2].startswith(('/static/', '/api/')) and z[2] not in strony:
            strony.append(z[2])
    skad = next((z[4] for z in sesja if z[4] not in ('', '-') and domena not in z[4]), '')
    return {
        'start': sesja[0][0],
        'trwala': sesja[-1][0] - sesja[0][0],
        'ip': ip,
        'urzadzenia': sorted({urzadzenie(z[5]) for z in sesja}),
        'strony': strony,
        'zalogowany': any(z[1] == 'POST' and z[2] == '/api/login' and z[3] == '200' for z in sesja),
        'skad': skad,
    }


def nazwa_hosta(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return '-'


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--moje', nargs='*', default=[], help='własne adresy IP — oznaczane, nie ukrywane')
    p.add_argument('--domena', default='ilemamkasy.pl')
    p.add_argument('--dns', action='store_true', help='dopisz nazwę hosta (wolniejsze)')
    a = p.parse_args()

    for w in wizyty(sys.stdin, a.domena):
        kto = 'TY' if w['ip'] in a.moje else (nazwa_hosta(w['ip']) if a.dns else '')
        print(f"{w['start'].astimezone():%Y-%m-%d %H:%M}  {int(w['trwala'].total_seconds() // 60):>3} min"
              f"  {w['ip']:<15}  {' + '.join(w['urzadzenia'])}"
              f"{'  [logowanie]' if w['zalogowany'] else ''}"
              f"{'  z: ' + w['skad'] if w['skad'] else ''}"
              f"{'  (' + kto + ')' if kto else ''}")
        print(f"{'':18}{' → '.join(w['strony']) or '(tylko statyki)'}")


if __name__ == '__main__':
    main()
