import pytest
from aiopypay.app import get_app
from aiopypay.db import migrate, drop_tables, get_engine


@pytest.fixture
async def cli(aiohttp_client, tables):
    app = get_app([])
    return await aiohttp_client(app)


@pytest.fixture
async def tables():
    migrate(True)
    yield
    drop_tables(get_engine())


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


