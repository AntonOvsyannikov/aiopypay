import hashlib
# noinspection PyUnresolvedReferences
import json
import logging
import math

import psycopg2
from aiohttp import web
from sqlalchemy import and_, select

from .models import *

routes = web.RouteTableDef()


def log(*args, **kwargs):
    logging.getLogger('aiohttp.server').debug(*args, **kwargs)


# ===========================================
# DB helpers

async def get_one(conn, clause):
    cursor = await conn.execute(clause)
    result = await cursor.fetchone()
    if result is not None:
        result = dict(result)
    return result


async def get_many(conn, clause):
    cursor = await conn.execute(clause)
    records = await cursor.fetchall()
    return list(map(dict, records))


# ===========================================
# Handlers itself

# --------- Currencies

@routes.get('/currencies')
async def get_currencies(request):
    async with request.app['db'].acquire() as conn:
        result = await get_many(conn, currencies.select())
    return web.json_response(result)


# --------- Users

@routes.post('/users')
async def register_user(request):
    form = await request.post()

    user = {}
    try:
        user['username'] = form['username']
        user['password_hash'] = hashlib.md5(form['password'].encode('utf-8')).hexdigest()
        user['full_name'] = form.get('full_name', 'Unknown')
    except KeyError:
        raise web.HTTPBadRequest

    async with request.app['db'].acquire() as conn:
        async with conn.begin():
            if await get_one(conn, users.select().where(users.c.username == user['username'])):
                raise web.HTTPConflict

            user_id = (await get_one(conn, users.insert(values=user)))['id']

            # logging.getLogger('aiohttp.server').debug('{}'.format(result.id))

            # create default accounts
            await conn.execute(accounts.insert(values=dict(user_id=user_id, currency_id='USD', amount=100)))
            await conn.execute(accounts.insert(values=dict(user_id=user_id, currency_id='CNY', amount=0)))
            await conn.execute(accounts.insert(values=dict(user_id=user_id, currency_id='EUR', amount=0)))

        user = await get_one(
            conn,
            users.select().where(users.c.id == user_id)
        )
        del user['password_hash']
        del user['is_superuser']

    return web.json_response(user, status=201)


# --------- Accounts

@routes.get(r'/users/{id:\d+}/accounts')
async def get_accounts(request):
    async with request.app['db'].acquire() as conn:
        result = await get_many(
            conn,
            accounts.select().where(accounts.c.user_id == request.match_info['id'])
        )

    return web.json_response(result)


@routes.post(r'/users/{user_id:\d+}/accounts/{currency_id:[A-Z]{3}}')
async def create_account(request):
    user_id = request.match_info['user_id']
    currency_id = request.match_info['currency_id']

    # noinspection PyUnresolvedReferences
    try:
        async with request.app['db'].acquire() as conn:
            account_id = (await get_one(
                conn,
                accounts.insert(values=dict(
                    user_id=user_id,
                    currency_id=currency_id,
                    amount=0
                ))
            ))['id']
    except psycopg2.errors.ForeignKeyViolation:
        return web.json_response({'error': "Bad request"}, status=400)

    return web.json_response(await get_one(
        conn,
        accounts.select().where(accounts.c.id == account_id)
    ))


# --------- Transfers

@routes.post('/transfers')
async def make_transfer(request):
    form = await request.post()

    try:
        from_account_id = form['from']
        to_account_id = form['to']
        amount = float(form['amount'])
    except KeyError:
        raise web.HTTPBadRequest

    # noinspection PyShadowingNames
    async def transfer(conn, from_account_id, to_account_id, amount, comment):
        """ Executes transfer and log it"""

        await conn.execute(
            accounts
                .update(accounts.c.id == from_account_id)
                .values(amount=accounts.c.amount - amount)
        )

        await conn.execute(
            accounts
                .update(accounts.c.id == to_account_id)
                .values(amount=accounts.c.amount + amount)
        )

        return await get_one(
            conn,
            transfers
                .insert()
                .values(from_account_id=from_account_id, to_account_id=to_account_id,
                        amount=amount, comment=comment)
        )

    async with request.app['db'].acquire() as conn:
        async with conn.begin():  # Enter transaction
            from_acc = await get_one(conn, accounts.select().where(accounts.c.id == from_account_id))
            to_acc = await get_one(conn, accounts.select().where(accounts.c.id == to_account_id))

            if from_acc is None or to_acc is None:
                return web.json_response({'error': "Bad account id"}, status=400)

            if from_acc['currency_id'] != to_acc['currency_id']:
                return web.json_response({'error': "Currency conversion is not allowed"}, status=400)

            superuser_account_id = (await get_one(conn, select([users, accounts], use_labels=True).where(
                and_(
                    users.c.is_superuser == True,
                    accounts.c.currency_id == from_acc['currency_id']
                )
            )))['users_id']

            if from_acc['user_id'] != to_acc['user_id']:
                # Calculate comission
                currency = await get_one(conn, currencies.select().where(currencies.c.id == from_acc['currency_id']))
                comission_tax = currency['comission']
                # logging.getLogger('aiohttp.server').debug('{} {}'.format(amount, comission_tax))
                comission = math.ceil(amount * comission_tax * 100) / 100
            else:
                comission = 0

            if from_acc['amount'] < amount + comission:
                return web.json_response({'error': "No enough money on account {}".format(from_account_id)}, status=400)

            result = []

            result.append(
                await transfer(
                    conn, from_account_id, to_account_id, amount,

                    "External payment"
                    if from_acc['user_id'] != to_acc['user_id'] else
                    "Internal transfer"
                )
            )

            if comission:
                result.append(
                    await transfer(
                        conn, from_account_id, superuser_account_id, comission,
                        "Commission"
                    )
                )

    return web.json_response({"transfers": result})

# @routes.get('/accounts')
#     if 'user_id' in request.query:
#         clause = clause
#
#     if 'currency_id' in request.query:
#         clause = clause.where(accounts.c.currency_id == request.query['currency_id'])


@routes.get('/transfers')
async def get_transfers(request):
    clause = transfers.select()

    async with request.app['db'].acquire() as conn:
        result = await get_many(conn, clause)

    return web.json_response(result, dumps=lambda o: json.dumps(o, default=str))
