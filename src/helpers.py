import pika
from random import choice
# import aiogram
from contextlib import contextmanager
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from walld_db.models import get_psql_dsn, User
# ЭТОТ УЖАС НУЖНО ПЕРЕПИСАТЬ НА КЛАСС
# TODO ATEXIT STUFF

class DB:
    def __init__(self, db_user, db_passwd, db_host, db_port, db_name):
        dsn = get_psql_dsn(db_user, db_passwd, db_host, db_port, db_name)
        self.engine = self.get_engine(dsn)
        self.session_maker = sessionmaker(bind=self.engine)

    @staticmethod
    def get_engine(dsn):
        return sa.create_engine(dsn)

    @contextmanager
    def get_connection(self):
        with self.engine.connect() as connection:
            yield connection

    @contextmanager
    def get_session(self):
        session = self.session_maker()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()


class Rmq:
    def __init__(self,
                 host='localhost',
                 port='5672',
                 user="guest",
                 password='guest'):
        self.creds = pika.PlainCredentials(user, password)
        self.params = pika.ConnectionParameters(host=host,
                                                port=port,
                                                credentials=self.creds)
        self.connection = pika.BlockingConnection()
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='check_out', durable=True)
        self.channel.queue_declare(queue='go_sql', durable=True)

    def get_message(self, amount: int):
        self.channel.basic_qos(prefetch_count=amount)
        method, props, body = next(self.channel.consume('check_out'))
        self.channel.cancel()
        self.channel.basic_ack(method.delivery_tag)
        return body

    def send_message(self, body):
        self.channel.basic_publish(exchange='',
                                   routing_key='go_sql',
                                   body=body)


def gen_answers(answer:bool) -> str:
    if answer:
        ll = ['Чотко', 'Сок', 'Невъебенно']
        emo = ['👌', '👌', '✅']
    else:
        ll = ["Так не пойдет", "Неа"]
        emo = ["❌", '👎']
    return f'{choice(ll)} - {choice(emo)}' # nosec

def gen_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(InlineKeyboardButton(gen_answers(True), callback_data="cb_yes"),
               InlineKeyboardButton(gen_answers(False), callback_data="cb_no"))
    return markup
