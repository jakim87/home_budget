from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Date, ForeignKey
from datetime import date
from typing import Optional
from app import db
from datetime import datetime, timezone

# NOWA TABELA: Shadow table dla usuwanych transakcji
class TransactionArchive(db.Model):
    __tablename__ = 'transaction_archive'
    
    id = db.Column(db.Integer, primary_key=True)
    original_id = db.Column(db.Integer, nullable=False) # ID z oryginalnej tabeli
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    account_id = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, nullable=False)
    
    # Znacznik czasu operacji usunięcia
    deleted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)

class Account(db.Model):
    __tablename__ = 'accounts'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False) # np. "ING Konto Direct", "Portfel"
    bank_name: Mapped[str] = mapped_column(String(50)) # np. "ING", "Manual"
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default='PLN')
    
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

class Category(db.Model):
    __tablename__ = 'categories'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20)) # np. "expense" (wydatek) lub "income" (przychód)
    # NOWE POLE: Miękkie usuwanie
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)

class TransactionSplit(db.Model):
    __tablename__ = 'transaction_splits'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    desc: Mapped[str] = mapped_column(String(255), nullable=True)
    
    transaction_id: Mapped[int] = mapped_column(ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    
    category = relationship('Category')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contractor: Mapped[Optional[str]] = mapped_column(String(255)) # nadawca/odbiorca
    
    # Relacje
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

    # Relacja do podziałów - selectin sprawi, że zapytanie będzie bardzo wydajne (brak problemu N+1)
    splits = relationship('TransactionSplit', backref='transaction', lazy='selectin', cascade='all, delete-orphan')

class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    month: Mapped[int] = mapped_column(nullable=False) # 1-12
    year: Mapped[int] = mapped_column(nullable=False)
    
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'), nullable=False)