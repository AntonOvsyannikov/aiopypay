# aiopypay
Simple payment system prototype, REST backend done with aiohttp, tested with pytest and deployed with docker-compose.

PostgreSQL is used as database. All money sensitive operations are performed in transactions. Aiohttp is chosen as gold standard for fast asynchronous API. There are other choices, like FastAPI. Aiopg.sa is used for async database access.


## Installation and running

```
git clone https://github.com/AntonOvsyannikov/aiopypay.git
cd aiopypay
docker-compose up --build
# or ./run.sh prod
# or ./run.sh test to run tests (exit with Ctrl-C)
```

## API documentation
There is short documentation for REST API. In real project it is better to document API 
with some of Swagger tool like aiohttp-swagger.

API in using Basic Auth. In real project API should be secured with https, in example with nginx reverse proxy.

```
@routes.get('/currencies')
Returns list of currencies n the system.
```

```
@routes.post('/users')
@form_data('username', 'password', 'full_name')
Register user, returns regitered user.
```

```
@routes.get(r'/users/{user_id:\d+}/accounts')
@auth_required('user_id')
Returns users's accounts list.
```

```
@routes.get(r'/accounts/{account_id:\d+}')
@auth_required()
Returns account status by account id. Owner of account should be authorized.
```

```
@routes.post(r'/users/{user_id:\d+}/accounts/{currency_id:[A-Z]{3}}')
@auth_required('user_id')
Creates new account with given currency.
```

```
@routes.post(r'/users/{user_id:\d+}/transfers')
@form_data('from', 'to', 'amount')
@auth_required('user_id')
Makes transfer from account id "from" to account id "to". 
Owner of "from" account should be authorized.
If accounts belongs to same user there is no commission.
If accounts belongs to different users, there is commission, configured
for each currency. Commission is charged additionally to transfer amount
and transferred to special account (depends on currency) of superuser,
which id is 1.
Currency conversion not supported. 
```

```
@routes.get(r'/users/{user_id:\d+}/transfers')
@query_string('from', 'to', 'sort')
@auth_required('user_id')
Lists all transfers from and to given user. User should be authorized. 
Additional filetering is available by given "from" and "to" user ids. 
Also list can be sorted ascending or descending with "sort=[asc|dsc]"
```