from flask import Blueprint, render_template, jsonify, request
from app import db
from app.models import Transaction, Category, User, Account, TransactionArchive, TransactionSplit
from datetime import datetime
from app.services.budget_service import parse_ing_csv, save_transactions_to_staging

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
    user = db.session.query(User).first()
    if user:
        transactions_with_cat = db.session.query(Transaction, Category).outerjoin(Category, Transaction.category_id == Category.id).filter(Transaction.user_id == user.id).all()
    else:
        transactions_with_cat = []
        
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

    # 3. Zapis do bazy za pomocą serwisu (który przy okazji zaktualizuje saldo konta)
    new_tx = create_transaction(
        user_id=user.id,
        account_id=account.id,
        amount=amount,
        title=title,
        transaction_date=tx_date,
        category_id=category.id if category else None
    )
    
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
    """Aktualizuje transakcję (podstawowe dane oraz podziały)."""
    tx = db.get_or_404(Transaction, tx_id)
    data = request.get_json()

    # 1. Aktualizacja głównych danych transakcji
    if 'title' in data or 'desc' in data:
        tx.title = data.get('title') or data.get('desc', tx.title)
    if 'amount' in data:
        tx.amount = float(data.get('amount', tx.amount))
    if 'date' in data:
        tx.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    if 'category' in data:
        cat = db.session.query(Category).filter_by(name=data['category']).first()
        tx.category_id = cat.id if cat else tx.category_id

    # 2. Aktualizacja podziałów (splits)
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

@main_bp.route('/api/import/ing', methods=['POST'])
def import_ing_csv():
    """Odbiera plik CSV z ING, parsuje go i wrzuca do tabeli stagingowej."""
    if 'file' not in request.files:
        return jsonify({'error': 'Brak pliku w żądaniu.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku.'}), 400

    try:
        # Dekodowanie w UTF-8
        file_content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        # Pliki z polskich banków często są w kodowaniu Windows-1250
        file.seek(0)
        file_content = file.read().decode('windows-1250')

    # 1. Mockowanie przypisania (dopóki nie mamy uwierzytelniania w aplikacji)
    user = db.session.query(User).first()
    if not user:
        user = User(username="import_user", email="import@test.com", password_hash="secret")
        db.session.add(user)
        db.session.commit()

    account = db.session.query(Account).filter_by(user_id=user.id).first()
    if not account:
        account = Account(name="Konto do Importu", bank_name="ING", balance=0.0, user_id=user.id)
        db.session.add(account)
        db.session.commit()

    # 2. Parsowanie i zapis w tabeli buforowej
    parsed_data = parse_ing_csv(file_content)
    if not parsed_data:
        return jsonify({'error': 'Plik nie zawiera poprawnych transakcji lub jest uszkodzony.'}), 400
        
    saved_records = save_transactions_to_staging(parsed_data, user_id=user.id, account_id=account.id)

    return jsonify({
        'message': f'Udało się zaimportować {len(saved_records)} transakcji do weryfikacji.',
        'count': len(saved_records)
    }), 201