from flask import Blueprint, render_template, jsonify, redirect, request
from flask_login import login_required, current_user
from app.services.init_service import build_init_payload

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    # Zalogowany trafia od razu do aplikacji, gość widzi wizytówkę.
    if current_user.is_authenticated:
        return render_template('base.html')
    return render_template('landing.html', seo={
        'path': '/',
        'title': 'Ile mam kasy — drugi mózg od pieniędzy',
        'description': 'Salda wszystkich kont, wartość netto i plan budżetu w jednym miejscu. '
                       'Import wyciągów z polskich banków i kalkulator kredytu.',
    })

@home_bp.route('/login')
def login():
    # Ta sama aplikacja — gościowi /api/init odpowie 401 i pokaże modal logowania.
    # Skrót szybkiego wpisu z ekranu telefonu (/login?dodaj=1) ma dotrzeć do aplikacji z
    # parametrem. Adres składamy sami — nic z zapytania nie trafia do przekierowania.
    if current_user.is_authenticated:
        return redirect('/?dodaj=1' if request.args.get('dodaj') else '/')
    # Ten sam ekran co wizytówka pod innym adresem (także ?demo=1, ?rejestracja=1):
    # poza indeksem, a canonical wskazuje stronę główną.
    return render_template('base.html', seo={
        'path': '/',
        'title': 'Ile mam kasy',
        'description': 'Logowanie do aplikacji Ile mam kasy.',
        'noindex': True,
    })

@home_bp.route('/api/init', methods=['GET'])
@login_required
def init_data():
    return jsonify(build_init_payload(current_user.token))
