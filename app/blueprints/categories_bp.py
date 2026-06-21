from flask import Blueprint, request, jsonify
from flask_login import login_required
from marshmallow import ValidationError
from app.schemas import CategorySchema
from app.services.category_service import create_category, soft_delete_category

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/api/categories', methods=['POST'])
@login_required
def add_category():
    try:
        data = CategorySchema().load(request.get_json() or {})
        new_cat = create_category(data)
        return jsonify({'name': new_cat.name, 'type': new_cat.type}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@categories_bp.route('/api/categories/<string:cat_name>', methods=['DELETE'])
@login_required
def delete_category(cat_name):
    try:
        soft_delete_category(cat_name)
        return jsonify({'message': f'Kategoria {cat_name} została usunięta.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400