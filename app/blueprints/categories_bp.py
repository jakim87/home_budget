from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app.schemas import CategorySchema
from app.services.category_service import create_category, soft_delete_category

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/api/categories', methods=['POST'])
@login_required
def add_category():
    try:
        data = CategorySchema().load(request.get_json() or {})
        new_cat = create_category(current_user.token, data)
        # Kształt MUSI odpowiadać kategorii z /api/init — front robi categories.push(saved)
        # i renderuje ją w selektach po ID (rec-category/planned-category). Bez 'id'
        # nowa kategoria trafiała tam jako <option value="undefined">.
        return jsonify({
            'id': new_cat.id,
            'name': new_cat.name,
            'type': new_cat.type,
            'is_system_category': new_cat.is_system_category,
        }), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@categories_bp.route('/api/categories/<string:cat_name>', methods=['DELETE'])
@login_required
def delete_category(cat_name):
    try:
        soft_delete_category(current_user.token, cat_name)
        return jsonify({'message': f'Kategoria {cat_name} została usunięta.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400