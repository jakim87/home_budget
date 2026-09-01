from sqlalchemy.orm import Mapped, mapped_column, relationship, Session
from sqlalchemy import String, Text, Numeric, Date, ForeignKey, Enum as SQLAlchemyEnum, event, CheckConstraint
from datetime import date
from typing import Optional, List
from app import db
from decimal import Decimal
from datetime import datetime, timezone
from flask_login import UserMixin
import enum
import uuid

class Frequency(enum.Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'

class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transactions'
    __table_args__ = (
        # interval=0 zapetla process_recurring_transactions (next_run_date sie nie
        # posuwa) — patrz bezpiecznik w recurring_service.process_recurring_transactions.
        # Niezmiennik wymuszony w bazie, nie tylko w schemacie Marshmallow.
        CheckConstraint('interval >= 1', name='ck_recurring_transactions_interval_positive'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'), nullable=True)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey('contractors.id'), nullable=True)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    frequency: Mapped[Frequency] = mapped_column(SQLAlchemyEnum(Frequency), nullable=False)
    interval: Mapped[int] = mapped_column(default=1, nullable=False) # Np. co 2 tygodnie (interval=2, frequency=WEEKLY)
    day_of_week: Mapped[Optional[int]] = mapped_column(nullable=True) # 0=Poniedziałek, 6=Niedziela (dla WEEKLY)
    day_of_month: Mapped[Optional[int]] = mapped_column(nullable=True) # 1-31 (dla MONTHLY)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="recurring_transactions", foreign_keys=[user_token])
    account: Mapped["Account"] = relationship()
    category: Mapped["Category"] = relationship()
    contractor: Mapped["Contractor"] = relationship()

class PlannedTransaction(db.Model):
    __tablename__ = 'planned_transactions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'), nullable=True)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey('contractors.id'), nullable=True)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    execution_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False) # pending, processed
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="planned_transactions", foreign_keys=[user_token])
    account: Mapped["Account"] = relationship()
    category: Mapped["Category"] = relationship()
    contractor: Mapped["Contractor"] = relationship()

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
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False)

    # Pełny ślad audytowy usuniętej transakcji (wcześniej ginęły przy usuwaniu).
    comment: Mapped[Optional[str]] = mapped_column(String(255))
    contractor_raw: Mapped[Optional[str]] = mapped_column(String(255))  # surowy tekst kontrahenta z banku
    splits_json: Mapped[Optional[str]] = mapped_column(Text)  # zserializowane podziały (JSON jako tekst — zgodne z SQLite)

    # Znacznik czasu operacji usunięcia
    deleted_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    token: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))

    # Relacja zwrotna do kont
    accounts: Mapped[list['Account']] = relationship(back_populates="user")
    # Relacja do transakcji cyklicznych
    recurring_transactions: Mapped[List["RecurringTransaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # Relacja do transakcji zaplanowanych
    planned_transactions: Mapped[List["PlannedTransaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")

# Dozwolone typy konta. None = konto bez przypisanego typu (np. gotówka/portfel,
# konto techniczne). ROR/KO/Rach. Maklerski/IKZE mogą mieć dowolne saldo; Kredyt
# musi mieć saldo <= 0 (zobowiązanie) — patrz ACCOUNT_TYPE_KREDYT i walidacja w budget_service.
ACCOUNT_TYPES = ('ROR', 'KO', 'Kredyt', 'Rach. Maklerski', 'IKZE')
ACCOUNT_TYPE_KREDYT = 'Kredyt'


class Account(db.Model):
    __tablename__ = 'accounts'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False) # np. "ING Konto Direct", "Portfel"
    bank_name: Mapped[str] = mapped_column(String(50)) # np. "ING", "Manual"
    account_number: Mapped[Optional[str]] = mapped_column(String(50)) # Numer rachunku docelowego
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))
    currency: Mapped[str] = mapped_column(String(3), default='PLN')
    # Typ konta (jeden z ACCOUNT_TYPES) lub None. Steruje walidacją salda (Kredyt <= 0)
    # i prezentacją; nie wpływa na dopasowanie kont przy imporcie (to idzie po NRB).
    account_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    co_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Miękkie usuwanie ze słownika
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, server_default='false', nullable=False)
    # Kolejność wyświetlania w UI (ustawiana ręcznie przez użytkownika) — nie ma wpływu na logikę aplikacji.
    sort_order: Mapped[int] = mapped_column(default=0, server_default='0', nullable=False)
    # Data dodania konta do słownika — istotna dla raportowania i rozstrzygania kolejności
    # (np. przy duplikatach nazw). Dla kont istniejących przed migracją ustawiona na czas
    # migracji (brak historycznej daty utworzenia).
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), server_default=db.func.now(), nullable=False
    )
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False)

    # Relacja do użytkownika
    user: Mapped['User'] = relationship(back_populates="accounts", foreign_keys=[user_token])

class Category(db.Model):
    __tablename__ = 'categories'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50)) # np. "expense", "income", "transfer", "system_reconciliation"
    # NOWE POLE: Miękkie usuwanie
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)
    is_system_category: Mapped[bool] = mapped_column(default=False, server_default='false', nullable=False)
    # Właściciel kategorii. NULL = kategoria globalna (systemowa, wspólna dla wszystkich):
    # widoczna dla każdego, ale nieusuwalna przez użytkownika. Wcześniej WSZYSTKIE
    # kategorie były globalne, więc dowolny użytkownik mógł dezaktywować cudzą.
    user_token: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey('users.token'), nullable=True, index=True
    )

class Contractor(db.Model):
    __tablename__ = 'contractors'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False) # Znormalizowana nazwa, np. "Biedronka"
    mapping_rules: Mapped[Optional[str]] = mapped_column(String(500)) # np. "biedronka, jeronimo martins"
    
    default_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categories.id'))
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False)
    # NOWE POLE: Miękkie usuwanie
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true', nullable=False)
    # Dla kontrahentów typu "Moje konto: {nazwa}" — twarde powiązanie z kontem docelowym.
    # Dzięki temu przelewy wewnętrzne są odporne na zmianę nazwy konta i duplikaty nazw.
    linked_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey('accounts.id'), nullable=True)

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
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Powiązanie dwóch stron przelewu wewnętrznego (samoodwołanie).
    # Zastępuje kruchą heurystykę dopasowania po (konto, kwota, data).
    linked_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True
    )
    # Ślad pochodzenia — z jakiej definicji harmonogramu powstała transakcja.
    # Umożliwia idempotentne przetwarzanie (brak podwójnego wykonania).
    source_recurring_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('recurring_transactions.id', ondelete='SET NULL'), nullable=True
    )
    source_planned_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('planned_transactions.id', ondelete='SET NULL'), nullable=True
    )
    # Pochodzenie transakcji: 'manual' | 'import' | 'recurring' | 'planned' | 'mirror'
    # | 'reconcile' | 'excel' | 'unknown' (dane sprzed wprowadzenia kolumny).
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default='manual', server_default='manual')

    # Właściwości relacyjne (wymagane m.in. dla eager loadingu w zapytaniach)
    account: Mapped['Account'] = relationship()
    contractor_details: Mapped[Optional['Contractor']] = relationship("Contractor", foreign_keys=[contractor_id])
    category: Mapped[Optional['Category']] = relationship()
    user: Mapped['User'] = relationship(foreign_keys=[user_token])

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
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False)

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
    user_token: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey('users.token'))
    suggested_contractor_name: Mapped[Optional[str]] = mapped_column(String(255))
    # Numer rachunku kontrahenta z wyciągu (surowy, nieznormalizowany) — potrzebny,
    # by reanalyze_all_staging mogło ponownie rozpoznać przelew wewnętrzny po IBAN,
    # nie tylko przy pierwszym imporcie (patrz analyze_transaction_data, krok 1).
    counterparty_account: Mapped[Optional[str]] = mapped_column(String(50))


class Feedback(db.Model):
    """Uwaga od użytkownika o działaniu aplikacji.

    Zgłoszenie NIE jest danymi finansowymi użytkownika i celowo nie znika przy
    „Wyczyść dane testowe" ani przy odtwarzaniu konta demo — to korespondencja
    z autorem aplikacji, nie zawartość czyjegoś budżetu.

    Treść pisze człowiek i czyta ją administrator w przeglądarce, więc przy
    wyświetlaniu MUSI przejść przez escapowanie (patrz szablon zgloszenia.html).
    """
    __tablename__ = 'feedback'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Kontekst zbierany automatycznie, żeby nie wypytywać zgłaszającego „a gdzie
    # to było": nazwa otwartej zakładki i wersja aplikacji z chwili wysłania.
    context: Mapped[Optional[str]] = mapped_column(String(120))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), server_default=db.func.now(), index=True
    )

    user: Mapped['User'] = relationship(foreign_keys=[user_token])


class StatementImport(db.Model):
    """Ewidencja wgranych wyciągów — jeden wiersz na parę (plik, pokryte konto).

    Pełni dwie role:
    1. audyt — co, kiedy i za jaki okres zostało zaimportowane,
    2. sygnał pokrycia — czy dane konto w ogóle dostaje własne wyciągi. To drugie
       jest fundamentem modelu transferów: dla konta z własnymi wyciągami druga
       noga przelewu przyjdzie realnie, więc lustra generować NIE wolno.

    Plik wielokontowy (ING) tworzy N wierszy o wspólnym batch_id — dzięki temu
    pokrycie da się odpytać zwykłym filtrem po account_id, bez kolumn JSON
    (których SQLite w testach nie obsługuje).
    """
    __tablename__ = 'statement_imports'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_token: Mapped[str] = mapped_column(String(36), ForeignKey('users.token'), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    bank: Mapped[str] = mapped_column(String(30), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)

    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey('accounts.id'), index=True)

    # Zakres wyznaczany z min/max daty zaimportowanych transakcji (nie z deklaracji
    # w nagłówku) — zawsze dostępny i odzwierciedla to, co faktycznie weszło.
    period_start: Mapped[Optional[date]] = mapped_column(Date)
    period_end: Mapped[Optional[date]] = mapped_column(Date)

    transaction_count: Mapped[int] = mapped_column(default=0)
    skipped_count: Mapped[int] = mapped_column(default=0)
    imported_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), server_default=db.func.now())

    account = relationship("Account")


@event.listens_for(Session, 'before_flush')
def _enforce_account_type_invariants(session, flush_context, instances):
    """Twardy niezmiennik typu konta: Kredyt (zobowiązanie) nie może mieć salda > 0.

    Egzekwowane centralnie przy KAŻDYM flushu, więc łapie wszystkie ścieżki zmiany
    salda (dodanie/edycja/usunięcie transakcji, lustro przelewu wewnętrznego,
    uzgodnienie salda, migracja historii) bez instrumentowania każdej z osobna.
    Dodatnie saldo na koncie Kredyt oznacza błąd danych — świadomie przerywamy flush.
    Saldo == 0 jest dozwolone (moment spłaty — patrz flow spłaty w budget_service).
    """
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, Account) and obj.account_type == ACCOUNT_TYPE_KREDYT:
            if obj.balance is not None and Decimal(str(obj.balance)) > 0:
                raise ValueError(
                    f"Konto '{obj.name}' jest typu Kredyt i nie może mieć dodatniego "
                    f"salda (próba ustawienia {obj.balance}). Kredyt to zobowiązanie — saldo musi być <= 0."
                )