from datetime import datetime
from sqlalchemy import MetaData, Table, Column, ForeignKey, Integer, String, DateTime, Float, Boolean

meta = MetaData()

__all__ = ['currencies', 'users', 'accounts', 'transfers']

currencies = Table(
    'currencies', meta,

    Column('id', String(3), primary_key=True),
    Column('description', String, nullable=False),

    # Commission, taken for transfer from such type of accounts
    # We assume fixed commission on transfer amount and no currency exchange are allowed
    Column('comission', Float, nullable=False),
)

users = Table(
    'users', meta,

    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('username', String, nullable=False),
    Column('password_hash', String, nullable=False),
    Column('first_name', String, nullable=False),
    Column('last_name', String, nullable=False),
    Column('is_superuser', Boolean, nullable=False, default=False),
)

accounts = Table(
    'accounts', meta,

    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
    Column('currency_id', String(3), ForeignKey('currencies.id', ondelete='RESTRICT'), nullable=False),
    Column('amount', Float(), nullable=False),
)

transfers = Table(
    'transfers', meta,

    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('timestamp', DateTime, default=datetime.utcnow, nullable=False),
    Column('from_account_id', Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
    Column('to_account_id', Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
    Column('from_amount', Float(), nullable=False),
    Column('to_amount', Float(), nullable=False),
)
