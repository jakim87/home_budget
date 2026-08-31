"""Konto demo — dane pokazowe, które można obejrzeć bez zakładania konta.

`seed_demo()` jest idempotentne: kasuje poprzedni stan konta demo i odtwarza go
od zera, więc nadaje się na nocny timer. Zwiedzający ma pełne prawa zapisu (to
zwykłe konto, nie tryb tylko-do-odczytu) — porządek robi dopiero odtworzenie.

Dane są deterministyczne (stałe ziarno losowania), żeby demo wyglądało tak samo
po każdym odtworzeniu; ruchome są tylko daty, liczone wstecz od dnia
uruchomienia — dzięki temu historia nigdy się nie zestarzeje.
"""
import logging
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import db
from app.models import Account, Category, Contractor, Frequency, RecurringTransaction, Transaction, User
from app.services.budget_service import create_transaction
from app.services.category_service import create_starter_categories

logger = logging.getLogger(__name__)

# Stałe ziarno: demo ma wyglądać identycznie po każdym nocnym odtworzeniu.
# Zmiana tej liczby = inny (nadal sensowny) zestaw kwot i dat.
SEED = 20260830
MONTHS_OF_HISTORY = 12

# Zdarzenia jednorazowe rozrzucone po historii. Bez nich krzywa majątku jest idealnie
# prosta — każdy miesiąc wygląda tak samo, więc od razu widać, że to dane wygenerowane.
# Tylko przychody i wydatki ruszają majątek netto (przelewy wewnętrzne się znoszą),
# więc zmienność musi przyjść stąd. Każde zdarzenie trafia w inny miesiąc.
ONE_OFF_EVENTS = [
    # (tytuł, kwota, kategoria, kontrahent albo None)
    ('Wakacje — Chorwacja', '-7200.00', 'Rozrywka', None),
    ('Naprawa samochodu', '-1450.00', 'Inne', None),
    ('Ubezpieczenie OC', '-1180.00', 'Inne', None),
    ('Pralka', '-2190.00', 'Inne', None),
    ('Przegląd i opony', '-890.00', 'Inne', None),
    ('Premia roczna', '4800.00', 'Inne przychody', 'Pracodawca sp. z o.o.'),
    ('Premia kwartalna', '2100.00', 'Inne przychody', 'Pracodawca sp. z o.o.'),
    ('Zwrot podatku', '1340.00', 'Inne przychody', None),
    ('Sprzedaż roweru', '850.00', 'Inne przychody', None),
]

# Konta demo. Numerów rachunków celowo nie ustawiamy — bez nich nikt nie pomyśli,
# że to czyjeś prawdziwe dane, a import wyciągu i tak pozwala wskazać konto ręcznie.
DEMO_ACCOUNTS = [
    # (nazwa, bank, typ konta, domyślne)
    ('Konto osobiste', 'ING', 'ROR', True),
    ('Konto oszczędnościowe', 'ING', 'KO', False),
    ('Karta kredytowa', 'Millennium', 'Kredyt', False),
    ('Gotówka', 'Portfel', None, False),
]

# (nazwa, reguły dopasowania, kategoria domyślna) — reguły pokazują, po czym
# aplikacja rozpoznaje kontrahenta w opisie z wyciągu bankowego.
DEMO_CONTRACTORS = [
    ('Biedronka', 'biedronka, jeronimo martins', 'Zakupy spożywcze'),
    ('Lidl', 'lidl', 'Zakupy spożywcze'),
    ('Żabka', 'zabka, żabka', 'Zakupy spożywcze'),
    ('Orlen', 'orlen, pkn orlen', 'Paliwo'),
    ('Netflix', 'netflix', 'Subskrypcje'),
    ('Spotify', 'spotify', 'Subskrypcje'),
    ('Tauron', 'tauron', 'Rachunki'),
    ('Vectra', 'vectra', 'Rachunki'),
    ('Wspólnota Mieszkaniowa', 'wspolnota, czynsz', 'Rachunki'),
    ('Apteka Gemini', 'apteka, gemini', 'Zdrowie'),
    ('Kino Helios', 'helios, kino', 'Rozrywka'),
    ('Restauracja Zielona', 'restauracja zielona', 'Inne'),
    ('Pracodawca sp. z o.o.', 'pracodawca, wynagrodzenie', 'Wynagrodzenie'),
]

# Konta, na które demo robi przelewy wewnętrzne. Dla każdego powstaje kontrahent
# "Moje konto: {nazwa}" — po tej nazwie plus kategorii typu 'transfer' aplikacja
# rozpoznaje przelew i sama dokłada drugą nogę.
DEMO_TRANSFER_TARGETS = ('Konto oszczędnościowe', 'Gotówka', 'Karta kredytowa')


def wipe_user_data(user_token: str, commit: bool = True) -> None:
    """Kasuje dane jednego użytkownika: transakcje, kontrahentów, harmonogramy, staging.

    Zostawia same konta (z wyzerowanym saldem) i kategorie — słownik kategorii
    buduje się długo i nie jest „danymi testowymi"; zerujemy jedynie powiązania
    kategorii w usuwanych rekordach.

    Dwaj wołający: przycisk „Wyczyść wszystkie dane testowe" (`/api/dev/reset`)
    oraz odtwarzanie konta demo, które dokłada do tego kasowanie kont i kategorii.

    commit=False pozwala wołającemu domknąć całość jednym commitem.
    """
    params = {'utok': user_token}
    try:
        # 1. Wyzeruj FK do kategorii — TYLKO w wierszach należących do tego użytkownika.
        for stmt in (
            "UPDATE transactions SET category_id = NULL WHERE user_token = :utok",
            "UPDATE transaction_splits SET category_id = NULL "
            "WHERE transaction_id IN (SELECT id FROM transactions WHERE user_token = :utok)",
            "UPDATE transaction_staging SET proposed_category_id = NULL WHERE user_token = :utok",
            "UPDATE recurring_transactions SET category_id = NULL WHERE user_token = :utok",
            "UPDATE planned_transactions SET category_id = NULL WHERE user_token = :utok",
            "UPDATE contractors SET default_category_id = NULL WHERE user_token = :utok",
        ):
            db.session.execute(text(stmt), params)
        db.session.flush()

        # 2. Usuń rekordy użytkownika w kolejności wymuszonej przez klucze obce.
        for stmt in (
            "DELETE FROM transaction_splits "
            "WHERE transaction_id IN (SELECT id FROM transactions WHERE user_token = :utok)",
            "DELETE FROM transaction_staging WHERE user_token = :utok",
            "DELETE FROM transaction_archive WHERE user_token = :utok",
            "DELETE FROM transactions WHERE user_token = :utok",
            "DELETE FROM recurring_transactions WHERE user_token = :utok",
            "DELETE FROM planned_transactions WHERE user_token = :utok",
            "DELETE FROM budgets WHERE user_token = :utok",
            # Historia importów trzyma FK do konta — bez tego kasowania konta
            # demo nie dają się usunąć przy odtwarzaniu.
            "DELETE FROM statement_imports WHERE user_token = :utok",
            "DELETE FROM contractors WHERE user_token = :utok",
        ):
            db.session.execute(text(stmt), params)
        db.session.flush()

        # 3. Wyzeruj salda kont użytkownika (same konta zostają).
        db.session.execute(text("UPDATE accounts SET balance = 0 WHERE user_token = :utok"), params)

        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def seed_demo(username: str, password: str) -> dict:
    """Odtwarza konto demo od zera i zwraca licznik utworzonych obiektów.

    Zakłada użytkownika, jeśli go nie ma. Hasło ustawia przy KAŻDYM uruchomieniu —
    konto jest publiczne, więc cały jego stan ma wracać do znanego punktu.
    """
    try:
        user = db.session.query(User).filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                email=f'{username}@example.invalid',
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.flush()  # nadaje token UUID — właściciela wszystkich danych niżej
        else:
            user.password_hash = generate_password_hash(password)

        utok = user.token
        wipe_user_data(utok, commit=False)
        # Konta i kategorie: kasujemy je tu, a nie w wipe_user_data, bo dla demo reset
        # ma być całkowity (zwiedzający mógł dodać konto albo usunąć kategorię —
        # kategorie znikają „miękko", więc bez tego zostałyby wyłączone na zawsze).
        db.session.execute(text("DELETE FROM accounts WHERE user_token = :t"), {'t': utok})
        db.session.execute(text("DELETE FROM categories WHERE user_token = :t"), {'t': utok})
        db.session.flush()

        create_starter_categories(utok, commit=False)
        db.session.flush()
        cats = {c.name: c for c in db.session.query(Category).filter_by(user_token=utok).all()}

        # Modele budujemy wprost, nie przez account_service/category_service: serwisy
        # commitują po każdym rekordzie (chcemy jeden commit na całe odtworzenie),
        # a ich walidacja dotyczy danych od użytkownika, nie stałych z tego pliku.
        accounts = {}
        for order, (name, bank, acc_type, is_default) in enumerate(DEMO_ACCOUNTS, start=1):
            acc = Account(
                name=name, bank_name=bank, account_type=acc_type, is_default=is_default,
                balance=Decimal('0.00'), user_token=utok, sort_order=order,
            )
            db.session.add(acc)
            accounts[name] = acc
        db.session.flush()

        contractors = {}
        for name, rules, cat_name in DEMO_CONTRACTORS:
            cont = Contractor(
                name=name, mapping_rules=rules, user_token=utok,
                default_category_id=cats[cat_name].id,
            )
            db.session.add(cont)
            contractors[name] = cont

        transfer_cat = cats['Przelew wewnętrzny']
        for target in DEMO_TRANSFER_TARGETS:
            cel = accounts[target]
            cont = Contractor(
                name=f'Moje konto: {cel.name}', user_token=utok,
                default_category_id=transfer_cat.id, linked_account_id=cel.id,
            )
            db.session.add(cont)
            contractors[f'__transfer__{target}'] = cont
        db.session.flush()

        _generate_history(utok, accounts, cats, contractors)

        # Jeden harmonogram, żeby zakładka „Cykliczne" nie była pusta.
        netflix = contractors['Netflix']
        db.session.add(RecurringTransaction(
            user_token=utok, account_id=accounts['Konto osobiste'].id,
            category_id=cats['Subskrypcje'].id, contractor_id=netflix.id,
            title='Abonament Netflix', amount=Decimal('-43.00'),
            frequency=Frequency.MONTHLY, interval=1, day_of_month=5,
            start_date=date.today().replace(day=1),
            next_run_date=_next_monthly_run(5),
        ))

        db.session.commit()
        # Liczymy ze stanu bazy, nie z list powyżej: przelew wewnętrzny dokłada
        # własnego kontrahenta zwrotnego i drugą nogę każdej transakcji.
        summary = {
            'user': username,
            'accounts': len(accounts),
            'categories': len(cats),
            'contractors': db.session.query(Contractor).filter_by(user_token=utok).count(),
            'transactions': db.session.query(Transaction).filter_by(user_token=utok).count(),
        }
        logger.info("seed-demo: odtworzono konto demo %s (%s)", username, summary)
        return summary
    except Exception:
        db.session.rollback()
        logger.exception("seed-demo: odtwarzanie konta demo nie powiodło się")
        raise


# Przykładowy wyciąg do wypróbowania importu. Format ING, jednokontowy (bez sekcji
# "Wybrane rachunki" i bez kolumny "Konto"), więc aplikacja poprosi o wskazanie konta
# — to samo w sobie jest częścią pokazu. Trzy pierwsze pozycje pasują do reguł
# kontrahentów z demo, więc kategoria podpowie się sama; DECATHLON celowo NIE pasuje,
# żeby było widać krok ręcznej kategoryzacji.
SAMPLE_STATEMENT_ROWS = [
    # (ile dni temu, kontrahent, tytuł, kwota)
    (9, 'BIEDRONKA 4021 WARSZAWA', 'Płatność kartą', '-124,80'),
    (8, 'ORLEN STACJA 1288', 'Płatność kartą', '-287,45'),
    (7, 'NETFLIX INTERNATIONAL B.V.', 'Płatność cykliczna', '-43,00'),
    (6, 'DECATHLON WARSZAWA', 'Płatność kartą', '-329,99'),
    (5, 'LIDL SP. Z O.O. SP.K.', 'Płatność kartą', '-96,17'),
    (4, 'JAN KOWALSKI', 'Zwrot za bilety', '150,00'),
    (2, 'ZABKA Z7481', 'Płatność kartą', '-31,50'),
]


def build_sample_statement_csv() -> str:
    """Buduje przykładowy wyciąg ING (CSV) z datami z ostatnich dni.

    Generowany w locie, a nie trzymany jako plik w repozytorium: dane demo mają
    ruchome daty (liczone wstecz od dziś), więc wyciąg z zamrożonymi datami
    rozjechałby się z resztą w kilka miesięcy.
    """
    today = date.today()
    naglowek = (
        'Lista transakcji;;;;;\n'
        'Przykładowy wyciąg do wypróbowania importu — dane wymyślone;;;;;\n'
        ';;;;;\n'
        'Data transakcji;Data księgowania;Dane kontrahenta;Tytuł;Nr rachunku;'
        'Kwota transakcji (waluta rachunku);Waluta\n'
    )
    wiersze = [
        f'{(today - timedelta(days=ile_dni)).isoformat()};'
        f'{(today - timedelta(days=ile_dni)).isoformat()};'
        f'{kontrahent};{tytul};;{kwota};PLN'
        for ile_dni, kontrahent, tytul, kwota in SAMPLE_STATEMENT_ROWS
    ]
    return naglowek + '\n'.join(wiersze) + '\n'


def _next_monthly_run(day_of_month: int) -> date:
    """Najbliższy przyszły dzień miesiąca o podanym numerze."""
    today = date.today()
    if today.day < day_of_month:
        return today.replace(day=day_of_month)
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(year, month, day_of_month)


def _month_starts(count: int) -> list[date]:
    """Pierwsze dni `count` ostatnich miesięcy, od najstarszego do bieżącego."""
    cursor = date.today().replace(day=1)
    months = [cursor]
    for _ in range(count - 1):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
        months.append(cursor)
    return list(reversed(months))


def _generate_history(utok, accounts, cats, contractors) -> None:
    """Tworzy historię transakcji: stałe miesięczne pozycje + losowe zakupy.

    Wszystko przez create_transaction, bo tylko ono aktualizuje saldo konta i
    dokłada drugą nogę przelewu wewnętrznego.
    """
    rng = random.Random(SEED)
    today = date.today()
    ror = accounts['Konto osobiste']
    karta = accounts['Karta kredytowa']
    gotowka = accounts['Gotówka']

    def add(account, amount, title, when, contractor_name, category_name):
        """Pomija daty z przyszłości — bieżący miesiąc jest zwykle niepełny."""
        if when > today:
            return
        cont = contractors[contractor_name] if contractor_name else None
        create_transaction(
            user_token=utok, account_id=account.id, amount=Decimal(amount),
            title=title, transaction_date=when, category_id=cats[category_name].id,
            contractor_id=cont.id if cont else None,
            contractor=cont.name if cont else None,
            commit=False, origin='manual',
        )

    months = _month_starts(MONTHS_OF_HISTORY)

    # Stan początkowy: bez tego historia zaczyna się od zera na wszystkich kontach,
    # a portfel schodzi na minus przy pierwszych zakupach za gotówkę.
    for account, kwota in ((ror, '12000.00'), (accounts['Konto oszczędnościowe'], '25000.00'),
                           (gotowka, '850.00')):
        create_transaction(
            user_token=utok, account_id=account.id, amount=Decimal(kwota),
            title='Stan początkowy', transaction_date=months[0],
            category_id=cats['Inne przychody'].id, commit=False, origin='manual',
        )

    # Karta spłacana jest z opóźnieniem jednego miesiąca (wyciąg przychodzi po fakcie),
    # więc trzymamy jej saldo z końca poprzedniego obrotu. Bez spłat karta przez rok
    # zsuwa się na kilka tysięcy debetu — nikt tak nie żyje.
    karta_do_splaty = Decimal('0.00')

    for month_start in months:
        def day(number):
            return month_start.replace(day=number)

        # --- Stałe pozycje miesiąca ---
        # Pensja lekko się waha (nadgodziny, różna liczba dni roboczych), ale zostaje
        # w wąskim przedziale — to ma być etat, nie działalność z nierównym przychodem.
        add(ror, f'{rng.randint(6480, 7120)}.{rng.randint(0, 99):02d}',
            'Wynagrodzenie', day(10), 'Pracodawca sp. z o.o.', 'Wynagrodzenie')
        add(ror, '-2350.00', 'Czynsz', day(11), 'Wspólnota Mieszkaniowa', 'Rachunki')
        # Prąd drożeje zimą — rachunek za grzanie widać w danych, tak jak w życiu.
        zima = month_start.month in (11, 12, 1, 2, 3)
        add(ror, f'-{rng.randint(240, 330) if zima else rng.randint(120, 190)}.{rng.randint(0, 99):02d}',
            'Prąd', day(12), 'Tauron', 'Rachunki')
        add(ror, '-89.00', 'Internet', day(12), 'Vectra', 'Rachunki')
        add(ror, '-43.00', 'Abonament Netflix', day(5), 'Netflix', 'Subskrypcje')
        add(ror, '-23.99', 'Abonament Spotify', day(5), 'Spotify', 'Subskrypcje')

        # Przelewy wewnętrzne — create_transaction sam dopisze wpływ na koncie
        # docelowym i zepnie obie nogi (linked_transaction_id). Na majątek netto nie
        # wpływają (znoszą się), ale zmienna kwota nie robi z oszczędności schodków.
        add(ror, f'-{rng.choice([700, 1000, 1000, 1300, 1600])}.00', 'Odkładam na wakacje',
            day(15), '__transfer__Konto oszczędnościowe', 'Przelew wewnętrzny')
        add(ror, f'-{rng.choice([300, 400, 500])}.00', 'Wypłata z bankomatu', day(8),
            '__transfer__Gotówka', 'Przelew wewnętrzny')

        # --- Zakupy: kilka w miesiącu, losowe dni i kwoty ---
        for _ in range(rng.randint(4, 7)):
            sklep = rng.choice(['Biedronka', 'Lidl', 'Żabka'])
            konto = rng.choices([ror, karta, gotowka], weights=[6, 2, 2])[0]
            add(konto, f'-{rng.randint(38, 265)}.{rng.randint(0, 99):02d}',
                f'Zakupy {sklep}', day(rng.randint(1, 28)), sklep, 'Zakupy spożywcze')

        for _ in range(2):
            konto = rng.choice([ror, karta])
            add(konto, f'-{rng.randint(180, 340)}.{rng.randint(0, 99):02d}',
                'Tankowanie', day(rng.randint(1, 28)), 'Orlen', 'Paliwo')

        # --- Pozycje okazjonalne ---
        if rng.random() < 0.5:
            add(ror, f'-{rng.randint(28, 140)}.00', 'Leki',
                day(rng.randint(1, 28)), 'Apteka Gemini', 'Zdrowie')
        if rng.random() < 0.4:
            add(gotowka, '-64.00', 'Bilety do kina',
                day(rng.randint(1, 28)), 'Kino Helios', 'Rozrywka')
        if rng.random() < 0.6:
            add(karta, f'-{rng.randint(75, 210)}.00', 'Obiad na mieście',
                day(rng.randint(1, 28)), 'Restauracja Zielona', 'Inne')

        # Spłata karty w całości, ale za POPRZEDNI miesiąc — dzięki temu karta nie
        # spirala, a demo i tak pokazuje na niej niezerowe, bieżące saldo.
        if karta_do_splaty < 0:
            add(ror, str(karta_do_splaty), 'Spłata karty kredytowej', day(20),
                '__transfer__Karta kredytowa', 'Przelew wewnętrzny')
        karta_do_splaty = Decimal(karta.balance)

    # --- Zdarzenia jednorazowe: to one łamią prostą linię majątku ---
    # Każde ląduje w innym miesiącu (sample bez powtórzeń), w losowym dniu. Wakacje
    # celowo w lipcu lub sierpniu, jeśli taki miesiąc jest w historii — inaczej
    # wyglądałyby jak przypadkowy wydatek.
    wakacje, pozostale = ONE_OFF_EVENTS[0], list(ONE_OFF_EVENTS[1:])
    lato = [m for m in months if m.month in (7, 8)]
    wolne_miesiace = list(months)
    if lato:
        title, amount, category, contractor_name = wakacje
        miesiac_wakacji = rng.choice(lato)
        add(ror, amount, title, miesiac_wakacji.replace(day=rng.randint(5, 20)),
            contractor_name, category)
        # Miesiąc wakacji wypada z puli: gdyby trafiła w niego premia, oba zdarzenia
        # zniosłyby się i wykres majątku nie pokazałby żadnego zjazdu.
        wolne_miesiace.remove(miesiac_wakacji)
    else:
        pozostale.append(wakacje)

    for (title, amount, category, contractor_name), month_start in zip(
        pozostale, rng.sample(wolne_miesiace, k=min(len(pozostale), len(wolne_miesiace)))
    ):
        add(ror, amount, title, month_start.replace(day=rng.randint(2, 27)),
            contractor_name, category)
