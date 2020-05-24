import json
import logging
from threading import Thread
from time import sleep

import sqlalchemy as sa
import telebot

from sqlalchemy.orm import sessionmaker

from config import TG_TOKEN
from helpers import Rmq, gen_markup

from walld_db.models import User, get_psql_dsn
from walld_db.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

# Configure bot here
PROXY_URL = 'socks5://127.0.0.1:8123'  # Or 'socks5://host:port'
telebot.apihelper.proxy = {'https':'socks5://127.0.0.1:8123'}
logging.basicConfig(level=logging.INFO)

ENGINE = sa.create_engine(get_psql_dsn(DB_USER,
                                       DB_PASSWORD,
                                       DB_HOST,
                                       DB_PORT,
                                       DB_NAME))

bot = telebot.TeleBot(TG_TOKEN)
rmq = Rmq() # TODO ДОБАВИТЬ ВНЕШНИЕ ПЕрЕМЕННЫЕ

@bot.callback_query_handler(func=lambda call: True)
def do_stuff(call):
    Session = sessionmaker(bind=ENGINE)
    ses = Session()
    dude = ses.query(User).filter_by(telegram_id=call.from_user.id).first()

    bot.edit_message_reply_markup(dude.telegram_id,
                                  message_id=dude.telegram_last_message_id)
    if call.data == 'cb_yes':
        bot.answer_callback_query(call.id,
                                  "Отлично, добавляю в очередь на обработку")
        rmq.send_message(dude.json_review)
        print('Добавляю стафф')
    elif call.data == 'cb_no':
        bot.answer_callback_query(call.id, "Забываем про пикчу")
    dude.avail = True
    ses.commit()
    ses.close()

@bot.message_handler(commands=['reg'])
def cmd_reg(message):
    Session = sessionmaker(bind=ENGINE)
    ses = Session()
    dude = ses.query(User).filter_by(telegram_id=message.chat.id).one_or_none()
    if not dude:
        dude = User(nickname=message.chat.username,
                    telegram_id=message.chat.id)
        ses.add(dude)
        ses.commit()
    ses.close()
    # Вообще стоит у меня спросить
    bot.send_message(message.chat.id, 'regged!')

def main():
    Session = sessionmaker(bind=ENGINE)
    ses = Session()
    while True:
        for user in ses.query(User).filter(User.avail): # Мне лень писать это сейчас, пусть на стороне дб будет выборка тех у кого есть нужен пермишен скорее всего это where(...)
            body = json.loads(rmq.get_message(1).decode())
            text = f"""Новая пикча!
                       Разрешение - {body["width"]}x{body["height"]}
                       Сервис - {body["service"]}
                       Превью \n{body["preview_url"]}
                       Оригинал\n{body["download_url"]}"""
            message = bot.send_message(user.telegram_id, text)
            user.avail = False
            user.telegram_last_message_id = message.message_id
            user.json_review = body
            ses.commit()
        sleep(3)

if __name__ == '__main__':
    pol = Thread(target=bot.polling)
    ll = Thread(target=main)
    pol.start()
    ll.start()
