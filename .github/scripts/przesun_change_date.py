"""Przesuwa `Change Date` w pliku LICENSE (BSL 1.1) o 4 lata od podanego dnia.

Wołane z .github/workflows/release.yml przy wydaniu MINOR/MAJOR. BSL pozwala na datę
najwyżej 4 lata od pierwszej publikacji wersji — wywołanie w dniu przygotowania
wydania daje datę nie późniejszą niż ta granica (wydanie powstaje najwcześniej dziś).

Użycie: python przesun_change_date.py LICENSE [RRRR-MM-DD]   (domyślnie: dziś)
"""
import re
import sys
from datetime import date

WZORZEC = re.compile(r'^(Change Date:\s+)\d{4}-\d{2}-\d{2}', re.MULTILINE)


def przesun(tekst: str, dzis: date) -> str:
    try:
        nowa = dzis.replace(year=dzis.year + 4)
    except ValueError:  # 29 lutego -> 28 lutego (rok +4 też przestępny, ale zostawiamy bezpiecznie)
        nowa = dzis.replace(year=dzis.year + 4, day=28)
    wynik, ile = WZORZEC.subn(lambda m: m.group(1) + nowa.isoformat(), tekst)
    if ile != 1:
        raise ValueError('W LICENSE nie znaleziono dokładnie jednego pola "Change Date:"')
    return wynik


if __name__ == '__main__':
    sciezka = sys.argv[1]
    dzis = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    with open(sciezka, encoding='utf-8', newline='') as f:
        tekst = f.read()
    with open(sciezka, 'w', encoding='utf-8', newline='') as f:
        f.write(przesun(tekst, dzis))
