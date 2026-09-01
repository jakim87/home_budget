import click
import logging
import sys
from flask.cli import with_appcontext
from app.services.recurring_service import process_recurring_transactions
from app.services.planned_transaction_service import process_planned_transactions

logger = logging.getLogger(__name__)


def bezpieczny_tekst(tekst: str) -> str:
    """Przygotowuje tekst napisany przez użytkownika do wypisania na terminal.

    Dwa zagrożenia, oba wynikają z tego, że treść pisze obca osoba:

    1. Znaki sterujące (sekwencje ANSI) pozwoliłyby pokolorować, przesunąć albo
       ukryć fragment wyniku — wycinamy wszystko poza tabulacją i nową linią.
    2. Konsola Windows bywa w cp1250/cp852 i rzuca UnicodeEncodeError na znaku
       spoza swojej strony kodowej. Jedno emoji w zgłoszeniu wywaliłoby całą
       komendę, więc nieobsługiwane znaki zamieniamy na '?'.

    Używane przez komendy czytające zgłoszenia (feedback-list, feedback-delete).
    """
    czysty = ''.join(c for c in tekst if c in '\n\t' or c >= ' ')
    kodowanie = sys.stdout.encoding or 'utf-8'
    return czysty.encode(kodowanie, errors='replace').decode(kodowanie, errors='replace')

def register_commands(app):
    @app.cli.command('seed')
    @with_appcontext
    def seed_db():
        """Wypełnia bazę danymi startowymi do developmentu."""
        from app import db
        from app.models import User, Account, Category, Contractor, Transaction
        from werkzeug.security import generate_password_hash
        from datetime import date
        from decimal import Decimal

        click.echo("Seeding database...")
        user = db.session.query(User).filter_by(username="default_user").first()
        if user:
            click.echo("Default user already exists. Skipping seed.")
            return

        user = User(username="default_user", email="default@local", password_hash=generate_password_hash("password"))
        db.session.add(user)
        db.session.commit()
        click.echo("Created default_user with password 'password'.")

        # Saldo startowe = 0; transakcje ponizej same je ustala (2000.00 - 150.50 =
        # 1849.50), zamiast zaczynac konto od niezgodnej z historia liczby "z powietrza"
        # — myli przy testowaniu uzgadniania salda.
        account = Account(name="Portfel", bank_name="Gotówka", balance=Decimal('0.00'), user_token=user.token, is_default=True)
        db.session.add(account)

        cat_income = Category(name="Wynagrodzenie", type="income", user_token=user.token)
        cat_expense = Category(name="Spożywcze", type="expense", user_token=user.token)
        reconciliation_cat = Category(name="Uzgadnianie salda", type="system_reconciliation", is_system_category=True)
        db.session.add_all([cat_income, cat_expense, reconciliation_cat])
        db.session.commit()

        cont_employer = Contractor(name="Pracodawca", user_token=user.token, default_category_id=cat_income.id)
        cont_biedronka = Contractor(name="Biedronka", mapping_rules="biedronka, jeronimo", user_token=user.token, default_category_id=cat_expense.id)
        db.session.add_all([cont_employer, cont_biedronka])
        db.session.commit()

        db.session.add_all([
            Transaction(
                date=date.today(), title="Wypłata", amount=Decimal('2000.00'),
                account_id=account.id, category_id=cat_income.id, user_token=user.token,
                contractor_id=cont_employer.id
            ),
            Transaction(
                date=date.today(), title="Zakupy Biedronka", amount=Decimal('-150.50'),
                account_id=account.id, category_id=cat_expense.id, user_token=user.token,
                contractor_id=cont_biedronka.id
            ),
        ])
        account.balance = Decimal('1849.50')
        db.session.commit()
        click.echo("Database seeded successfully.")

    @app.cli.command('reset-password')
    @click.option('--user', 'username', required=True, help='Nazwa użytkownika, któremu zmieniamy hasło.')
    @click.password_option('--password', 'new_password', help='Nowe hasło (bez tej opcji zapyta interaktywnie, bez echa).')
    @with_appcontext
    def reset_password_command(username, new_password):
        """Ustawia nowe hasło użytkownika.

        Jedyna droga odzyskania konta, dopóki aplikacja nie wysyła maili — nie ma
        mechanizmu "zapomniałem hasła" dla użytkownika. Wymaga dostępu do serwera
        (SSH), więc z internetu nie da się tego wywołać.
        """
        from app import db
        from app.models import User
        from werkzeug.security import generate_password_hash

        if len(new_password) < 10:
            click.echo("Hasło musi mieć co najmniej 10 znaków (tak jak przy rejestracji).")
            return

        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            click.echo(f"Nie znaleziono użytkownika '{username}'.")
            return

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        logger.info("CLI reset-password: zmieniono hasło użytkownika %s", username)
        click.echo(f"Hasło użytkownika '{username}' zostało zmienione.")

    @app.cli.command('seed-demo')
    @with_appcontext
    def seed_demo_command():
        """Odtwarza konto demo od zera — dane pokazowe dla osób bez konta.

        Idempotentne: kasuje poprzedni stan konta demo (łącznie z tym, co
        namieszali zwiedzający) i buduje historię na nowo. Nadaje się na nocny
        timer. Nazwę i hasło bierze z konfiguracji (DEMO_USERNAME/DEMO_PASSWORD).
        """
        from flask import current_app
        from app.services.demo_service import seed_demo

        summary = seed_demo(
            current_app.config['DEMO_USERNAME'],
            current_app.config['DEMO_PASSWORD'],
        )
        click.echo(
            f"Konto demo '{summary['user']}' odtworzone: "
            f"{summary['accounts']} kont, {summary['categories']} kategorii, "
            f"{summary['contractors']} kontrahentów, {summary['transactions']} transakcji."
        )
        if not current_app.config['DEMO_ENABLED']:
            click.echo("Uwaga: DEMO_ENABLED nie jest ustawione — przycisk demo nie pokaże się na ekranie logowania.")

    @app.cli.command('feedback-list')
    @click.option('--limit', default=50, show_default=True, help='Ile ostatnich zgłoszeń wypisać.')
    @with_appcontext
    def feedback_list_command(limit):
        """Wypisuje uwagi użytkowników o aplikacji, od najnowszej.

        Jedyna droga odczytu zgłoszeń — aplikacja webowa nie ma trasy, która by
        je pokazywała, więc wymaga to dostępu do serwera.
        """
        from app.services.feedback_service import list_feedback

        zgloszenia = list_feedback(limit=limit)
        if not zgloszenia:
            click.echo('Brak zgłoszeń.')
            return

        # Separator z myślników, nie z ramek unicode — ten sam powód co wyżej.
        kreska = '-' * 72
        for z in zgloszenia:
            click.echo(kreska)
            click.echo(bezpieczny_tekst(f"#{z.id}  {z.created_at:%Y-%m-%d %H:%M} UTC  |  {z.user.username}"))
            if z.context:
                click.echo(bezpieczny_tekst(f"   {z.context}"))
            click.echo('')
            for linia in bezpieczny_tekst(z.content).splitlines() or ['(pusto)']:
                click.echo(f"   {linia}")
            click.echo('')
        click.echo(kreska)
        click.echo(f'Razem: {len(zgloszenia)}')

    @app.cli.command('feedback-delete')
    @click.option('--id', 'ids', type=int, multiple=True, required=True,
                  help='Numer zgłoszenia do usunięcia; można podać wielokrotnie.')
    @click.option('--yes', is_flag=True, default=False, help='Nie pytaj o potwierdzenie.')
    @with_appcontext
    def feedback_delete_command(ids, yes):
        """Usuwa zgłoszenia po numerze — do sprzątania śmieci i już załatwionych uwag.

        Kasowanie jest trwałe: zgłoszenia nie mają archiwum, bo nie są danymi
        finansowymi (w odróżnieniu od transakcji, które trafiają do TransactionArchive).
        """
        from app import db
        from app.models import Feedback

        znalezione = db.session.query(Feedback).filter(Feedback.id.in_(ids)).all()
        if not znalezione:
            click.echo('Nie znaleziono zgłoszeń o podanych numerach.')
            return

        for z in znalezione:
            skrot = bezpieczny_tekst(' '.join(z.content.split())[:70])
            click.echo(f"  #{z.id}  {z.user.username:16} {skrot}...")

        brakujace = set(ids) - {z.id for z in znalezione}
        if brakujace:
            click.echo(f"Pominięto nieistniejące numery: {', '.join(map(str, sorted(brakujace)))}")

        if not yes and not click.confirm(f'Usunąć trwale {len(znalezione)}?'):
            click.echo('Przerwano, nic nie usunięto.')
            return

        for z in znalezione:
            db.session.delete(z)
        db.session.commit()
        logger.info("CLI feedback-delete: usunieto %d zgloszen", len(znalezione))
        click.echo(f'Usunięto {len(znalezione)}.')

    @app.cli.command('cleanup-archive')
    @with_appcontext
    def cleanup_archive():
        """Usuwa przestarzałe wpisy z transaction_archive (> 60 dni)."""
        from app import db
        from app.models import TransactionArchive
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        deleted = db.session.query(TransactionArchive).filter(TransactionArchive.deleted_at < cutoff).delete()
        db.session.commit()
        click.echo(f"Pomyślnie usunięto {deleted} przestarzałych wpisów z archiwum.")

    @app.cli.command('process-scheduled')
    @with_appcontext
    def process_scheduled_command():
        """
        Processes all due recurring and planned transactions.
        """
        click.echo("Starting to process scheduled transactions...")
        logger.info("CLI process-scheduled: start")
        try:
            planned_count = process_planned_transactions()
            click.echo(f"-> Processed {planned_count} planned transactions.")

            recurring_count = process_recurring_transactions()
            click.echo(f"-> Processed {recurring_count} recurring transactions.")

            total = planned_count + recurring_count
            click.echo(f"Successfully created a total of {total} new transactions.")
            logger.info("CLI process-scheduled: zakończono, utworzono %d transakcji", total)
        except Exception as e:
            click.echo(f"An error occurred: {e}")
            logger.exception("CLI process-scheduled: błąd krytyczny")

    @app.cli.command('import-excel-balance-history')
    @click.option('--file', 'file_path', required=True, help='Ścieżka do pliku .xlsx z historią sald (arkusze Dictionaries, SaldoEndOfMonth).')
    @click.option('--user', 'username', required=True, help='Nazwa użytkownika, dla którego importujemy historię.')
    @click.option('--execute', is_flag=True, default=False, help='Bez tej flagi: tylko podgląd (dry-run), nic nie zapisuje do bazy.')
    @click.option('--merge', 'merges', multiple=True, help='Scalenie etykiet z Excela pod jedno konto w apce: "Nazwa konta=Etykieta1,Etykieta2". Można podać wielokrotnie.')
    @with_appcontext
    def import_excel_balance_history_command(file_path, username, execute, merges):
        """
        Jednorazowa migracja historii sald miesięcznych z arkusza XLSX (#110)
        do transakcji "Uzgadnianie salda".

        Działa WYŁĄCZNIE z kontami już istniejącymi w apce (dopasowanymi po
        numerze rachunku) — nie tworzy nowych kont. Dla dotkniętych kont USUWA
        wszystkie istniejące transakcje i odtwarza historię od zera z arkusza —
        kategorie i kontrahenci pozostają nietknięci.

        Domyślnie dry-run: pokazuje co by się stało, nic nie zapisuje.
        Z --execute: zapisuje na stałe, jedna atomowa transakcja bazy danych
        (wszystkie konta razem albo żadne).
        """
        from app import db
        from app.models import User, Account
        from app.services.budget_service import _normalize_acc_num
        from app.services.excel_history_import_service import (
            read_xlsx_sheet_rows, parse_dictionaries, parse_saldo_end_of_month,
            build_migration_report, build_rebuild_plans, execute_account_rebuild,
        )

        # Grupy współdzielonego NRB (jeden fizyczny rachunek pod kilkoma etykietami
        # sub-celów w Excelu). Zależą od konkretnego arkusza, nie od aplikacji —
        # dlatego podawane z linii poleceń, a nie zaszyte w kodzie. Scalać wolno
        # dopiero po sprawdzeniu, że segmenty etykiet NIE nakładają się w czasie.
        manual_merges = {}
        for raw in merges:
            name, sep, labels = raw.partition('=')
            parsed = [label.strip() for label in labels.split(',') if label.strip()]
            if not sep or not name.strip() or not parsed:
                raise click.BadParameter(
                    f"Oczekiwano formatu 'Nazwa konta=Etykieta1,Etykieta2', otrzymano: {raw!r}",
                    param_hint='--merge',
                )
            manual_merges[name.strip()] = parsed

        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            click.echo(f"Nie znaleziono użytkownika '{username}'.")
            return

        click.echo(f"Wczytywanie {file_path}...")
        try:
            dict_accounts = parse_dictionaries(read_xlsx_sheet_rows(file_path, 'Dictionaries'))
            balances = parse_saldo_end_of_month(read_xlsx_sheet_rows(file_path, 'SaldoEndOfMonth'))
        except (ValueError, FileNotFoundError, KeyError) as e:
            click.echo(f"Błąd odczytu pliku: {e}")
            return

        app_accounts = (
            db.session.query(Account)
            .filter_by(user_token=user.token, is_active=True)
            .filter(Account.account_number.isnot(None))
            .all()
        )
        app_by_nrb = {_normalize_acc_num(a.account_number): a.name for a in app_accounts if _normalize_acc_num(a.account_number)}
        app_id_by_name = {a.name: a.id for a in app_accounts}

        report = build_migration_report(dict_accounts, balances, app_by_nrb)

        plans = build_rebuild_plans(report, balances, manual_merges=manual_merges)
        if not plans:
            click.echo("Brak kont do migracji (zero dopasowań do istniejących kont w apce).")
            return

        click.echo(f"\n{'TRYB: DRY-RUN (podgląd, NIC nie zapisuje)' if not execute else 'TRYB: EXECUTE (zapisuje na stałe)'}\n")

        summaries = []
        for plan in sorted(plans, key=lambda p: p.app_account_name):
            account_id = app_id_by_name.get(plan.app_account_name)
            if account_id is None:
                click.echo(f"  POMINIĘTO {plan.app_account_name!r} — konto nie istnieje w apce.")
                continue
            summary = execute_account_rebuild(user.token, account_id, plan, dry_run=not execute)
            summaries.append(summary)
            click.echo(
                f"  {summary.app_account_name!r:34} | usunięto {summary.existing_tx_deleted:4} starych tx"
                f" | utworzono {summary.new_tx_created:4} nowych | okres {summary.first_date} -> {summary.last_date}"
                f" | saldo końcowe: {summary.final_balance}"
            )

        if execute:
            db.session.commit()
            click.echo(f"\nZapisano. {len(summaries)} kont zaktualizowanych.")
            logger.info("CLI import-excel-balance-history: EXECUTE, user=%s, kont=%d", username, len(summaries))
        else:
            db.session.rollback()
            click.echo("\nDry-run zakończony — NIC nie zapisano. Uruchom z --execute, żeby zapisać na stałe.")