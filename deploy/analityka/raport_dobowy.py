"""Raport dobowy: prawdopodobne wizyty ludzi z ostatnich 24 h → mail.

Uruchamia go budget-report.timer (deploy/systemd). Konfiguracja: /etc/budget-report.conf
(wzór i instalacja: budget-report.conf.example), hasło SMTP w osobnym pliku.
Wysyłka idzie przez smtplib — serwer nie ma i nie potrzebuje własnej poczty.
Reguła „prawdopodobnie człowiek” i jej ograniczenia: goscie.py.

    python3 raport_dobowy.py --podglad     # wypisz zamiast wysyłać
"""
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import goscie

# Rotacja nginx jest dobowa, więc doba wstecz mieści się w dwóch najnowszych plikach.
LOGI = ('/var/log/nginx/access.log.1', '/var/log/nginx/access.log')
PLIK_HASLA = '/etc/budget-report.smtp-password'
# ponytail: na sztywno Gmail; inny dostawca = host i port do konfiguracji
SMTP = ('smtp.gmail.com', 587)


def zbuduj(linie, teraz, moje=(), domena='ilemamkasy.pl', dns=False):
    """Zwraca (temat, treść) raportu za 24 h kończące się w `teraz`."""
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
    obcych = sum(1 for w in lista if w['ip'] not in moje)
    od_ludzi = sum(w['zadan'] for w in lista)

    tresc = [
        f"Prawdopodobne wizyty ludzi na {domena}, "
        f"{od.astimezone():%d.%m %H:%M} – {teraz.astimezone():%d.%m %H:%M}.",
        f"Obcych: {obcych}, Twoich: {len(lista) - obcych}.",
        '',
        *([goscie.formatuj(w, moje, dns) for w in lista] or ['Nikt nie zajrzał.']),
        '',
        f"Żądań w tym czasie: {zadan} — z tego {od_ludzi} od prawdopodobnych ludzi, "
        f"reszta ({zadan - od_ludzi}) to skanery i boty.",
        'To heurystyka: wizyta z nazwą hosta amazonaws/googleusercontent to zwykle automat.',
    ]
    return f'Ile mam kasy: odwiedziny z doby ({obcych})', '\n'.join(tresc)


def wyslij(temat, tresc, adres):
    with open(PLIK_HASLA, encoding='utf-8') as f:
        haslo = f.read().strip().replace(' ', '')  # Google pokazuje hasło aplikacji ze spacjami
    wiadomosc = EmailMessage()
    wiadomosc['Subject'] = temat
    wiadomosc['From'] = wiadomosc['To'] = adres
    wiadomosc.set_content(tresc)
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
    temat, tresc = zbuduj(linie, datetime.now(timezone.utc),
                          os.environ.get('REPORT_MOJE_IP', '').split(), dns=True)
    if '--podglad' in sys.argv:
        print(temat, tresc, sep='\n\n')
    else:
        wyslij(temat, tresc, os.environ['REPORT_TO'])


if __name__ == '__main__':
    main()
