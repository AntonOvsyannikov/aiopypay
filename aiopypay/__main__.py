import argparse
import logging
import os, sys
from aiohttp import web
from .app import get_app
from .db import migrate

logging.basicConfig(level=logging.DEBUG if os.environ.get('APP_DEBUG', False) else logging.INFO)

# print(os.environ)

parser = argparse.ArgumentParser(description='Simple payment platform application.')
parser.add_argument('-f', '--force-recreate', action='store_true', help='force recreate tables in DB')
args, unknownargs = parser.parse_known_args()

migrate(args.force_recreate)

web.run_app(
    get_app(unknownargs),
    host=os.environ.get('APP_HOST', '0.0.0.0'),
    port=int(os.environ.get('APP_PORT', 8080)),
)
