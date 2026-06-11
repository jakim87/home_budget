import click
from flask.cli import with_appcontext
from app.services.recurring_service import process_recurring_transactions
from app.services.planned_transaction_service import process_planned_transactions

def register_commands(app):
    @app.cli.command('process-scheduled')
    @with_appcontext
    def process_scheduled_command():
        """
        Processes all due recurring and planned transactions.
        """
        click.echo("Starting to process scheduled transactions...")
        try:
            planned_count = process_planned_transactions()
            click.echo(f"-> Processed {planned_count} planned transactions.")

            recurring_count = process_recurring_transactions()
            click.echo(f"-> Processed {recurring_count} recurring transactions.")

            total = planned_count + recurring_count
            click.echo(f"Successfully created a total of {total} new transactions.")
        except Exception as e:
            click.echo(f"An error occurred: {e}")