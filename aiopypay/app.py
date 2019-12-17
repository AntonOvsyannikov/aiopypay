from aiohttp import web
from .handlers import routes
from .db import init_pg, close_pg


# noinspection PyUnusedLocal
def get_app(argv):
    app = web.Application()
    app.on_startup.append(init_pg)
    app.on_cleanup.append(close_pg)
    app.add_routes(routes)
    return app
