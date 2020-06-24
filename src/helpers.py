
from random import choice
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telebot import types


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

def gen_markup(stuff=None):
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
