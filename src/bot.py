import json
import logging
from threading import Thread
from time import sleep

import telebot
from walld_db.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from walld_db.models import User

from config import TG_TOKEN
from helpers import DB, Rmq, gen_markup

# Configure bot here
PROXY_URL = 'socks5://127.0.0.1:8123'  # Or 'socks5://host:port'
telebot.apihelper.proxy = {'https':'socks5://127.0.0.1:8123'}
logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(TG_TOKEN)
rmq = Rmq() # TODO ДОБАВИТЬ ВНЕШНИЕ ПЕрЕМЕННЫЕ
db = DB(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)

@bot.callback_query_handler(func=lambda call: True)
def do_stuff(call):
    with db.get_session() as ses:
        dude = ses.query(User).filter_by(telegram_id=call.from_user.id).first()
        dude.avail = True
        ses.expunge_all()

    bot.edit_message_reply_markup(dude.telegram_id,
                                  message_id=dude.telegram_last_message_id)
    if call.data == 'cb_yes':
        bot.answer_callback_query(call.id, "Отлично, добавляю в очередь на обработку")
        rmq.send_message(dude.json_review)
    elif call.data == 'cb_no':
        bot.answer_callback_query(call.id, "Забываем про пикчу")

@bot.message_handler(commands=['reg'])
def cmd_reg(message):
    with db.get_session() as ses:
        dude = ses.query(User).filter_by(telegram_id=message.chat.id).one_or_none()
        if not dude:
            dude = User(nickname=message.chat.username,
                        telegram_id=message.chat.id)
            ses.add(dude)

    # Вообще стоит у меня спросить
    bot.send_message(message.chat.id, 'regged!')

def main():
    while True:
        with db.get_session() as ses:
            for user in ses.query(User).filter(User.avail): 
                # Мне лень писать это сейчас, пусть на стороне дб
                # будет выборка тех у кого есть нужен пермишен
                # скорее всего это where(...)
                body = json.loads(rmq.get_message(1).decode())
                text = ("Новая пикча!\n"
                        f"Разрешение - {body['width']}x{body['height']}\n"
                        f"Сервис - {body['service']}\n"
                        f'Превью - \n{body["preview_url"]}\n'
                        f'Оригинал - \n{body["download_url"]}\n')
                message = bot.send_message(user.telegram_id,
                                           text,
                                           reply_markup=gen_markup())
                user.avail = False
                user.telegram_last_message_id = message.message_id
                user.json_review = body
        sleep(3)

if __name__ == '__main__':
    pol_updates = Thread(target=bot.polling)
    send_pics = Thread(target=main)
    pol_updates.start()
    send_pics.start()
