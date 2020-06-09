from os import getenv

TG_TOKEN = getenv('TG_TOKEN')

RMQ_HOST = getenv('RMQ_HOST')
RMQ_PORT = getenv('RMQ_PORT')
RMQ_USER = getenv('RMQ_USER')
RMQ_PASS = getenv('RMQ_PASS')

DB_HOST = getenv('DB_HOST', "localhost")
DB_PORT = getenv("DB_PORT", "5432")
DB_USER = getenv("DB_USER")

assert DB_USER

DB_PASSWORD = getenv("DB_PASSWORD")

assert DB_PASSWORD

DB_NAME = getenv("DB_NAME")

assert DB_NAME
