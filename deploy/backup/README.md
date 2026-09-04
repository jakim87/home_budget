# Kopie zapasowe bazy

Baza to jedyne miejsce, gdzie żyje historia finansowa użytkowników. Kod można
odtworzyć z gita, konfigurację napisać od nowa — trzech lat transakcji nie
odtworzy nikt. Ten katalog zawiera wszystko, co potrzebne, żeby kopie powstawały
same i żeby dało się z nich faktycznie wrócić.

| Plik | Rola |
| ---- | ---- |
| `budget-backup.sh` | zrzut → szyfrowanie → **weryfikacja odczytu** → rotacja |
| `budget-restore.sh` | odtworzenie kopii do wskazanej (nowej) bazy |
| `budget-backup.conf.example` | wzór `/etc/budget-backup.conf` |
| `../systemd/budget-backup.{service,timer}` | uruchamianie codziennie o 02:00 UTC |

Kopie są szyfrowane AES-256 (gpg, hasło symetryczne). Powód: zrzut bazy to
komplet danych finansowych wszystkich użytkowników w jednym pliku. Kopia leżąca
otwartym tekstem na dysku sieciowym albo w chmurze jest większym zagrożeniem niż
sama aplikacja.

## Instalacja (jednorazowo, na serwerze)

```bash
# 1. Hasło szyfrowania — wygeneruj losowe i ZAPISZ JE POZA SERWEREM
openssl rand -base64 32 > /etc/budget-backup.passphrase
chown postgres:postgres /etc/budget-backup.passphrase
chmod 600 /etc/budget-backup.passphrase

# 2. Konfiguracja
cp /opt/budget/deploy/backup/budget-backup.conf.example /etc/budget-backup.conf
$EDITOR /etc/budget-backup.conf          # ustaw BACKUP_DB i BACKUP_MIRROR_DIR
chown postgres:postgres /etc/budget-backup.conf   # skrypt chodzi jako postgres
chmod 600 /etc/budget-backup.conf

# 3. Katalog na kopie
mkdir -p /var/backups/budget
chown postgres:postgres /var/backups/budget
chmod 700 /var/backups/budget

# 4. Timer
cp /opt/budget/deploy/systemd/budget-backup.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now budget-backup.timer

# 5. Pierwszy przebieg od razu, żeby nie czekać do nocy
systemctl start budget-backup.service
journalctl -u budget-backup.service -n 20 --no-pager
```

> **Hasło szyfrowania przechowuj również poza serwerem** — w menedżerze haseł
> albo na kartce w domu. Hasło, które istnieje wyłącznie na maszynie, która
> właśnie padła, nie istnieje. Bez niego żadna kopia nie da się odtworzyć.

## Odtworzenie po awarii

```bash
# Najnowsza kopia
ls -t /var/backups/budget/*.dump.gpg | head -1

# Odtworzenie do NOWEJ bazy (skrypt odmówi nadpisania istniejącej)
sudo -u postgres /opt/budget/deploy/backup/budget-restore.sh \
    /var/backups/budget/budget-20260903-020000.dump.gpg budget_db_odtworzona
```

Skrypt na koniec wypisuje liczbę transakcji, kont, użytkowników i sumę sald —
porównaj je z tym, czego się spodziewasz, zanim przepniesz `DATABASE_URL`.

## Ćwiczenie odtworzenia — raz na kwartał

**To jest najważniejsza część i jedyna, która wymaga Twojego czasu.** Kopia,
której nigdy nie otworzyłeś, jest hipotezą, nie kopią. Skrypt sprawdza po każdym
przebiegu, czy plik da się odczytać, ale tylko pełne odtworzenie potwierdza, że
wracasz do działającej aplikacji.

```bash
sudo -u postgres /opt/budget/deploy/backup/budget-restore.sh \
    $(ls -t /var/backups/budget/*.dump.gpg | head -1) budget_drill

# Aplikacja musi wstać na odtworzonej bazie i pokazywać te same salda
DATABASE_URL=postgresql://.../budget_drill /opt/budget/venv/bin/flask db current
sudo -u postgres dropdb budget_drill      # sprzątanie po ćwiczeniu
```

Ćwiczenie jest zaliczone, gdy: liczba transakcji i suma sald zgadzają się z
produkcją **co do grosza**, `flask db current` pokazuje `head`, a logowanie
działa.

## Czego ta konfiguracja NIE robi

- **Nie wysyła powiadomienia, gdy kopia się nie uda.** Timer, który po cichu
  przestał działać, to najczęstszy sposób na obudzenie się bez kopii. Sprawdzaj
  `systemctl list-timers budget-backup.timer` i `journalctl -u budget-backup`
  przy okazji kwartalnego ćwiczenia.
- **Nie kopiuje poza serwer, dopóki `BACKUP_MIRROR_DIR` jest puste.** Bez tego
  kopie chronią przed pomyłką („skasowałem nie te transakcje"), ale nie przed
  awarią dysku ani utratą maszyny.
- **Nie obejmuje `logs/` ani plików wyciągów** — pierwsze są odtwarzalne, drugie
  aplikacja z założenia nie przechowuje.
