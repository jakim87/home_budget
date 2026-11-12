"""Zapisane widoki zakładki Wnioski. Odczyt idzie przez /api/init (lista `saved_views`)."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from marshmallow import ValidationError

from app.schemas import SavedViewSchema
from app.services import saved_view_service as svs

views_bp = Blueprint('views', __name__, url_prefix='/api/views')


def _wykonaj(akcja, kod_sukcesu=200):
    try:
        dane = SavedViewSchema().load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    try:
        w = akcja(dane['name'], dane['config'])
    except svs.BrakWidoku as err:
        return jsonify({'error': str(err)}), 404
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    return jsonify(svs.view_dict(w)), kod_sukcesu


@views_bp.route('', methods=['POST'])
@login_required
def dodaj_widok():
    return _wykonaj(lambda nazwa, cfg: svs.create_view(current_user.token, nazwa, cfg), 201)


@views_bp.route('/<int:view_id>', methods=['PUT'])
@login_required
def zmien_widok(view_id):
    return _wykonaj(lambda nazwa, cfg: svs.update_view(current_user.token, view_id, nazwa, cfg))


@views_bp.route('/<int:view_id>', methods=['DELETE'])
@login_required
def usun_widok(view_id):
    try:
        svs.delete_view(current_user.token, view_id)
    except svs.BrakWidoku as err:
        return jsonify({'error': str(err)}), 404
    return jsonify({'message': 'Widok usunięty.'}), 200
