#!/usr/bin/env bash
#
# Kopia zapasowa bazy aplikacji budzetowej.
#
# Robi trzy rzeczy, w tej kolejnosci:
#   1. zrzuca baze (pg_dump -Fc — format wlasny Postgresa, skompresowany),
#   2. szyfruje zrzut (gpg, AES-256) — zrzut to komplet danych finansowych
#      wszystkich uzytkownikow w jednym pliku, wiec lezenie go otwartym
#      gdziekolwiek poza serwerem jest gorsze niz brak kopii,
#   3. SPRAWDZA, czy powstaly plik da sie odczytac (pg_restore --list).
#
# Punkt 3 jest tu celowo. Kopia, ktorej nikt nigdy nie otworzyl, jest hipoteza,
# nie kopia — a o tym, ze byla uszkodzona, dowiadujesz sie w najgorszym momencie.
#
# Konfiguracja: /etc/budget-backup.conf (wzor obok: budget-backup.conf.example).
# Uruchamianie: budget-backup.timer (systemd), codziennie.
#
# Odtworzenie: budget-restore.sh — patrz README.md w tym katalogu.

set -euo pipefail

CONFIG="${BUDGET_BACKUP_CONFIG:-/etc/budget-backup.conf}"
if [[ -r "$CONFIG" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG"
fi

: "${BACKUP_DB:?BACKUP_DB nie ustawione (nazwa bazy, np. budget_db)}"
: "${BACKUP_DIR:?BACKUP_DIR nie ustawione (katalog na kopie)}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE nie ustawione (plik z haslem do szyfrowania)}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
BACKUP_MIRROR_DIR="${BACKUP_MIRROR_DIR:-}"

if [[ ! -r "$BACKUP_PASSPHRASE_FILE" ]]; then
    echo "BLAD: nie moge odczytac pliku z haslem: $BACKUP_PASSPHRASE_FILE" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/budget-$STAMP.dump.gpg"

# Katalog na zrzut przed zaszyfrowaniem. Kasowany zawsze, takze gdy skrypt
# przerwie sie w polowie — inaczej niezaszyfrowana kopia bazy zostawalaby
# na dysku po kazdym nieudanym przebiegu.
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "[1/4] Zrzut bazy $BACKUP_DB"
pg_dump --format=custom --file="$WORKDIR/dump" "$BACKUP_DB"

echo "[2/4] Szyfrowanie (AES-256)"
gpg --batch --yes --symmetric --cipher-algo AES256 \
    --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
    --output "$TARGET" "$WORKDIR/dump"
chmod 600 "$TARGET"

echo "[3/4] Weryfikacja odczytu"
gpg --batch --quiet --decrypt \
    --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
    "$TARGET" > "$WORKDIR/verify" 2>/dev/null
LICZBA_OBIEKTOW="$(pg_restore --list "$WORKDIR/verify" | grep -c '^[0-9]')"
if [[ "$LICZBA_OBIEKTOW" -lt 1 ]]; then
    echo "BLAD: zaszyfrowana kopia nie zawiera zadnych obiektow bazy." >&2
    rm -f "$TARGET"
    exit 1
fi
echo "      OK — $LICZBA_OBIEKTOW obiektow, $(du -h "$TARGET" | cut -f1)"

if [[ -n "$BACKUP_MIRROR_DIR" ]]; then
    # Kopia poza tym serwerem (zamontowany dysk sieciowy, rclone, cokolwiek).
    # Bez tego awaria maszyny zabiera baze RAZEM z jej kopiami zapasowymi.
    echo "[3b/4] Kopia do $BACKUP_MIRROR_DIR"
    mkdir -p "$BACKUP_MIRROR_DIR"
    cp "$TARGET" "$BACKUP_MIRROR_DIR/"
fi

echo "[4/4] Rotacja — zostawiam $BACKUP_KEEP najnowszych"
# `ls -t` sortuje po czasie modyfikacji, `tail -n +N` odcina te, ktore
# przekraczaja limit. Wzorzec dopasowuje wylacznie nasze pliki, wiec nic
# innego z katalogu nie zniknie.
mapfile -t DO_USUNIECIA < <(
    find "$BACKUP_DIR" -maxdepth 1 -name 'budget-*.dump.gpg' -printf '%T@ %p\n' \
        | sort -rn | tail -n +$((BACKUP_KEEP + 1)) | cut -d' ' -f2-
)
for stary in "${DO_USUNIECIA[@]:-}"; do
    [[ -n "$stary" ]] || continue
    echo "      usuwam $(basename "$stary")"
    rm -f "$stary"
done

echo "Gotowe: $TARGET"
