from contextlib import contextmanager
from random import choice
from time import sleep

import pika
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from walld_db.models import (Category, SubCategory, Tag, User,
                             get_psql_dsn, Moderator)

# TODO ATEXIT STUFF

class DB:
    def __init__(self, db_user, db_passwd, db_host, db_port, db_name):
        dsn = get_psql_dsn(db_user, db_passwd, db_host, db_port, db_name)
        self.engine = self.get_engine(dsn)
        self.session_maker = sessionmaker(bind=self.engine)

    @staticmethod
    def get_engine(dsn):
        return sa.create_engine(dsn, echo=True)

    @contextmanager
    def get_connection(self):
        with self.engine.connect() as connection:
            yield connection

    @contextmanager
    def get_session(self, expire=False, commit=True):
        session = self.session_maker(expire_on_commit=expire)
        try:
            yield session
        except:
            session.rollback()
        finally:
            if commit:
                session.commit()
            session.close()

    @property
    def categories(self):
        with self.get_session(commit=False) as ses:
            cats = ses.query(Category.category_name).all()
            return [i[0] for i in cats]

    @property
    def users(self) -> list:
        with self.get_session(commit=False) as ses:
            users = ses.query(User.nickname)
        return [i[0] for i in users]

    @property
    def tags(self) -> list:
        with self.get_session(commit=False) as ses:
            tags = ses.query(Tag.tag_name)
        return [i[0] for i in tags]

    def get_category(self, category_name, session=None):
        if session:
            cat = session.query(Category).filter_by(category_name=category_name).one_or_none()
        else:
            with self.get_session(commit=False) as ses:
                cat = ses.query(Category).filter_by(category_name=category_name).one_or_none()
        return cat

    def get_state(self, tg_id, table): # TODO add sessions
        with self.get_session(commit=False) as ses:
            l = ses.query(User, table.tg_state).\
                join(table, User.user_id == table.user_id).\
                filter(User.telegram_id == tg_id)
            l = l.one_or_none()
            if l:
                return l[1]
            return l

    def get_moderator(self, tg_id, session=None):
        l = session.query(User, Moderator).\
            join(Moderator, User.user_id == Moderator.user_id).\
            filter(User.telegram_id==tg_id).one()
        return l

    def get_sub_categories(self, category) -> list:
        with self.get_session(commit=False) as ses:
            cat_id = self.get_category(category).category_id
            sub_cats = ses.query(SubCategory).\
                       filter_by(category_id=cat_id).\
                       all()
            stuff = [i.sub_category_name for i in sub_cats]
            return stuff
    


class Rmq:
    def __init__(self,
                 host='localhost',
                 port='5672',
                 user="guest",
                 passw='guest'):
        self.creds = pika.PlainCredentials(user, passw)
        self.params = pika.ConnectionParameters(host=host,
                                                port=port,
                                                credentials=self.creds)
        while True:
            try:
                self.connection = pika.BlockingConnection()
                break
            except pika.exceptions.AMQPConnectionError:
                sleep(3)
                continue
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


def gen_answers(answer: bool) -> str:
    if answer:
        ll = ['Чотко', 'Сок', 'Невъебенно']
        emo = ['👌', '👌', '✅']
    else:
        ll = ["Так не пойдет", "Неа"]
        emo = ["❌", '👎']
    return f'{choice(ll)} - {choice(emo)}' # nosec

def gen_inline_markup(cb_yes='cb_yes', cb_no='cb_no'):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(InlineKeyboardButton(gen_answers(True), callback_data=cb_yes),
               InlineKeyboardButton(gen_answers(False), callback_data=cb_no))
    return markup

def gen_markup(stuff=None): # TODO мне не нравится этот кстыль с deep
    markup = types.ReplyKeyboardMarkup()
    if stuff:
        for i in stuff:
            markup.row(i)
    else: 
        markup = types.ReplyKeyboardRemove()
    return markup

def prepare_json_review(body):
    text = (f'Сервис - {body["service"]}\n'
            f'ШиринаХВысота - {body["width"]}X{body["height"]}\n'
            f'Превью урл - \n{body["preview_url"]}\n'
            f'Категория - {body["category"]}\n'
            f'Под категория - {body["sub_category"]}\n'
            f'Тэги - {body["tags"]}')
    return text
