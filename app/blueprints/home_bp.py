from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Category, Contractor, Account, Transaction, User

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    return render_template('base.html')

@home_bp.route('/api/init', methods=['GET'])
def init_data():
    # Omijamy mechanizm sesji, szukając zawsze domyślnego użytkownika:
    default_user = db.session.query(User).filter_by(username="default_user").first()
    if not default_user:
        return jsonify({'error': 'Brak domyślnego użytkownika w bazie.'}), 404
    user_id = default_user.id

    # Pobieranie kategorii z bazy
    categories = db.session.query(Category).filter_by(is_active=True).all()
    categories_data = [{'name': c.name, 'type': c.type} for c in categories]
    
    # Pobieranie kontrahentów
    contractors = db.session.query(Contractor).filter_by(user_id=user_id, is_active=True).all()
    cat_map = {c.id: c.name for c in categories}
    contractors_data = [{'id': c.id, 'name': c.name, 'rules': c.mapping_rules, 'default_category_id': c.default_category_id, 'default_category_name': cat_map.get(c.default_category_id, '')} for c in contractors]

    # Pobieranie kont (Słownik kont)
    accounts = db.session.query(Account).filter_by(user_id=user_id, is_active=True).all()
    accounts_data = [{'id': a.id, 'name': a.name, 'bank_name': a.bank_name, 'account_number': a.account_number, 'balance': float(a.balance)} for a in accounts]

    # Pobieranie transakcji
    transactions_with_cat = db.session.query(Transaction, Category, Contractor).outerjoin(
        Category, Transaction.category_id == Category.id
    ).outerjoin(
        Contractor, Transaction.contractor_id == Contractor.id
    ).filter(Transaction.user_id == user_id).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        
    transactions_data = []
    for tx, cat, cont in transactions_with_cat:
        splits_data = []
        if hasattr(tx, 'splits') and tx.splits:
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
            'category': cat.name if cat else 'Inne',
            'contractor_id': tx.contractor_id,
            'contractor_name': cont.name if cont else tx.contractor,
            'splits': splits_data
        })
    
    return jsonify({
        'transactions': transactions_data,
        'categories': categories_data,
        'contractors': contractors_data,
        'accounts': accounts_data
    })