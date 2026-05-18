from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from app import db
from app.models import User
from app.schemas import ContractorSchema
from app.services.contractor_service import create_contractor, update_contractor, soft_delete_contractor

contractors_bp = Blueprint('contractors', __name__)

@contractors_bp.route('/api/contractors', methods=['POST'])
def add_contractor():
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    try:
        data = ContractorSchema().load(request.get_json() or {})
        new_cont, category = create_contractor(user_id, data)
        return jsonify({'id': new_cont.id, 'name': new_cont.name, 'rules': new_cont.mapping_rules, 'default_category_id': new_cont.default_category_id, 'default_category_name': category.name if category else ''}), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

@contractors_bp.route('/api/contractors/<int:c_id>', methods=['PUT'])
def edit_contractor(c_id):
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    try:
        data = ContractorSchema(partial=True).load(request.get_json() or {})
        cont, category = update_contractor(user_id, c_id, data)
        return jsonify({'id': cont.id, 'name': cont.name, 'rules': cont.mapping_rules, 'default_category_id': cont.default_category_id, 'default_category_name': category.name if category else ''}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 404

@contractors_bp.route('/api/contractors/<int:c_id>', methods=['DELETE'])
def delete_contractor(c_id):
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    try:
        soft_delete_contractor(user_id, c_id)
        return jsonify({'message': 'Kontrahent usunięty.'}), 200
    except ValueError as err:
        return jsonify({'error': str(err)}), 400