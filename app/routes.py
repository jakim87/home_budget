from flask import Blueprint, render_template, jsonify, request
from app import db
from app.models import Transaction, Category, User, Account, TransactionArchive, TransactionSplit, TransactionStaging, Contractor
from datetime import datetime
from app.services.budget_service import parse_ing_csv, save_transactions_to_staging, create_transaction

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
    
    # Pobieranie kontrahentów
    user = db.session.query(User).first()
    contractors = db.session.query(Contractor).filter_by(user_id=user.id, is_active=True).all() if user else []
    cat_map = {c.id: c.name for c in categories}
    contractors_data = [{'id': c.id, 'name': c.name, 'rules': c.mapping_rules, 'default_category_id': c.default_category_id, 'default_category_name': cat_map.get(c.default_category_id, '')} for c in contractors]

    # 2. Pobieranie kont (Słownik kont)
    accounts = db.session.query(Account).filter_by(user_id=user.id, is_active=True).all() if user else []
    accounts_data = [{'id': a.id, 'name': a.name, 'bank_name': a.bank_name, 'account_number': a.account_number, 'balance': float(a.balance)} for a in accounts]

    # 3. Pobieranie transakcji i formatowanie ich dla frontendu
    if user:
        transactions_with_cat = db.session.query(Transaction, Category, Contractor).outerjoin(
            Category, Transaction.category_id == Category.id
        ).outerjoin(
            Contractor, Transaction.contractor_id == Contractor.id
        ).filter(Transaction.user_id == user.id).all()
    else:
        transactions_with_cat = []
        
    transactions_data = []
    for tx, cat, cont in transactions_with_cat:
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

    account_id = data.get('account_id')
    account = db.session.get(Account, account_id) if account_id else db.session.query(Account).first()
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

    contractor_id = data.get('contractor_id')
    if contractor_id:
        contractor_id = int(contractor_id)
    else:
        contractor_id = None

    # 3. Zapis do bazy za pomocą serwisu (który przy okazji zaktualizuje saldo konta)
    new_tx = create_transaction(
        user_id=user.id,
        account_id=account.id,
        amount=amount,
        title=title,
        transaction_date=tx_date,
        category_id=category.id if category else None,
        contractor_id=contractor_id
    )
    
    # Zwracamy pełny obiekt transakcji, aby frontend mógł go od razu wyświetlić
    return jsonify({
        'id': new_tx.id,
        'desc': new_tx.title,
        'amount': float(new_tx.amount),
        'date': new_tx.date.strftime('%Y-%m-%d'),
        'category': category.name if category else 'Inne',
        'contractor_id': new_tx.contractor_id,
        'contractor_name': db.session.get(Contractor, new_tx.contractor_id).name if new_tx.contractor_id else None,
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

@main_bp.route('/api/contractors', methods=['POST'])
def add_contractor():
    """Zapisuje nowego kontrahenta ze słownika do bazy."""
    data = request.get_json()
    user = db.session.query(User).first()
    if not user:
        return jsonify({'error': 'Brak użytkownika'}), 400
        
    cat_name = data.get('category')
    category = db.session.query(Category).filter_by(name=cat_name).first() if cat_name else None

    new_cont = Contractor(
        name=data.get('name'),
        mapping_rules=data.get('rules'),
        default_category_id=category.id if category else None,
        user_id=user.id
    )
    db.session.add(new_cont)
    db.session.commit()

    return jsonify({
        'id': new_cont.id,
        'name': new_cont.name,
        'rules': new_cont.mapping_rules,
        'default_category_id': new_cont.default_category_id,
        'default_category_name': category.name if category else ''
    }), 201

@main_bp.route('/api/accounts', methods=['POST'])
def add_account():
    """Zapisuje nowe konto ze słownika do bazy."""
    data = request.get_json()
    user = db.session.query(User).first()
    if not user:
        return jsonify({'error': 'Brak użytkownika'}), 400
        
    new_acc = Account(
        name=data.get('name'),
        bank_name=data.get('bank_name'),
        account_number=data.get('account_number'),
        balance=0.0,
        user_id=user.id
    )
    db.session.add(new_acc)
    db.session.commit()

    return jsonify({'id': new_acc.id, 'name': new_acc.name, 'bank_name': new_acc.bank_name, 'account_number': new_acc.account_number, 'balance': 0.0}), 201

@main_bp.route('/api/accounts/<int:a_id>', methods=['PUT'])
def update_account(a_id):
    """Aktualizuje dane istniejącego konta."""
    acc = db.session.get(Account, a_id)
    if not acc:
        return jsonify({'error': 'Nie znaleziono konta.'}), 404
        
    data = request.get_json()
    acc.name = data.get('name', acc.name)
    acc.bank_name = data.get('bank_name', acc.bank_name)
    acc.account_number = data.get('account_number', acc.account_number)
        
    db.session.commit()
    return jsonify({'id': acc.id, 'name': acc.name, 'bank_name': acc.bank_name, 'account_number': acc.account_number, 'balance': float(acc.balance)}), 200

@main_bp.route('/api/accounts/<int:a_id>', methods=['DELETE'])
def delete_account(a_id):
    """Wykonuje miękkie usunięcie (soft delete) konta."""
    acc = db.session.get(Account, a_id)
    if acc:
        acc.is_active = False
        db.session.commit()
    return jsonify({'message': 'Konto usunięte ze słownika.'}), 200

@main_bp.route('/api/contractors/<int:c_id>', methods=['PUT'])
def update_contractor(c_id):
    """Aktualizuje dane istniejącego kontrahenta."""
    cont = db.session.get(Contractor, c_id)
    if not cont:
        return jsonify({'error': 'Nie znaleziono kontrahenta.'}), 404
        
    data = request.get_json()
    cont.name = data.get('name', cont.name)
    cont.mapping_rules = data.get('rules', cont.mapping_rules)
    
    cat_name = data.get('category')
    if cat_name:
        category = db.session.query(Category).filter_by(name=cat_name).first()
        cont.default_category_id = category.id if category else None
    else:
        cont.default_category_id = None
        category = None
        
    db.session.commit()
    return jsonify({
        'id': cont.id,
        'name': cont.name,
        'rules': cont.mapping_rules,
        'default_category_id': cont.default_category_id,
        'default_category_name': category.name if category else ''
    }), 200

@main_bp.route('/api/contractors/<int:c_id>', methods=['DELETE'])
def delete_contractor(c_id):
    """Wykonuje miękkie usunięcie (soft delete) kontrahenta."""
    cont = db.session.get(Contractor, c_id)
    if cont:
        cont.is_active = False
        db.session.commit()
    return jsonify({'message': 'Kontrahent usunięty.'}), 200

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
    if 'contractor_id' in data:
        cid = data.get('contractor_id')
        tx.contractor_id = int(cid) if cid else None

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
        # Używamy utf-8-sig, które automatycznie usuwa niewidoczny znacznik BOM
        file_content = file.read().decode('utf-8-sig')
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

    account_id_str = request.form.get('account_id')
    account = db.session.get(Account, int(account_id_str)) if account_id_str and account_id_str.isdigit() else db.session.query(Account).filter_by(user_id=user.id).first()
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

@main_bp.route('/api/staging/pending', methods=['GET'])
def get_pending_staging_transactions():
    """Pobiera listę transakcji oczekujących na zatwierdzenie z tabeli stagingowej."""
    user = db.session.query(User).first()
    if not user:
        return jsonify([]), 200
        
    pending_txs = db.session.query(TransactionStaging, Category, Contractor).outerjoin(
        Category, TransactionStaging.proposed_category_id == Category.id
    ).outerjoin(
        Contractor, TransactionStaging.proposed_contractor_id == Contractor.id
    ).filter(
        TransactionStaging.user_id == user.id, 
        TransactionStaging.status == 'pending'
    ).order_by(TransactionStaging.date.desc()).all()
    
    data = []
    for tx, cat, cont in pending_txs:
        data.append({
            'id': tx.id,
            'date': tx.date.strftime('%Y-%m-%d'),
            'amount': float(tx.amount),
            'title': tx.title,
            'contractor': tx.contractor or '',
            'status': tx.status,
            'proposed_category': cat.name if cat else '',
            'proposed_contractor_id': tx.proposed_contractor_id,
            'proposed_contractor_name': cont.name if cont else ''
        })
        
    return jsonify(data), 200

@main_bp.route('/api/staging/pending', methods=['DELETE'])
def clear_pending_staging_transactions():
    """Usuwa (odrzuca) wszystkie oczekujące transakcje ze stagingu dla danego użytkownika."""
    user = db.session.query(User).first()
    if not user:
        return jsonify({'error': 'Brak użytkownika'}), 400
        
    deleted_count = db.session.query(TransactionStaging).filter_by(
        user_id=user.id, 
        status='pending'
    ).delete()
    
    db.session.commit()
    return jsonify({'message': f'Odrzucono {deleted_count} transakcji.'}), 200

@main_bp.route('/api/staging/<int:stg_id>/approve', methods=['POST'])
def approve_staging_transaction(stg_id):
    """Zatwierdza transakcję ze stagingu i przenosi ją do głównej tabeli, aktualizując saldo."""
    data = request.get_json() or {}
    stg_tx = db.session.get(TransactionStaging, stg_id)
    
    if not stg_tx or stg_tx.status != 'pending':
        return jsonify({'error': 'Nie znaleziono oczekującej transakcji.'}), 404
        
    category_name = data.get('category')
    category = db.session.query(Category).filter_by(name=category_name).first() if category_name else None
    contractor_id = data.get('contractor_id')
    
    if not category or not contractor_id:
        return jsonify({'error': 'Wybór kategorii i kontrahenta jest wymagany do zatwierdzenia transakcji.'}), 400

    try:
        # Użycie logiki biznesowej do stworzenia wpisu i aktualizacji konta
        new_tx = create_transaction(
            user_id=stg_tx.user_id,
            account_id=stg_tx.account_id,
            amount=float(stg_tx.amount),
            title=stg_tx.title,
            transaction_date=stg_tx.date,
            category_id=category.id if category else None,
            contractor=stg_tx.contractor,
            contractor_id=int(contractor_id) if contractor_id else None
        )
        # Usunięcie ze stagingu po poprawnym przeniesieniu do bazy transakcji
        db.session.delete(stg_tx)
        db.session.commit()
        return jsonify({'message': 'Transakcja zatwierdzona.', 'transaction_id': new_tx.id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400