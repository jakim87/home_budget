from flask import Blueprint, render_template, jsonify, request
from app import db
from app.models import Transaction, Category, User, Account, TransactionArchive, TransactionSplit
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Pamiętaj, aby przenieść plik base.html do folderu app/templates/
    # Możesz też zmienić jego nazwę na index.html i użyć render_template('index.html')
    return render_template('base.html')

@main_bp.route('/api/init', methods=['GET'])
def init_data():
    """
    Zwraca startowe dane dla frontendu. 
    """
    # 1. Pobieranie kategorii z bazy
    categories = db.session.query(Category).filter_by(is_active=True).all()
    if not categories:
        # Mockowanie początkowych kategorii, jeśli baza jest pusta
        categories = [
            Category(name='Jedzenie', type='expense'),
            Category(name='Wynagrodzenie', type='income'),
            Category(name='Inne', type='expense')
        ]
        db.session.add_all(categories)
        db.session.commit()
        
    categories_data = [{'name': c.name, 'type': c.type} for c in categories]
    
    # 2. Pobieranie transakcji i formatowanie ich dla frontendu
    transactions_with_cat = db.session.query(Transaction, Category).outerjoin(Category, Transaction.category_id == Category.id).all()
    transactions_data = []
    for tx, cat in transactions_with_cat:
        splits_data = []
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
            'splits': splits_data
        })
    
    return jsonify({
        'transactions': transactions_data,
        'categories': categories_data
    })

@main_bp.route('/api/transactions', methods=['POST'])
def add_transaction():
    """Zapisuje nową transakcję wysłaną przez formularz frontendu."""
    data = request.get_json()
    
    # 1. Mockowanie użytkownika i konta - model Transaction wymaga kluczy obcych!
    user = db.session.query(User).first()
    if not user:
        user = User(username="default_user", email="user@example.com", password_hash="secret")
        db.session.add(user)
        db.session.commit()

    account = db.session.query(Account).first()
    if not account:
        account = Account(name="Portfel domyślny", bank_name="Brak", balance=0.0, user_id=user.id)
        db.session.add(account)
        db.session.commit()

    # 2. Przygotowanie danych (bezpieczne pobieranie wartości z JSON)
    title = data.get('title') or data.get('desc', 'Bez tytułu')
    amount = float(data.get('amount', 0.0))
    date_str = data.get('date')
    tx_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.today().date()

    # Powiązanie transakcji z kategorią pobraną z bazy
    category_name = data.get('category')
    category = db.session.query(Category).filter_by(name=category_name).first()

    # 3. Zapis do bazy
    new_tx = Transaction(
        title=title,
        amount=amount,
        date=tx_date,
        account_id=account.id,
        user_id=user.id,
        category_id=category.id if category else None
    )
    db.session.add(new_tx)
    db.session.commit()
    
    # Zwracamy pełny obiekt transakcji, aby frontend mógł go od razu wyświetlić
    return jsonify({
        'id': new_tx.id,
        'desc': new_tx.title,
        'amount': float(new_tx.amount),
        'date': new_tx.date.strftime('%Y-%m-%d'),
        'category': category.name if category else 'Inne',
        'splits': []
    }), 201

@main_bp.route('/api/categories', methods=['POST'])
def add_category():
    """Zapisuje nową kategorię wysłaną przez formularz frontendu."""
    data = request.get_json()
    name = data.get('name')
    cat_type = data.get('type')

    # Zabezpieczenie na wypadek dublowania nazwy
    if db.session.query(Category).filter_by(name=name).first():
        return jsonify({'error': 'Kategoria o tej nazwie już istnieje'}), 400

    new_cat = Category(name=name, type=cat_type)
    db.session.add(new_cat)
    db.session.commit()

    return jsonify({
        'name': new_cat.name,
        'type': new_cat.type
    }), 201

@main_bp.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    """Usuwa transakcję przenosząc ją najpierw do tabeli archiwalnej (shadow table)."""
    tx = db.get_or_404(Transaction, tx_id)
    
    # 1. Kopiowanie do Shadow Table
    archive_tx = TransactionArchive(
        original_id=tx.id,
        title=tx.title,
        amount=tx.amount,
        date=tx.date,
        account_id=tx.account_id,
        category_id=tx.category_id,
        user_id=tx.user_id
    )
    db.session.add(archive_tx)
    
    # 2. Hard Delete z tabeli faktów
    db.session.delete(tx)
    db.session.commit()
    
    return jsonify({'message': 'Transakcja zarchiwizowana i usunięta.'}), 200

@main_bp.route('/api/categories/<string:cat_name>', methods=['DELETE'])
def delete_category(cat_name):
    """Wykonuje miękkie usunięcie (soft delete) kategorii o podanej nazwie."""
    category = db.session.query(Category).filter_by(name=cat_name).first()
    if not category:
        return jsonify({'error': 'Nie znaleziono kategorii.'}), 404
        
    category.is_active = False
    db.session.commit()
    
    return jsonify({'message': f'Kategoria {cat_name} została usunięta.'}), 200

@main_bp.route('/api/transactions/<int:tx_id>', methods=['PUT'])
def update_transaction(tx_id):
    """Aktualizuje transakcję (na ten moment głównie jej podziały - splits)."""
    tx = db.get_or_404(Transaction, tx_id)
    data = request.get_json()

    if 'splits' in data:
        tx.splits.clear() # Czyści stare podziały (SQLAlchemy usunie je automatycznie z bazy)
        
        for split_data in data['splits']:
            cat_name = split_data.get('category')
            cat = db.session.query(Category).filter_by(name=cat_name).first()
            
            new_split = TransactionSplit(
                amount=float(split_data.get('amount', 0)),
                desc=split_data.get('desc', ''),
                category_id=cat.id if cat else None
            )
            tx.splits.append(new_split)
            
    db.session.commit()
    return jsonify({'message': 'Transakcja zaktualizowana pomyślnie.'}), 200