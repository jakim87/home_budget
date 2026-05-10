# Home Budget App

A web application for managing a home budget, analyzing expenses, importing bank transactions, and monitoring net worth.

This project is built as an educational application, developed step-by-step using Python, Flask, and PostgreSQL.

## Main Project Goals

- Import transactions from bank export files
- Expense analysis
- Transaction categorization
- Monthly budget planning
- Account balance monitoring
- Multi-bank and multi-currency support
- Net worth tracking
- Mortgage handling (treated as a negative value/liability)
- Manual cash balance entry
- User authentication (login)

## Supported Data Sources

Ultimately, the application aims to support:

- ING Bank Śląski
- Millennium
- mBank
- Pekao
- Revolut
- Manual cash entries

Initial development will focus on importing files from ING.

## Tech Stack

Planned technologies:

- Python
- Flask
- PostgreSQL
- SQLAlchemy
- Flask-Migrate
- HTML
- Bootstrap
- HTMX
- Chart.js
- pytest (for testing imports and logic)

## Required Tools

To run and work on this project, you will need:

- Python 3.14+
- Git
- PostgreSQL
- pgAdmin 4
- Visual Studio Code

## Planned Project Structure

```text
home-budget-app/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── templates/
│   ├── static/
│   ├── imports/
│   │   └── ing_parser.py
│   └── services/
├── local_data/         # Ignored by git (keep your bank CSVs here!)
├── migrations/
├── tests/
├── .env
├── .gitignore
├── config.py
├── requirements.txt
├── run.py
└── README.md