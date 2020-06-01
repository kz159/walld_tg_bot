import json
import random
from threading import Thread
from time import sleep

import telebot
from pika.exceptions import AMQPConnectionError
from walld_db.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from walld_db.models import User, Admin, AdminStates, Picture, Moderator, ModStates

from sqlalchemy import distinct
from config import TG_TOKEN
from helpers import DB, Rmq, gen_markup, gen_inline_markup

# Configure bot here
PROXY_URL = 'socks5://127.0.0.1:8123'  # Or 'socks5://host:port'
#logging.basicConfig(level=logging.INFO)

# TODO СОРТИРОВКА ПО КАТЕГОРИЯМ, ТЭГАМ 

telebot.apihelper.proxy = {'https':'socks5://127.0.0.1:8123'}
bot = telebot.TeleBot(TG_TOKEN)
print('conecting to rmq...', end=' ')
while True:
    try:
        rmq = Rmq() # TODO ДОБАВИТЬ ВНЕШНИЕ ПЕрЕМЕННЫЕ
    except AMQPConnectionError:
        sleep(1)
        continue
    print('ok')
    break

db = DB(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)


@bot.callback_query_handler(func=lambda call: True)
def do_stuff(call):
    with db.get_session() as ses:
        dude = ses.query(User, Moderator).filter_by(telegram_id=call.from_user.id).one_or_none()

        if call.data == 'cb_yes':
            dude.Moderator.tg_state = ModStates.choosing_category
            bot.answer_callback_query(call.id, "Погнали")
            categories = db.get_categories()
            categories.append('Добавить новую...')
            bot.edit_message_reply_markup(dude.User.telegram_id,
                                        message_id=dude.Moderator.last_message,
                                        reply_markup=gen_markup(categories, deep=False))
            # rmq.send_message(dude.json_review)

        elif call.data == 'cb_no':
            bot.edit_message_reply_markup(dude.User.telegram_id,
                                        message_id=dude.Moderator.last_message)
            bot.answer_callback_query(call.id, "Забываем про пикчу")
            dude.Moderator.tg_state = ModStates.available


@bot.message_handler(commands=['reg'])
def cmd_reg(message):
    """
    Регестрирует пользователя
    и если нет пользователей вообще
    делает его админом
    """
    with db.get_session() as ses:
        is_there_admins = ses.query(User).one_or_none()
        dude = ses.query(User).\
               filter_by(telegram_id=message.chat.id).one_or_none()
        if not dude:
            dude = User(nickname=message.chat.username,
                        telegram_id=message.chat.id)
            ses.add(dude)
            ses.commit()
            bot.send_message(message.chat.id, 'Regged!')
            if not is_there_admins:
                ses.add(Admin(admin_id=dude.user_id))
        else:
            bot.send_message(message.chat.id, 'Already!')


@bot.message_handler(commands=['raise_user'])
def raise_user(message):
    with db.get_session() as ses:
        dude = ses.query(User, Admin).filter_by(telegram_id=message.chat.id).one_or_none()
        if getattr(dude, 'Admin'):
            dudes = db.get_users().all()
            bot.send_message(message.chat.id, 'which one?', reply_markup=gen_markup(dudes))
            dude.Admin.tg_state = AdminStates.raising_user


@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Admin) == AdminStates.raising_user)
def raise_user_step_two(message):
    with db.get_session() as ses:
        user = ses.query(User).filter_by(nickname=message.text).one_or_none()
        if user:
            ses.add(Moderator(mod_id=user.user_id))

            bot.send_message(message.chat.id, 'ok')
        else:
            bot.send_message(message.chat.id, 'not found user')
        admin = ses.query(User, Admin).filter_by(telegram_id=message.chat.id).one()
        admin.Admin.tg_state = AdminStates.available


def main():
    while True:
        with db.get_session() as ses:
            for user in ses.query(Moderator, User).filter_by(tg_state=ModStates.available): 
                # Мне лень писать это сейчас, пусть на стороне дб
                # будет выборка тех у кого есть нужен пермишен
                # скорее всего это where(...)
                body = json.loads(rmq.get_message(1).decode())
                text = ("Новая пикча!\n"
                        f"Разрешение - {body['width']}x{body['height']}\n"
                        f"Сервис - {body['service']}\n"
                        f'Превью - \n{body["preview_url"]}\n'
                        f'Оригинал - \n{body["download_url"]}\n')
                message = bot.send_message(user.User.telegram_id,
                                           text, reply_markup=gen_inline_markup())
                user.Moderator.tg_state = ModStates.got_picture
                user.Moderator.last_message = message.message_id
                user.Moderator.json_review = body
        sleep(3)

if __name__ == '__main__':
    pol_updates = Thread(target=bot.polling)
    send_pics = Thread(target=main)
    pol_updates.start()
    send_pics.start()
