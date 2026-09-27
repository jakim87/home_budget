from flask import Blueprint, render_template, jsonify, redirect
from flask_login import login_required, current_user
from app.services.init_service import build_init_payload

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    # Zalogowany trafia od razu do aplikacji, gość widzi wizytówkę.
    if current_user.is_authenticated:
        return render_template('base.html')
    return render_template('landing.html')

@home_bp.route('/login')
def login():
    # Ta sama aplikacja — gościowi /api/init odpowie 401 i pokaże modal logowania.
    if current_user.is_authenticated:
        return redirect('/')
    return render_template('base.html')

@home_bp.route('/api/init', methods=['GET'])
@login_required
def init_data():
    return jsonify(build_init_payload(current_user.token))
