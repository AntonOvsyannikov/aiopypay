import base64
import hashlib
# noinspection PyUnresolvedReferences
import json
import logging
import math
import re
from functools import wraps

import psycopg2
from aiohttp import web, BasicAuth
from sqlalchemy import and_, select, or_, desc, asc

from .models import *


# ===========================================


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
# Basic Auth

@web.middleware
async def auth_middleware(request, handler):
    auth = request.headers.get('Authorization', None)
    if auth:
        try:
            basic_auth = BasicAuth.decode(auth, 'utf-8')
        except ValueError:
            raise web.HTTPBadRequest

        async with request.app['db'].acquire() as conn:
            user = await get_one(
                conn,
                users.select().where(users.c.username == basic_auth.login)
            )

            if user is not None and user['password_hash'] == hashlib.md5(
                    basic_auth.password.encode('utf-8')).hexdigest():
                request['authorized_user'] = user

    return await handler(request)


def auth_required(matched_userid=None):
    def wrapper(handler):
        @wraps(handler)
        async def wraped(request):
            if 'authorized_user' not in request:
                raise web.HTTPUnauthorized

            if matched_userid is not None:
                if request['authorized_user']['id'] != int(request.match_info[matched_userid]):
                    raise web.HTTPForbidden

            return await handler(request)

        return wraped

    return wrapper


# ===========================================
# Handlers itself

routes = web.RouteTableDef()


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
        return web.json_response({'error': "Incorrect parameters"}, status=400)

    if not re.match(r'^[a-zA-Z_\d@]+$', user['username']):
        return web.json_response({'error': "Bad username"}, status=400)

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
@auth_required('id')
async def get_accounts(request):
    async with request.app['db'].acquire() as conn:
        result = await get_many(
            conn,
            accounts.select().where(accounts.c.user_id == request.match_info['id'])
        )

    return web.json_response(result)


@routes.get(r'/accounts/{id:\d+}')
@auth_required()
async def get_accounts(request):
    user = request['authorized_user']
    async with request.app['db'].acquire() as conn:
        account = await get_one(
            conn,
            accounts.select().where(accounts.c.id == request.match_info['id'])
        )
        if account is None:
            raise web.HTTPNotFound

        if account['user_id'] != user['id']:
            raise web.HTTPForbidden

    return web.json_response(account)


@routes.post(r'/users/{user_id:\d+}/accounts/{currency_id:[A-Z]{3}}')
@auth_required('user_id')
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

@routes.post(r'/users/{user_id:\d+}/transfers')
@auth_required('user_id')
async def make_transfer(request):
    form = await request.post()
    user_id = request['authorized_user']['id']

    try:
        from_account_id = form['from']
        to_account_id = form['to']
        amount = float(form['amount'])
    except KeyError:
        return web.json_response({'error': "Missing transfer details"}, status=400)

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

    log('here')
    async with request.app['db'].acquire() as conn:
        async with conn.begin():  # Enter transaction
            from_acc = await get_one(conn, accounts.select().where(accounts.c.id == from_account_id))
            to_acc = await get_one(conn, accounts.select().where(accounts.c.id == to_account_id))

            if from_acc is None or to_acc is None:
                return web.json_response({'error': "Bad account id"}, status=400)

            if from_acc['user_id'] != user_id:
                raise web.HTTPForbidden

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

            log('here')

    return web.json_response({"transfers": result})


@routes.get(r'/users/{user_id:\d+}/transfers')
@auth_required('user_id')
async def get_transfers(request):
    user = request['authorized_user']

    # filtering
    from_user_id = request.query.get('from', None)
    to_user_id = request.query.get('to', None)

    # sorting
    sort = request.query.get('sort', None)
    if not sort in [None, 'asc', 'dsc']:
        return web.json_response({'error': "Bad sort param, use sort=[asc|dsc]"}, status=400)

    async with request.app['db'].acquire() as conn:
        user_accounts = [d['id'] for d in await get_many(
            conn,
            select([accounts.c.id]).where(accounts.c.user_id == user['id'])
        )]

        # Basic clause, we show only transfers to or from authorized user
        clause = transfers.select().where(or_(
            transfers.c.from_account_id.in_(user_accounts),
            transfers.c.to_account_id.in_(user_accounts),
        ))

        # Additional filtering by from/to user id
        if from_user_id:
            from_user_accounts = [d['id'] for d in await get_many(
                conn,
                select([accounts.c.id]).where(accounts.c.user_id == from_user_id)
            )]
            clause = clause.where(transfers.c.from_account_id.in_(from_user_accounts))

        if to_user_id:
            to_user_accounts = [d['id'] for d in await get_many(
                conn,
                select([accounts.c.id]).where(accounts.c.user_id == to_user_id)
            )]
            clause = clause.where(transfers.c.to_account_id.in_(to_user_accounts))

        # Sort it
        if sort:
            clause = clause.order_by((asc if sort == 'asc' else desc)(transfers.c.id))

        result = await get_many(conn, clause)

    return web.json_response(result, dumps=lambda o: json.dumps(o, default=str))

