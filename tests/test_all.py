import os

import pytest
from aiohttp import BasicAuth

from aiopypay.app import get_app
from aiopypay.db import migrate, drop_tables, get_engine


# ===========================================

@pytest.fixture
async def cli(aiohttp_client, tables):
    app = get_app([])
    return await aiohttp_client(app)


@pytest.fixture
async def tables():
    migrate(True)
    yield
    drop_tables(get_engine())


async def create_vasya(cli):
    return await cli.post(
        '/users',
        data=dict(username="vasya", password="pass", full_name="Vasya Pupkin")
    )


async def create_frosya(cli):
    return await cli.post(
        '/users',
        data=dict(username="frosya", password="pass", full_name="Frosya Taburetkina")
    )


# ===========================================

async def test_currencies(cli):
    response = await cli.get('/currencies')
    assert response.status == 200
    clist = await response.json()
    assert len(clist) == 3


async def test_bad_uri(cli):
    response = await cli.get('/currencies/111')
    assert response.status == 404


async def test_register_user(cli):
    response = await cli.post(
        '/users',
        data=dict(username="vasya", password="pass", full_name="Vasya Pupkin")
    )
    assert response.status == 201
    user = await response.json()
    assert user['username'] == 'vasya'


async def test_register_user_twice(cli):
    response = await cli.post(
        '/users',
        data=dict(username="vasya", password="pass", full_name="Vasya Pupkin")
    )
    assert response.status == 201

    response = await cli.post(
        '/users',
        data=dict(username="vasya", password="pass", full_name="Vasya Pupkin")
    )
    assert response.status == 409


async def test_register_user_unicode(cli):
    response = await cli.post(
        '/users',
        data=dict(username="vasya", password="pass", full_name="Вася Пупкин")
    )
    assert response.status == 201
    user = await response.json()
    assert user['full_name'] == "Вася Пупкин"


async def test_register_bad_user(cli):
    response = await cli.post(
        '/users',
        data=dict(password="pass", full_name="Вася Пупкин")
    )
    assert response.status == 400


# -------------------------------------------

async def test_accounts_created(cli):
    await create_vasya(cli)
    response = await cli.get('/users/2/accounts', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 200
    accounts = await response.json()
    assert len(accounts) == 3
    assert accounts[0]['currency_id'] == 'USD'
    assert accounts[0]['amount'] == 100

    response = await cli.get('/accounts/4', auth=BasicAuth('vasya', 'pass'))
    account = await response.json()
    assert account['currency_id'] == 'USD'
    assert account['amount'] == 100


async def test_unauthorized_access(cli):
    await create_vasya(cli)
    await create_frosya(cli)
    response = await cli.get('/users/2/accounts')
    assert response.status == 401
    response = await cli.get('/users/3/accounts', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 403
    response = await cli.get('/users/3/accounts', auth=BasicAuth('vasya', 'pass111'))
    assert response.status == 401
    response = await cli.get('/accounts/7', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 403
    response = await cli.get('/accounts/100', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 404


async def test_create_account(cli):
    await create_vasya(cli)
    response = await cli.post('/users/2/accounts/USD', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 200
    account = await response.json()
    assert account['currency_id'] == 'USD'


async def test_create_account_bad_currency(cli):
    await create_vasya(cli)
    response = await cli.post('/users/2/accounts/YUP', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 400
    response = await cli.post('/users/2/accounts/AAAAAAA', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 404


# -------------------------------------------

async def test_transfer_with_comission(cli):
    await create_vasya(cli)
    await create_frosya(cli)

    response = await cli.post(
        '/users/2/transfers',
        auth=BasicAuth('vasya', 'pass'),
        data={'from': 4, 'to': 7, 'amount': 10}
    )
    assert response.status == 200
    transfers = (await response.json())['transfers']
    assert len(transfers) == 2

    response = await cli.get('/users/2/transfers', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 200
    transfers = await response.json()
    assert len(transfers) == 2
    assert transfers[0]['comment'] == 'External payment'
    assert transfers[1]['comment'] == 'Commission'

    response = await cli.get('/accounts/4', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 200
    account = await response.json()
    assert account['amount'] == 89.9

    response = await cli.get('/accounts/7', auth=BasicAuth('frosya', 'pass'))
    assert response.status == 200
    account = await response.json()
    assert account['amount'] == 110

    response = await cli.get('/accounts/1', auth=BasicAuth('superuser', os.environ['APP_SUPERUSER_PASSWORD']))
    assert response.status == 200
    account = await response.json()
    assert account['amount'] == 0.1


async def test_transfer_without_comission(cli):
    await create_vasya(cli)

    response = await cli.post('/users/2/accounts/USD', auth=BasicAuth('vasya', 'pass'))
    assert response.status == 200

    response = await cli.post(
        '/users/2/transfers', auth=BasicAuth('vasya', 'pass'),
        data={'from': 4, 'to': 7, 'amount': 10}
    )
    assert response.status == 200

    transfers = (await response.json())['transfers']
    assert len(transfers) == 1

    response = await cli.get('/users/2/transfers', auth=BasicAuth('vasya', 'pass'))
    transfers = await response.json()
    assert len(transfers) == 1
    assert transfers[0]['comment'] == 'Internal transfer'

    response = await cli.get('/accounts/4', auth=BasicAuth('vasya', 'pass'))
    account = await response.json()
    assert account['amount'] == 90

    response = await cli.get('/accounts/7', auth=BasicAuth('vasya', 'pass'))
    account = await response.json()
    assert account['amount'] == 10
