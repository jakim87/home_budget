from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from marshmallow import ValidationError

from app.schemas import BudgetPlanSchema
from app.services import budget_plan_service as bps

budget_bp = Blueprint('budget', __name__, url_prefix='/api/budgets')


def _liczba(wartosc):
    """Decimal -> float dla JSON, spójnie z init_service (front liczy w JS)."""
    return float(wartosc) if isinstance(wartosc, Decimal) else wartosc


def _pozycja_json(p):
    sugestia = p['sugestia']
    return {
        **{k: p[k] for k in ('category_id', 'category_name', 'category_type')},
        'plan': _liczba(p['plan']),
        'wykonane': _liczba(p['wykonane']),
        'zarezerwowane': _liczba(p['zarezerwowane']),
        'sugestia': {
            'kwota': _liczba(sugestia['kwota']),
            'podstawa': sugestia['podstawa'],
            'zakres_min': _liczba(sugestia['zakres_min']),
            'zakres_max': _liczba(sugestia['zakres_max']),
            'liczba_miesiecy': sugestia['liczba_miesiecy'],
            'rok_temu': _liczba(sugestia['rok_temu']),
        },
    }


@budget_bp.route('/<int:year>/<int:month>', methods=['GET'])
@login_required
def pobierz_budzet(year, month):
    try:
        dane = bps.lista_budzetu(current_user.token, year, month)
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    return jsonify({
        'year': dane['year'],
        'month': dane['month'],
        'pozycje': [_pozycja_json(p) for p in dane['pozycje']],
        'planowane_przychody': _liczba(dane['planowane_przychody']),
        'planowane_wydatki': _liczba(dane['planowane_wydatki']),
        'bilans_planu': _liczba(dane['bilans_planu']),
    }), 200


@budget_bp.route('/<int:year>/<int:month>/<int:category_id>', methods=['PUT'])
@login_required
def zapisz_plan(year, month, category_id):
    try:
        dane = BudgetPlanSchema().load(request.get_json() or {})
        bps.ustaw_plan(current_user.token, year, month, category_id, dane['amount'])
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        # Cudza/nieistniejąca kategoria i kategoria transferowa dają ten sam 400 —
        # rozróżnienie ich statusem zdradzałoby, które ID istnieją u kogoś innego.
        return jsonify({'error': str(err)}), 400
    return jsonify({'message': 'Plan zapisany'}), 200


@budget_bp.route('/<int:year>/<int:month>/<int:category_id>', methods=['DELETE'])
@login_required
def skasuj_plan(year, month, category_id):
    try:
        bps.usun_plan(current_user.token, year, month, category_id)
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    return jsonify({'message': 'Plan usunięty'}), 200
