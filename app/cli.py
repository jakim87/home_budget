import click
import logging
from flask.cli import with_appcontext
from app.services.recurring_service import process_recurring_transactions
from app.services.planned_transaction_service import process_planned_transactions

logger = logging.getLogger(__name__)

def register_commands(app):
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
    @with_appcontext
    def import_excel_balance_history_command(file_path, username, execute):
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

        # Ręcznie potwierdzona grupa współdzielonego NRB (jeden fizyczny rachunek
        # pod trzema kolejnymi etykietami sub-celów oszczędnościowych w Excelu) —
        # zweryfikowane w sesji: segmenty się NIE nakładają, nazwy nie mają
        # znaczenia (cele to budżet/plany, nie osobne rachunki).
        manual_merges = {
            'Smart Saver': ['Sluchawki 1200', 'Telefon Ja', 'Robot czyszczący'],
        }

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