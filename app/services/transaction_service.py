from app import db
from app.models import Transaction, TransactionArchive, Category, TransactionSplit
from datetime import datetime

def archive_and_delete_transaction(user_id, tx_id):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_id=user_id).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje lub brak uprawnień.')
            
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
        db.session.delete(tx)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def update_transaction(user_id, tx_id, data):
    try:
        tx = db.session.query(Transaction).filter_by(id=tx_id, user_id=user_id).first()
        if not tx:
            raise ValueError('Transakcja nie istnieje.')

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

        if 'splits' in data:
            tx.splits.clear()
            for split_data in data['splits']:
                cat = db.session.query(Category).filter_by(name=split_data.get('category')).first()
                tx.splits.append(TransactionSplit(
                    amount=float(split_data.get('amount', 0)),
                    desc=split_data.get('desc', ''),
                    category_id=cat.id if cat else None
                ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))