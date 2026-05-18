from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Date, ForeignKey
from datetime import date
from typing import Optional
from app import db
from decimal import Decimal
from datetime import datetime, timezone
from flask_login import UserMixin

# NOWA TABELA: Shadow table dla usuwanych transakcji
class TransactionArchive(db.Model):
    __tablename__ = 'transaction_archive'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    original_id: Mapped[int] = mapped_column(nullable=False) # ID z oryginalnej tabeli
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    account_id: Mapped[int] = mapped_column(nullable=False)
    contractor_id: Mapped[Optional[int]] = mapped_column()
    category_id: Mapped[Optional[int]] = mapped_column()
    user_id: Mapped[int] = mapped_column(nullable=False)
    
    # Znacznik czasu operacji usunięcia
    deleted_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)

class User(db.Model, UserMixin):
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
    account_number: Mapped[Optional[str]] = mapped_column(String(50)) # Numer rachunku docelowego
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default='PLN')
    
    # Miękkie usuwanie ze słownika
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

class Category(db.Model):
    __tablename__ = 'categories'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20)) # np. "expense" (wydatek) lub "income" (przychód)
    # NOWE POLE: Miękkie usuwanie
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)

class Contractor(db.Model):
    __tablename__ = 'contractors'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False) # Znormalizowana nazwa, np. "Biedronka"
    mapping_rules: Mapped[Optional[str]] = mapped_column(String(500)) # np. "biedronka, jeronimo martins"
    
    default_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    # NOWE POLE: Miękkie usuwanie
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)

class TransactionSplit(db.Model):
    __tablename__ = 'transaction_splits'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    desc: Mapped[str] = mapped_column(String(255), nullable=True)
    
    transaction_id: Mapped[int] = mapped_column(ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    
    category = relationship('Category')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contractor: Mapped[Optional[str]] = mapped_column(String(255)) # Surowy tekst nadawcy z banku
    
    # Relacje
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'), nullable=False)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey('contractors.id')) # Powiązanie ze słownikiem
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

    # Znacznik czasu ostatniej modyfikacji
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=db.func.now())

    # Relacja do podziałów - selectin sprawi, że zapytanie będzie bardzo wydajne (brak problemu N+1)
    splits = relationship('TransactionSplit', backref='transaction', lazy='selectin', cascade='all, delete-orphan')

class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    month: Mapped[int] = mapped_column(nullable=False) # 1-12
    year: Mapped[int] = mapped_column(nullable=False)
    
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

class TransactionStaging(db.Model):
    """Tabela tymczasowa (staging) na dane z importu plików CSV przed ich zatwierdzeniem."""
    __tablename__ = 'transaction_staging'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contractor: Mapped[Optional[str]] = mapped_column(String(255)) # Surowy tekst z banku
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=db.func.now())
    
    # Kolumny proponowane przez algorytm analizy przy imporcie
    proposed_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    proposed_contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey('contractors.id'))
    
    status: Mapped[str] = mapped_column(String(20), default='pending') # np. 'pending', 'approved', 'rejected'
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey('accounts.id'))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id'))