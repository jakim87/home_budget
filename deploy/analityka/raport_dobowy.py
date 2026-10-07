"""Raport dobowy: prawdopodobne wizyty ludzi z ostatnich 24 h → mail.

Uruchamia go budget-report.timer (deploy/systemd). Konfiguracja: /etc/budget-report.conf
(wzór i instalacja: budget-report.conf.example), hasło SMTP w osobnym pliku.
Wysyłka idzie przez smtplib — serwer nie ma i nie potrzebuje własnej poczty.
Reguła „prawdopodobnie człowiek” i jej ograniczenia: goscie.py.

    python3 raport_dobowy.py --podglad     # wypisz wersję tekstową zamiast wysyłać
    python3 raport_dobowy.py --html        # wypisz wersję HTML zamiast wysyłać
"""
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape

import goscie

# Rotacja nginx jest dobowa, więc doba wstecz mieści się w dwóch najnowszych plikach.
LOGI = ('/var/log/nginx/access.log.1', '/var/log/nginx/access.log')
PLIK_HASLA = '/etc/budget-report.smtp-password'
# ponytail: na sztywno Gmail; inny dostawca = host i port do konfiguracji
SMTP = ('smtp.gmail.com', 587)

DNI = ('pon.', 'wt.', 'śr.', 'czw.', 'pt.', 'sob.', 'niedz.')
DNI_PELNE = ('poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela')
STRONY = {
    '/': 'strona główna',
    '/login': 'logowanie',
    '/login?demo=1': 'demo',
    '/login?rejestracja=1': 'rejestracja',
    '/kalkulator-kredytu': 'kalkulator kredytu',
    '/regulamin': 'regulamin',
    '/polityka-prywatnosci': 'polityka prywatności',
    '/o-aplikacji': 'o aplikacji',
}
# ponytail: tylko operatorzy widziani w logu; nieznana nazwa hosta idzie do maila bez zmian
SIECI = (
    ('centertel.pl', 'Orange komórkowy'),
    ('orange.pl', 'Orange stacjonarny'),
    ('tpnet.pl', 'Orange stacjonarny'),
    ('play-internet.pl', 'Play'),
    ('vectranet.pl', 'Vectra'),
    ('amazonaws.com', 'serwer Amazona — prawdopodobnie automat'),
    ('googleusercontent.com', 'serwer Google — prawdopodobnie automat'),
)


def siec(host):
    if not host:
        return ''
    if host == '-':
        return 'sieć nieznana'
    return next((nazwa for koncowka, nazwa in SIECI if host.endswith(koncowka)), host)


def odmien(n, jedna, kilka, wiele):
    if n == 1:
        return jedna
    return kilka if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else wiele


def _kiedy(czas):
    czas = czas.astimezone()
    return f'{DNI[czas.weekday()]} {czas:%H:%M}'


def _dzien(czas):
    czas = czas.astimezone()
    return f'{czas.day}.{czas.month:02d}'


def _wiersz(w, dns):
    strony = [STRONY.get(s, s) for s in w['strony']] or ['tylko zasoby strony']
    minuty = int(w['trwala'].total_seconds() // 60)
    return {
        'kiedy': _kiedy(w['start']),
        'trwala': f'{minuty} min' if minuty else 'poniżej 1 min',
        'sciezka': ' → '.join([strony[0][:1].upper() + strony[0][1:], *strony[1:]]),
        'akcje': w['akcje'],
        'opis': ' · '.join(filter(None, [
            ' + '.join(w['urzadzenia']),
            siec(goscie.nazwa_hosta(w['ip']) if dns else ''),
            f"z linku: {w['skad']}" if w['skad'] else '',
        ])),
        'ip': w['ip'],
    }


def zbuduj(linie, teraz, moje=(), domena='ilemamkasy.pl', dns=False):
    """Zwraca (temat, tekst, html) raportu za 24 h kończące się w `teraz`."""
    od = teraz - timedelta(hours=24)
    linie = list(linie)
    zadan = 0
    for linia in linie:
        m = goscie.LINIA.match(linia)
        if m and datetime.strptime(m.group(2), '%d/%b/%Y:%H:%M:%S %z') >= od:
            zadan += 1
    # Wizyty liczone z całego logu, dopiero potem okno: obcięcie wejścia do 24 h
    # ucinałoby początek wizyty trwającej na granicy.
    lista = [w for w in goscie.wizyty(linie, domena) if w['start'] >= od]
    obcy = [w for w in lista if w['ip'] not in moje]
    swoje = [w for w in lista if w['ip'] in moje]
    od_ludzi = sum(w['zadan'] for w in lista)

    n = len(obcy)
    ile = f"{n} {odmien(n, 'obca wizyta', 'obce wizyty', 'obcych wizyt')}" if n else 'brak obcych wizyt'
    okres = ' – '.join(
        f'{DNI_PELNE[c.astimezone().weekday()]} {_dzien(c)}, {c.astimezone():%H:%M}' for c in (od, teraz))
    liczby = (
        ('Obce wizyty', str(n)),
        ('W tym w demo', str(sum('wszedł w demo' in w['akcje'] for w in obcy))),
        ('Ruch skanerów', f'{round(100 * (zadan - od_ludzi) / zadan) if zadan else 0}%'),
    )
    wiersze = [_wiersz(w, dns) for w in obcy]
    ty = ''
    if swoje:
        k = len(swoje)
        ty = (f"Ty: {k} {odmien(k, 'wizyta', 'wizyty', 'wizyt')} ("
              + '; '.join(f"{_kiedy(w['start'])}, {w['urzadzenia'][0].split(',')[0]}" for w in swoje) + ').')
    def liczba(x):
        return f'{x:,}'.replace(',', ' ')
    stopka = (f"{liczba(zadan)} {odmien(zadan, 'żądanie', 'żądania', 'żądań')} w tym czasie, "
              f"z tego {liczba(od_ludzi)} od prawdopodobnych ludzi. Ocena „człowiek” to heurystyka.")
    dane = (domena, okres, liczby, wiersze, ty, stopka)
    return f'Ile mam kasy: {ile} ({_dzien(teraz)})', _tekst(*dane), _html(*dane)


def _tekst(domena, okres, liczby, wiersze, ty, stopka):
    czesci = [f'Odwiedziny {domena}', okres, '', ' · '.join(f'{n}: {w}' for n, w in liczby), '']
    for r in wiersze:
        akcje = f"  [{', '.join(r['akcje'])}]" if r['akcje'] else ''
        czesci += [f"{r['kiedy']} ({r['trwala']})  {r['sciezka']}{akcje}", f"    {r['opis']} · {r['ip']}"]
    if not wiersze:
        czesci.append('Nikt obcy nie zajrzał.')
    return '\n'.join([*czesci, '', *filter(None, [ty]), stopka])


KRESKA = 'border-top:1px solid #e5e3dc'


def _html(domena, okres, liczby, wiersze, ty, stopka):
    """Tabele i style w atrybutach: Gmail wycina <style>, flex i grid."""
    e = escape  # ścieżkę, odsyłacz i nazwę hosta ustala gość — wszystko z logu przez escape
    kafle = ''.join(
        '<td style="background:#f6f5f0;border-radius:8px;padding:10px 12px;width:33%">'
        f'<div style="font-size:12px;color:#5f5e5a">{e(nazwa)}</div>'
        f'<div style="font-size:22px;font-weight:bold">{e(wartosc)}</div></td>'
        for nazwa, wartosc in liczby)
    rzedy = ''
    for r in wiersze:
        plakietki = ''.join(
            ' <span style="background:#e6f1fb;color:#0c447c;font-size:12px;padding:1px 8px;'
            f'border-radius:8px;white-space:nowrap">{e(a)}</span>' for a in r['akcje'])
        rzedy += (
            f'<tr><td style="{KRESKA};padding:10px 12px 10px 0;width:92px;vertical-align:top;white-space:nowrap">'
            f'<div style="font-size:14px;font-weight:bold">{e(r["kiedy"])}</div>'
            f'<div style="font-size:12px;color:#888780">{e(r["trwala"])}</div></td>'
            f'<td style="{KRESKA};padding:10px 0;vertical-align:top">'
            f'<div style="font-size:14px">{e(r["sciezka"])}{plakietki}</div>'
            f'<div style="font-size:13px;color:#5f5e5a">{e(r["opis"])}</div>'
            f'<div style="font-size:12px;color:#888780;font-family:monospace">{e(r["ip"])}</div></td></tr>')
    if not wiersze:
        rzedy = f'<tr><td style="{KRESKA};padding:10px 0;font-size:14px">Nikt obcy nie zajrzał.</td></tr>'
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;color:#1f1f1f;max-width:600px">'
        f'<div style="font-size:18px;font-weight:bold">Odwiedziny {e(domena)}</div>'
        f'<div style="font-size:13px;color:#5f5e5a;margin-bottom:12px">{e(okres)}</div>'
        '<table role="presentation" cellspacing="8" cellpadding="0" '
        f'style="width:100%;margin-bottom:12px"><tr>{kafle}</tr></table>'
        '<div style="font-size:13px;font-weight:bold;color:#5f5e5a;margin-bottom:4px">Obcy</div>'
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        f'style="width:100%;border-bottom:1px solid #e5e3dc">{rzedy}</table>'
        + (f'<div style="font-size:13px;color:#5f5e5a;margin-top:14px">{e(ty)}</div>' if ty else '')
        + f'<div style="font-size:12px;color:#888780;margin-top:10px">{e(stopka)}</div></div>'
    )


def wyslij(temat, tekst, html, adres):
    with open(PLIK_HASLA, encoding='utf-8') as f:
        haslo = f.read().strip().replace(' ', '')  # Google pokazuje hasło aplikacji ze spacjami
    wiadomosc = EmailMessage()
    wiadomosc['Subject'] = temat
    wiadomosc['From'] = wiadomosc['To'] = adres
    wiadomosc.set_content(tekst)
    wiadomosc.add_alternative(html, subtype='html')
    with smtplib.SMTP(*SMTP, timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(adres, haslo)
        smtp.send_message(wiadomosc)


def main():
    linie = []
    for sciezka in LOGI:
        try:
            with open(sciezka, encoding='utf-8', errors='replace') as f:
                linie += f.readlines()
        except FileNotFoundError:
            pass
    temat, tekst, html = zbuduj(linie, datetime.now(timezone.utc),
                                os.environ.get('REPORT_MOJE_IP', '').split(), dns=True)
    if '--podglad' in sys.argv:
        print(temat, tekst, sep='\n\n')
    elif '--html' in sys.argv:
        print(html)
    else:
        wyslij(temat, tekst, html, os.environ['REPORT_TO'])


if __name__ == '__main__':
    main()
