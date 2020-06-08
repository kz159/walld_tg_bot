"""
Main bot module
"""
import json
from threading import Thread
from time import sleep

import telebot
from pika.exceptions import AMQPConnectionError
from walld_db.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from walld_db.models import (Admin, AdminStates, Category, Moderator,
                             ModStates, SubCategory, User, Tag)

from config import TG_TOKEN
from helpers import DB, Rmq, gen_inline_markup, gen_markup, prepare_json_review
from meta import Answers

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
    """
    На присланной картинке поставлены две кнопки да и нет
    Эта функция обрабатывает нажим кнопок
    По сути 2 шаг по обработке картинки
    """
    with db.get_session() as ses:
        dude = ses.query(User, Moderator).filter_by(telegram_id=call.from_user.id).one_or_none()

        if (call.data == 'cb_yes' or call.data == 'done_no'):
            dude.Moderator.tg_state = ModStates.choosing_category
            bot.answer_callback_query(call.id, "Погнали")
            categories = db.categories
            categories.append('Добавить новую...')
            bot.edit_message_reply_markup(dude.User.telegram_id,
                                          message_id=dude.Moderator.last_message)
            bot.send_message(call.from_user.id, 'Категория!', reply_markup=gen_markup(categories))

        elif call.data == 'cb_no':
            bot.edit_message_reply_markup(dude.User.telegram_id,
                                        message_id=dude.Moderator.last_message)
            bot.answer_callback_query(call.id, "Забываем про пикчу")
            dude.Moderator.tg_state = ModStates.available

        elif call.data == 'done_yes':
            bot.edit_message_reply_markup(dude.User.telegram_id,
                                          message_id=dude.Moderator.last_message)
            bot.answer_callback_query(call.id, "Спасибо! Бросил на обработку")
            dude.Moderator.pics_accepted += 1
            dude.Moderator.json_review['mod_review_id'] = dude.User.user_id
            rmq.send_message(str(dude.Moderator.json_review))
            bot.send_message(call.from_user.id, 'ok', reply_markup=gen_markup())
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

@bot.message_handler(command=['reset'])
def reset_user(message):
    with db.get_session() as ses:
        user = ses.query(User, Moderator, Admin).filter_by(telegram_id=message.chat.id).one()
        if getattr(user, 'Moderator'):
            user.Moderator.tg_state = ModStates.available
        if getattr(user, "Admin"):
            user.Admin.tg_state = AdminStates.available

@bot.message_handler(commands=['raise_user'])
def raise_user(message):
    """
    Чисто админский метод
    С помощью него можно добавить
    Юзера в модераторы т.е. дать возможность чекать картинки
    выдаем клавиатуру со всеми известными юзерами
    """
    with db.get_session() as ses:
        dude = ses.query(User, Admin).\
               filter_by(telegram_id=message.chat.id).one_or_none()
        if getattr(dude, 'Admin'):
            dudes = db.users
            bot.send_message(message.chat.id,
                             'which one?',
                             reply_markup=gen_markup(dudes))
            dude.Admin.tg_state = AdminStates.raising_user

@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Admin) == AdminStates.raising_user)
def raise_user_step_two(message):
    """
    Обработка второго шага повышение привелегий юзера
    """
    with db.get_session() as ses:
        user = ses.query(User).filter_by(nickname=message.text).one_or_none()
        if user:
            ses.add(Moderator(mod_id=user.user_id))
            bot.send_message(message.chat.id, Answers.ok)
        else:
            bot.send_message(message.chat.id, 'not found user')
        admin = ses.query(User, Admin).filter_by(telegram_id=message.chat.id).one()
        admin.Admin.tg_state = AdminStates.available

@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Moderator) == ModStates.choosing_category)
def apply_category(message):
    """
    Обрабатываем 2 шаг
    выдаем 3 стадию если нет необходимой категории
    выдаем 4 стадию если желаемая категория существует
    """
    with db.get_session() as ses: # TODO Очень много with session, мб есть прикол чтоб запихнуть это в декоратор?
        user = ses.query(User, Moderator).\
               filter_by(telegram_id=message.chat.id).one()
        if message.text in db.categories:
            user.Moderator.json_review['category'] = message.text
            user.Moderator.tg_state = ModStates.choosing_sub_category
            sub_cats = db.get_sub_categories(message.text)
            sub_cats.append(Answers.add_new)
            bot.send_message(message.chat.id,
                             'Неплохо, далее под_категория',
                             reply_markup=gen_markup(sub_cats))

        elif message.text == Answers.add_new:
            user.Moderator.tg_state = ModStates.making_category
            bot.send_message(message.chat.id, 'Окей, дай мне название категории')

        else:
            bot.send_message(message.chat.id, ('Ты находишься в состоянии '
                                               'подбора категории, кнопки '
                                               'доступны в клавиатуре'))

@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Moderator) == ModStates.choosing_sub_category)
def apply_sub_category(message):
    """
    Обработаем 4 стадию
    Выдаем 5 стадию если нужной подкатегории нет
    Выдаем финальную 6 стадию если есть
    """
    with db.get_session() as ses:
        user = ses.query(User, Moderator).filter_by(telegram_id=message.chat.id).one()
        cat = user.Moderator.json_review['category']

        if message.text in db.get_sub_categories(cat):
            user.Moderator.json_review['sub_category'] = message.text
            user.Moderator.tg_state = ModStates.choosing_tags
            tags = db.tags
            tags.append(Answers.add_new)
            tags.append(Answers.ok)
            bot.send_message(message.chat.id,
                             'Тэги!',
                             reply_markup=gen_markup(tags))

        elif message.text == Answers.add_new:
            user.Moderator.tg_state = ModStates.making_sub_category
            bot.send_message(message.chat.id,
                             'Окей, дай мне название подкатегории')

        else:
            bot.send_message(message.chat.id, ('Ты находишься в состоянии '
                                               'подбора подкатегории, кнопки '
                                               'доступны в клавиатуре'))

@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Moderator) == ModStates.choosing_tags)
def choose_tag(message):
    """
    Выбираем тэги тут
    TODO Сделать эмодзи выбранного тэга
    """

    with db.get_session() as ses:
        user = ses.query(User, Moderator).filter_by(telegram_id=message.chat.id).one()

        if not user.Moderator.json_review.get('tags'):
            user.Moderator.json_review['tags'] = []
        pic_tags = user.Moderator.json_review['tags']
        if (message.text in db.tags and message.text not in pic_tags):
            pic_tags.append(message.text)
            user.Moderator.json_review['tags'] = pic_tags
            bot.send_message(message.chat.id, Answers.ok)

        elif message.text in pic_tags:
            pic_tags.remove(message.text)
            user.Moderator.json_review['tags'] = pic_tags
            bot.send_message(message.chat.id, Answers.deleted)

        elif message.text == Answers.add_new:
            bot.send_message(message.chat.id, "Добавим новый тэг, введи название")
            user.Moderator.tg_state = ModStates.making_tags

        elif message.text == Answers.ok:
            review = bot.send_message(message.chat.id,
                                      prepare_json_review(user.Moderator.json_review),
                                      reply_markup=gen_inline_markup(cb_yes='done_yes',
                                                                     cb_no='done_no'))
            user.Moderator.last_message = review.message_id
        print('pk')
    print('ok')
@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Moderator) == ModStates.making_tags)
def create_tag(message):
    if (message.text == Answers.add_new or message.text == Answers.ok):
        bot.send_message(message.chat.id, 'Не ошибся ли?')
        return
    with db.get_session() as ses:
        ses.add(Tag(tag_name=message.text))
        user = ses.query(User, Moderator).filter_by(telegram_id=message.chat.id).one()
        user.Moderator.tg_state = ModStates.choosing_tags
    tags = db.tags
    tags.append(Answers.add_new)
    tags.append(Answers.ok)
    bot.send_message(user.User.telegram_id,
                     Answers.done,
                     reply_markup=gen_markup(tags))

@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Moderator) == ModStates.making_sub_category)
def create_sub_category(message):
    if message.text == Answers.add_new:
        bot.send_message(message.chat.id, 'Не ошибся ли?')
        return
    with db.get_session() as ses:
        user = ses.query(User, Moderator).filter_by(telegram_id=message.chat.id).one()
        category = user.Moderator.json_review['category']
        cat_id = db.get_category(category).category_id
        ses.add(SubCategory(category_id=cat_id,
                            sub_category_name=message.text))
        user.Moderator.tg_state = ModStates.choosing_sub_category
            
    sub_cats = db.get_sub_categories(category)
    sub_cats.append(Answers.add_new)
    bot.send_message(message.chat.id,
                     Answers.done,
                     reply_markup=gen_markup(sub_cats))


@bot.message_handler(func=lambda m: db.get_state(m.chat.id, Moderator) == ModStates.making_category)
def create_category(message):
    if message.text == Answers.add_new:
        bot.send_message(message.chat.id, 'Не ошибся ли?')
        return
    with db.get_session() as ses:
            ses.add(Category(category_name=message.text))
            user = ses.query(User, Moderator).filter_by(telegram_id=message.chat.id).one()
            user.Moderator.tg_state = ModStates.choosing_category
        
    categories = db.categories
    categories.append(Answers.add_new)
    bot.send_message(user.User.telegram_id,
                     Answers.done,
                     reply_markup=gen_markup(categories))
            



def send_pics_to_mods():
    """
    Присылаем всем модераторам у которых статус
    Available картинку на оценку
    """
    while True:
        with db.get_session() as ses:
            avail_mods = ses.query(Moderator, User).filter_by(tg_state=ModStates.available)
            for user in avail_mods:
                body = json.loads(rmq.get_message(1).decode())
                text = ("Новая пикча!\n"
                        f"Разрешение - {body['width']}x{body['height']}\n"
                        f"Сервис - {body['service']}\n"
                        f'Превью - \n{body["preview_url"]}\n'
                        f'Оригинал - \n{body["download_url"]}\n')
                message = bot.send_message(user.User.telegram_id,
                                           text,
                                           reply_markup=gen_inline_markup())
                user.Moderator.tg_state = ModStates.got_picture
                user.Moderator.last_message = message.message_id
                user.Moderator.json_review = body
        sleep(3)

def main(pics=False, updates=False):
    """
    Main function that starts all threads
    pass true to variable pics for sending pics thread
    pass true for updates to start polling updates
    """
    pol_updates = Thread(target=bot.polling)
    send_pics = Thread(target=send_pics_to_mods)
    if pics:
        send_pics.start()
    if updates:
        pol_updates.start()

if __name__ == '__main__':
    main(pics=True, updates=True)
