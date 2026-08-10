from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.services.init_service import build_init_payload

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    return render_template('base.html')

@home_bp.route('/api/init', methods=['GET'])
@login_required
def init_data():
    return jsonify(build_init_payload(current_user.token))
