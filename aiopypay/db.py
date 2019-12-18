import hashlib
import os
from sqlalchemy import MetaData, create_engine, inspect
import aiopg.sa
from . import models

dsn = "postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}".format(
    **os.environ
)


# ========== async

async def init_pg(app):
    engine = await aiopg.sa.create_engine(dsn)
    app['db'] = engine


async def close_pg(app):
    app['db'].close()
    await app['db'].wait_closed()


# ========== regular

def get_engine():
    return create_engine(dsn)


def create_tables(engine):
    meta = MetaData()
    meta.create_all(bind=engine, tables=[getattr(models, t) for t in models.__all__])


def drop_tables(engine):
    meta = MetaData()
    meta.drop_all(bind=engine, tables=[getattr(models, t) for t in models.__all__])


def init_data(engine):
    with engine.connect() as conn:
        # Create currencies
        conn.execute(models.currencies.insert(), [
            dict(id="USD", description="United States Dollar", comission=0.01),
            dict(id="CNY", description="Chinese Yuan", comission=0.02),
            dict(id="EUR", description="Euro", comission=0.03),
        ])

        # Create superuser, and it's accounts, where comisions will be tansfered
        superuser_id = conn.execute(models.users.insert(values=dict(
            username='superuser',
            password_hash=hashlib.md5(os.environ['APP_SUPERUSER_PASSWORD'].encode('utf-8')).hexdigest(),
            full_name='Superuser',
            is_superuser=True,
        ))).inserted_primary_key[0]

        conn.execute(models.accounts.insert(), [
            dict(user_id=superuser_id, currency_id="USD", amount=0),
            dict(user_id=superuser_id, currency_id="CNY", amount=0),
            dict(user_id=superuser_id, currency_id="EUR", amount=0),
        ])


def sample_data(engine):
    pass


def is_empty(engine):
    return not bool(inspect(engine).get_table_names())


def migrate(force_recreate):
    """ Performs simple migration scenario.
    Just creates tables for current models state, if database is empty.
    In real production migration management tools should be used,
    like alembic or migrate and migrations should be part of app deployment proccess.
    """

    engine = get_engine()

    if force_recreate or is_empty(engine):
        if force_recreate:
            print("Dropping tables...")
            drop_tables(engine)
        print("Initializing database...")
        create_tables(engine)
        init_data(engine)
        print('Done')
    else:
        print("Working with initialized database.")

    engine.dispose()
