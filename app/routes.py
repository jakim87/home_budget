from flask import Blueprint, render_template, jsonify, request
from app import db
# from app.models import Transaction, Category # Do odkomentowania po dodaniu modeli

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
    Zastępuje to statyczne tablice z pliku JS. Z czasem należy to zamienić na zapytania do DB.
    """
    mock_categories = [
        {'name': 'Jedzenie', 'type': 'expense'},
        {'name': 'Transport', 'type': 'expense'},
        {'name': 'Rozrywka', 'type': 'expense'},
        {'name': 'Rachunki', 'type': 'expense'},
        {'name': 'Wynagrodzenie', 'type': 'income'},
        {'name': 'Inne', 'type': 'expense'}
    ]
    
    mock_transactions = [
        # Przykład, docelowo transakcje pobierane z DB
    ]
    
    return jsonify({
        'transactions': mock_transactions,
        'categories': mock_categories
    })

@main_bp.route('/api/transactions', methods=['POST'])
def add_transaction():
    """Zapisuje nową transakcję wysłaną przez formularz frontendu."""
    data = request.get_json()
    
    # TODO: Tu wpisz tworzenie obiektu bazy danych
    # new_tx = Transaction(desc=data['desc'], amount=data['amount'], ...)
    # db.session.add(new_tx); db.session.commit()
    
    return jsonify(data), 201