# temp_114 — stan pracy nad #114 (kolumna „Konto")

> Plik roboczy do odczytu z Twojego VS Code. NIE jest częścią zadania — usuń przed mergem.

## Co zostało zrobione (kod #114)

Zmiana **wyłącznie frontendowa**, zacommitowana i wypchnięta na gałąź
`claude/next-task-noaxgh` (commit: `feat(transakcje): kolumna Konto przy widoku wszystkich kont`, ref #114).

Zmienione pliki:
- **`app/templates/base.html`**
  - nowy nagłówek tabeli transakcji: `<th id="th-tx-account" ... hidden>Konto</th>` (między „Data" a „Opis"),
  - szerokość tabeli `min-w-[850px]` → `min-w-[1000px]` (żeby nowa kolumna się nie ściskała).
- **`app/static/js/11_transactions.js`** → funkcja `renderTransactions()`
  - `showAccountColumn = !globalAccountFilter` — kolumna widoczna TYLKO przy „Wszystkie konta",
  - komórka z nazwą konta w trybie widoku i w trybie edycji inline,
  - nazwa konta przez istniejący `accountLabelById()` (obsługuje konta archiwalne), escapowana przez `escapeHtml()`.

Backend bez zmian — `account_id` jest już w danych z `/api/init`.

## Weryfikacja, która przeszła

1. `node --check app/static/js/11_transactions.js` — OK.
2. Harness jsdom (13/13 asercji PASS): kolumna pojawia się/znika zależnie od filtra,
   liczba komórek zgadza się z nagłówkiem (8 z kolumną / 7 bez) w widoku i edycji inline,
   nazwy kont poprawne, konto archiwalne rozpoznane, nazwa zescapowana.
3. Serwer podniesiony lokalnie w kontenerze, `GET /` → 200, `/api/login` → 200,
   `/api/init` → 200; wysłany HTML zawiera `th-tx-account`/`min-w-[1000px]`.

## Dlaczego strona „nie otwiera się" u Ciebie

To środowisko jest **zdalnym kontenerem w chmurze**. Serwer Flask nasłuchuje na
`localhost:5000` WEWNĄTRZ kontenera (odpowiada 200 z wnętrza), ale ten port **nie jest
przekierowany** do Twojej maszyny — dlatego przeglądarka nie ma jak się połączyć.
To nie jest błąd aplikacji ani zmiany #114.

Renderowanie przez Chromium (Playwright) potwierdziło, że strona działa, ale zrzut
full-page wyszedł zdominowany przez wielkie ikony SVG (Tailwind z CDN nie doczytał się
w czasie zrzutu w środowisku bez pełnego dostępu sieciowego — ikony bez klas rozmiaru
rozdymają się do pełnej szerokości). To też jest artefakt środowiska, nie kodu.

## Jak uruchomić u siebie w VS Code (najpewniejsza droga)

Aplikacja działa na PostgreSQL. Kroki (Windows/macOS/Linux analogicznie):

```bash
# 1. wirtualne środowisko + zależności
python -m venv venv
# Windows: venv\Scripts\activate    |  Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# 2. .env (w katalogu głównym repo) — wskaż SWOJĄ bazę Postgres:
#    DATABASE_URL=postgresql://postgres:HASLO@localhost:5432/budget_db
#    SECRET_KEY=dev-key-123
#    LOG_LEVEL=INFO
#    ENABLE_DEV_RESET=1

# 3. migracje + dane startowe
flask db upgrade
flask seed        # tworzy default_user / password

# 4. start
python run.py     # http://localhost:5000
```

Login: **default_user** / **password**.

### Jak zobaczyć kolumnę „Konto"
Domyślny seed tworzy tylko jedno konto („Portfel") — przy jednym koncie kolumna niczego
nie rozróżnia. Żeby zobaczyć efekt #114, dodaj drugie/trzecie konto z transakcjami
(w UI: zakładka Konta / formularz), albo szybciej skryptem:

```bash
python - <<'PY'
from datetime import date
from decimal import Decimal
from app import create_app, db
from app.models import Account, Transaction, Category, User
app = create_app()
with app.app_context():
    u = User.query.filter_by(username='default_user').first()
    cat = Category.query.first()
    a2 = Account(name='mBank eKonto', bank_name='mBank', balance=Decimal('0'),
                 currency='PLN', is_active=True, is_default=False, user_token=u.token)
    a3 = Account(name='ING Konto Osobiste', bank_name='ING Bank Śląski', balance=Decimal('0'),
                 currency='PLN', is_active=True, is_default=False, user_token=u.token)
    db.session.add_all([a2, a3]); db.session.flush()
    d = date.today().replace(day=15)
    txs = [
        Transaction(date=d, amount=Decimal('-89.90'), title='Zakupy Biedronka',
                    account_id=a2.id, category_id=cat.id, user_token=u.token),
        Transaction(date=d, amount=Decimal('-42.50'), title='Zakupy Biedronka',
                    account_id=a3.id, category_id=cat.id, user_token=u.token),
        Transaction(date=d, amount=Decimal('5000.00'), title='Wynagrodzenie',
                    account_id=a3.id, category_id=cat.id, user_token=u.token),
        Transaction(date=d.replace(day=10), amount=Decimal('-120.00'), title='Paliwo Orlen',
                    account_id=a2.id, category_id=cat.id, user_token=u.token),
    ]
    for t in txs:
        a = db.session.get(Account, t.account_id)
        a.balance = (a.balance or Decimal('0')) + t.amount
    db.session.add_all(txs); db.session.commit()
    print('OK — konta:', [(a.id, a.name) for a in Account.query.order_by(Account.id).all()])
PY
```

Potem w UI:
- zakładka **Transakcje**,
- „Widok konta" = **Wszystkie konta** → kolumna **Konto** widoczna, wiersze pokazują
  nazwy kont (dwie transakcje „Zakupy Biedronka" tego samego dnia na różnych kontach są
  już rozróżnialne — dokładnie przypadek z issue),
- wybierz konkretne konto → kolumna **znika** (cała tabela dotyczy jednego konta).

## Pliki pomocnicze (NIE commitować)

- `shot.py` — skrypt Playwright do zrzutów (artefakt debugowy).
- `shot_all.png`, `shot_one.png` — zrzuty.
- `temp_114.md` — ten plik.
- `.env`, `venv/`, `instance/` — środowisko lokalne (`.env`, `venv` są w `.gitignore`;
  `instance/` warto dodać do `.gitignore`, to standard Flaska).

## Stan repo

Gałąź `claude/next-task-noaxgh` = zsynchronizowana z `origin`. Sam commit #114 jest czysty
(tylko `base.html` + `11_transactions.js`) — pliki pomocnicze powyżej są nietrackowane
i nie wchodzą do commita.
