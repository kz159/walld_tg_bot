import logging
from os import getenv

TG_TOKEN = getenv('TG_TOKEN')

RMQ_HOST = getenv('RMQ_HOST', 'localhost')
RMQ_PORT = getenv('RMQ_PORT', '5672')
RMQ_USER = getenv('RMQ_USER', 'guest')
RMQ_PASS = getenv('RMQ_PASS', 'guest')

DB_HOST = getenv('DB_HOST', "localhost")
DB_PORT = getenv("DB_PORT", "5432")
DB_USER = getenv("DB_USER", "postgres")
LOG_LEVEL = getenv('LOG_LEVEL', 'INFO')

assert DB_USER

DB_PASSWORD = getenv("DB_PASSWORD", '1234')

assert DB_PASSWORD

DB_NAME = getenv("DB_NAME", DB_USER)

assert DB_NAME

log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
log.info(f'got this vars!\n'
         f'DB_HOST = {DB_HOST}\n'
         f'DB_PORT = {DB_PORT}\n'
         f'DB_NAME = {DB_NAME}\n'
         f'LOG_LEVEL = {LOG_LEVEL}\n'
         f'RMQ_HOST = {RMQ_HOST}\n'
         f'RMQ_PORT = {RMQ_PORT}\n')
