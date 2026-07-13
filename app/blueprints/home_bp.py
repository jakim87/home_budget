from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Category, Contractor, Account, Transaction, User, TransactionSplit
from sqlalchemy.orm import joinedload, selectinload

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    return render_template('base.html')

@home_bp.route('/api/init', methods=['GET'])
@login_required
def init_data():
    user_token = current_user.token

    categories = db.session.query(Category).filter_by(is_active=True).order_by(Category.name).all()
    categories_data = [{'id': c.id, 'name': c.name, 'type': c.type, 'is_system_category': c.is_system_category} for c in categories]

    contractors = db.session.query(Contractor).filter_by(user_token=user_token, is_active=True).order_by(Contractor.name).all()
    category_name_map = {c.id: c.name for c in db.session.query(Category).filter_by(is_active=True).all()}
    contractors_data = [{'id': c.id, 'name': c.name, 'rules': c.mapping_rules, 'default_category_id': c.default_category_id, 'default_category_name': category_name_map.get(c.default_category_id, '')} for c in contractors]

    accounts = db.session.query(Account).filter_by(user_token=user_token, is_active=True).order_by(Account.sort_order, Account.name).all()
    accounts_data = [{'id': a.id, 'name': a.name, 'bank_name': a.bank_name, 'account_number': a.account_number, 'balance': float(a.balance), 'is_default': getattr(a, 'is_default', False), 'owner': a.owner, 'co_owner': a.co_owner, 'created_at': a.created_at.strftime('%Y-%m-%d') if a.created_at else None} for a in accounts]

    transactions = db.session.query(Transaction).options(
        joinedload(Transaction.category),
        joinedload(Transaction.contractor_details),
        selectinload(Transaction.splits).joinedload(TransactionSplit.category)
    ).filter(Transaction.user_token == user_token).order_by(Transaction.date.desc(), Transaction.id.desc()).all()

    transactions_data = []
    for tx in transactions:
        splits_data = []
        if tx.splits:
            for split in tx.splits:
                splits_data.append({
                    'id': split.id,
                    'amount': float(split.amount),
                    'desc': split.desc or '',
                    'category': split.category.name if split.category else 'Inne'
                })

        transactions_data.append({
            'id': tx.id,
            'desc': tx.title,
            'amount': float(tx.amount),
            'date': tx.date.strftime('%Y-%m-%d') if tx.date else '',
            'category': tx.category.name if tx.category else 'Inne',
            'contractor_id': tx.contractor_id,
            'contractor_name': tx.contractor_details.name if tx.contractor_details else tx.contractor,
            'account_id': tx.account_id,
            'splits': splits_data,
            'comment': tx.comment or ''
        })

    return jsonify({
        'transactions': transactions_data,
        'categories': categories_data,
        'contractors': contractors_data,
        'accounts': accounts_data
    })
