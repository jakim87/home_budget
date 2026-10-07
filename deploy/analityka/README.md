# Odwiedziny z logu nginx

Kto zaglądał na stronę — bez skryptów śledzących i bez ciasteczek, wyłącznie
z logu dostępowego nginx (`/var/log/nginx/access.log*`, 14 dni).

| Plik | Rola |
| ---- | ---- |
| `goscie.py` | odsiewa skanery i wypisuje prawdopodobne wizyty ludzi (na żądanie) |
| `raport_dobowy.py` | wizyty z ostatnich 24 h jako mail (`budget-report.timer`, 05:00 UTC) |
| `budget-report.conf.example` | wzór `/etc/budget-report.conf` + instrukcja instalacji |

Reguła „prawdopodobnie człowiek” i jej ograniczenia są opisane w docstringu `goscie.py`.

## Plakietki w raporcie

Plakietka mówi, co gość **zrobił** w trakcie wizyty — tyle, ile widać po stronie
serwera. Każda pojawia się przy wizycie najwyżej raz, niezależnie od tego, ile razy
akcja się powtórzyła. Definicje żyją w `AKCJE` w `goscie.py`; ta tabela ma zostać
z nimi zgodna.

Liczą się tylko żądania zakończone powodzeniem (odpowiedź 2xx; dla stron także
304, czyli strona z pamięci przeglądarki). Jedyny wyjątek to „nieudane logowanie”.

| Plakietka | Co dokładnie zaszło | Wymaga zalogowania |
| --------- | ------------------- | ------------------ |
| wszedł w demo | Udane logowanie w wizycie, w której gość otworzył `/login?demo=1` — czyli kliknął „Zobacz demo” na wizytówce. | — |
| zalogował się | Każde inne udane logowanie: na własne konto **albo** na demo przyciskiem „Zobacz demo” w oknie logowania (bez `?demo=1` w adresie). Log nginx nie zawiera nazwy konta, więc tych dwóch przypadków nie da się rozróżnić. | — |
| nieudane logowanie | Próba logowania odrzucona (błędny login lub hasło). | nie |
| założył konto | Udana rejestracja nowego konta. | nie |
| otworzył kalkulator kredytu | Wejście na stronę `/kalkulator-kredytu`. Kalkulator w sekcji 04 wizytówki liczy w przeglądarce i **nie** daje plakietki. | nie |
| otworzył Budżet | Otwarcie zakładki Budżet albo zmiana miesiąca w tej zakładce. | tak |
| ustawiał budżet | Zapisanie lub usunięcie planu kwoty dla kategorii w zakładce Budżet. | tak |
| wgrał wyciąg | Import pliku z banku przyjęty przez aplikację. Plik odrzucony (zły format, złe konto) plakietki nie daje. | tak |
| pobrał przykładowy wyciąg | Pobranie pliku CSV do wypróbowania importu (link w oknie importu, tylko przy włączonym demo). | tak |
| porządkował poczekalnię | Zatwierdzenie wiersza z importu, przyjęcie proponowanego kontrahenta, oznaczenie duplikatu, „Odrzuć wszystkie” albo ponowna analiza poczekalni. | tak |
| zmieniał transakcje | Dodanie, edycja lub usunięcie transakcji, także zbiorcze. | tak |
| zmieniał inne dane | Każdy inny zapis: konta (w tym uzgodnienie salda), kategorie, kontrahenci, transakcje cykliczne i zaplanowane. | tak |
| wysłał uwagę | Wysłanie formularza zgłoszeń. Konto demo nie może go wysłać, więc to zawsze ktoś z własnym kontem. | tak |

### Demo czy własne konto?

Plakietki z „tak” w ostatniej kolumnie działają tylko po zalogowaniu, ale log nie
mówi, na jakim koncie. Rozstrzyga to druga plakietka przy tej samej wizycie:

- obok jest **wszedł w demo** → akcja zaszła w demo;
- obok jest **zalogował się** → własne konto albo demo wybrane przyciskiem w oknie
  logowania — nie do rozróżnienia;
- nie ma żadnej z nich → gość był już zalogowany z wcześniejszej wizyty (sesja
  w ciasteczku); konta nie da się ustalić z tego wiersza.

Pewność daje log aplikacji, który zapisuje nazwę konta i adres IP przy każdym
logowaniu: `grep Zalogowano /opt/budget/logs/app.log`.

### Czego plakietki nie pokażą

- Oglądania zakładek liczonych w przeglądarce: Dashboard, Transakcje, Raporty,
  Słowniki, Harmonogram. Widać dopiero zapis danych.
- Szczegółów zmiany — widać, że gość np. zmieniał transakcje, ale nie które i ile.
- Akcji nieudanych (poza logowaniem): odrzucony import czy błąd walidacji nie
  zostawiają plakietki.
