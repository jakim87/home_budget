from app import db
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash

def register_user(data):
    try:
        if db.session.query(User).filter_by(username=data['username']).first():
            raise ValueError("Użytkownik o tej nazwie już istnieje.")
        if db.session.query(User).filter_by(email=data['email']).first():
            raise ValueError("Konto z tym adresem email już istnieje.")
            
        hashed_pwd = generate_password_hash(data['password'])
        new_user = User(username=data['username'], email=data['email'], password_hash=hashed_pwd)
        
        db.session.add(new_user)
        db.session.commit()
        return new_user
    except Exception as e:
        db.session.rollback()
        raise ValueError(str(e))

def authenticate_user(username_or_email, password):
    user = db.session.query(User).filter(
        (User.username == username_or_email) | (User.email == username_or_email)
    ).first()
    if user and check_password_hash(user.password_hash, password):
        return user
    return None