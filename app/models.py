from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, Date, ForeignKey
from datetime import date
from typing import Optional
from app import db

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

class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    month: Mapped[int] = mapped_column(nullable=False) # 1-12
    year: Mapped[int] = mapped_column(nullable=False)
    
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'), nullable=False)