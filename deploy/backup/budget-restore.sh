#!/usr/bin/env bash
#
# Odtworzenie bazy aplikacji budzetowej z kopii zapasowej.
#
# Uzycie:
#   budget-restore.sh <plik.dump.gpg> <nazwa_bazy_docelowej>
#
# Skrypt sluzy do DWOCH rzeczy i to jest zamierzone:
#   - odtworzenia produkcji po awarii,
#   - okresowego CWICZENIA odtworzenia na bazie testowej (np. budget_drill).
#
# Dlatego nie ma tu zadnej magii wykrywajacej "wlasciwa" baze: nazwe podajesz
# recznie za kazdym razem. Skrypt ODMOWI nadpisania bazy, ktora juz istnieje —
# zeby literowka w nazwie nie skasowala produkcji.

set -euo pipefail

CONFIG="${BUDGET_BACKUP_CONFIG:-/etc/budget-backup.conf}"
if [[ -r "$CONFIG" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG"
fi

PLIK="${1:-}"
BAZA="${2:-}"

if [[ -z "$PLIK" || -z "$BAZA" ]]; then
    echo "Uzycie: $0 <plik.dump.gpg> <nazwa_bazy_docelowej>" >&2
    exit 1
fi
if [[ ! -r "$PLIK" ]]; then
    echo "BLAD: nie moge odczytac kopii: $PLIK" >&2
    exit 1
fi
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE nie ustawione (plik z haslem)}"

if psql -lqt | cut -d'|' -f1 | grep -qw "$BAZA"; then
    echo "BLAD: baza '$BAZA' juz istnieje. Odtwarzam wylacznie do nowej bazy." >&2
    echo "      Usun ja swiadomie (dropdb $BAZA) albo podaj inna nazwe." >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "[1/3] Odszyfrowanie kopii"
gpg --batch --quiet --decrypt \
    --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
    "$PLIK" > "$WORKDIR/dump"

echo "[2/3] Tworzenie bazy $BAZA"
createdb "$BAZA"

echo "[3/3] Odtwarzanie danych"
pg_restore --dbname="$BAZA" --no-owner --no-privileges "$WORKDIR/dump"

echo
echo "Odtworzono. Kontrola zgodnosci — porownaj te liczby z produkcja:"
psql --dbname="$BAZA" --command "
    SELECT (SELECT count(*) FROM transactions)          AS transakcje,
           (SELECT count(*) FROM accounts)              AS konta,
           (SELECT count(*) FROM users)                 AS uzytkownicy,
           (SELECT round(sum(balance), 2) FROM accounts) AS suma_sald;"
