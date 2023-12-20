import asyncio, logging, sys, sqlite3
from typing import Any, Dict

import pandas as pd
import os
import re
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, \
ReplyKeyboardRemove, FSInputFile, InlineKeyboardMarkup, \
InlineKeyboardButton, CallbackQuery

from aiogram.exceptions import TelegramBadRequest
from datetime import datetime

load_dotenv()

ADMIN_IDS = [679021494, 491021529, 686443228]

con = sqlite3.connect("app.db")
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS applies(user_id INT, name VARCHAR(100), email VARCHAR(100), phone VARCHAR(100), date VARCHAR(200))')

form_router = Router()

bot = Bot(token=os.environ.get("BOT_TOKEN"), parse_mode=ParseMode.HTML)
dp = Dispatcher()

class Form(StatesGroup):
    name = State()
    email = State()
    phone = State()
    recycle = State()

class Spam(StatesGroup):
    text = State()

def new_apply(user_id, name, email, phone):
    user = cur.execute(f'SELECT * FROM applies WHERE user_id={user_id}').fetchall()

    print(user)

    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

    if len(user) == 0:
        print('inserting')
        cur.execute('INSERT INTO applies VALUES(?,?,?,?,?)', (user_id, name, email, phone, dt_string))
        con.commit()
    else:
        print('updating')
        cur.execute('UPDATE applies SET user_id=?, name=?, email=?, phone=?, date=? WHERE user_id=?', (user_id, name, email, phone, dt_string, user_id,))
        con.commit()

async def xlsx_save():
    file = 'applies.xlsx'
    users_name = []
    users_email = []
    users_phone = []
    users_date = []

    data = cur.execute('SELECT * FROM applies').fetchall()
    for user in data:
        users_name.append(str(user[1]))
        users_email.append(str(user[2]))
        users_phone.append(str(user[3]))
        users_date.append(str(user[4]))

    new_dat = {
               'name' : users_name,
               'email' : users_email,
               'phone' : users_phone,
               'date' : users_date}
    
    df_new = pd.DataFrame(new_dat)
    df_new.to_excel(file, index=False, header=True)

async def recycle_add(message: Message, state: FSMContext):
    pass
    # recycle = (await state.get_data())['recycle']
    # recycle[message.message_id] = message
    # await state.update_data(recycle = recycle)

async def clear_recycle(state: FSMContext):
    recycle = (await state.get_data())['recycle']
    for x in recycle:
        try:
            await recycle[x].delete()
        except TelegramBadRequest:
            pass

async def spam(text: str) -> None:
    users = cur.execute('SELECT * FROM applies').fetchall()
    for user in users: 
        try: 
            await bot.send_message(user[0], text, parse_mode=ParseMode.HTML)
        except TelegramBadRequest: 
            pass     

@form_router.message(F.text.lower() == "почати спочатку")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    logging.info("Cancelling state %r", current_state)
    msg = await message.answer("Скасовано.")
    await recycle_add(message=msg, state=state)
    # await clear_recycle(state=state)
    await state.clear()
    await command_start(message, state)

@form_router.message(F.text.lower() == 'записатися знову')
async def update_applied(message: Message, state: FSMContext):
    await command_start(message, state)

@form_router.message(F.text.lower() == 'всі заявки')
async def all_applies(message: Message):
    file = FSInputFile('applies.xlsx')
    await bot.send_document(chat_id=message.chat.id, document=file) 

@form_router.message(F.text.lower() == 'скасувати', Spam.text)
async def cancel(message: Message, state: FSMContext):
    await message.answer("Скасовано.")
    await command_start(message, state)
    await state.clear()

@form_router.message(F.text.lower() == 'розіслати повідомлення')
async def start_spam(message: Message, state: FSMContext):
    await state.set_state(Spam.text)

    kb = [[KeyboardButton(text="Скасувати")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer('Введіть текст для розсилки', reply_markup=keyboard)
    
@form_router.message(Spam.text)
async def spam_text(message: Message, state: FSMContext):
    await spam(message.text)
    await message.answer('Розсилка закінчена')
    await state.clear()
    await command_start(message, state)

@form_router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    await state.update_data(recycle = {})
    await recycle_add(message=message, state=state)

    is_admin = False

    for admin_id in ADMIN_IDS:
        if admin_id == message.chat.id:
            is_admin = True

    if is_admin:
        kb = [[KeyboardButton(text="Почати спочатку")], [KeyboardButton(text="Всі заявки")], [KeyboardButton(text="Розіслати повідомлення")]]
    else:
        kb = [[KeyboardButton(text="Почати спочатку")]]

    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    inlineKeyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Так", callback_data="ask_user_yes")], [InlineKeyboardButton(text="Ні", callback_data="ask_user_no")]])

    msg = await message.answer("Вітаємо у Infinity Limits 👋\nМи навчаємо крок за кроком і допомагаємо отримати свій перший капітал для трейдингу 📊", reply_markup=keyboard)
    msg2 = await message.answer("Чи хотіли б ви покращити свої знання в світі трейдингу?", reply_markup=inlineKeyboard)
    await recycle_add(message=msg, state=state)
    await recycle_add(message=msg2, state=state)

@dp.callback_query()
async def process_callback_answer(callback_query: CallbackQuery, state: FSMContext):
    data = callback_query.data

    print(data)

    if(data == 'ask_user_yes'):
        await bot.send_message(callback_query.from_user.id, "Ваше ім'я")
        await state.set_state(Form.name)
    elif(data == 'ask_user_no'):
        inlineKb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Почати спочатку", callback_data="again")]])
        await bot.send_message(callback_query.from_user.id, "Навчання в трейдингу є важливою складовою успіху в цій сфері.\n\nПросто сигнали не працюють без аналізу фінансових ринків та прийняття обґрунтованих торгових рішень.\n\n👉 Дай свій фідбек - @InfinityLimits", reply_markup=inlineKb)
    elif(data == 'again'):
        state.clear()
        await command_start(callback_query.message, state)

@form_router.message(Form.name)
async def process_name(message: Message, state: FSMContext) -> None:
    await recycle_add(message=message, state=state)
    await state.update_data(name=message.text)
    msg = await message.answer("Введіть пошту")
    await recycle_add(message=msg, state=state)
    await state.set_state(Form.email)

@form_router.message(Form.email)
async def process_email(message: Message, state: FSMContext) -> None:
    await recycle_add(message=message, state=state)
    await state.update_data(email=message.text)
    kb = [[KeyboardButton(text="Відправити мій номер", request_contact=True)]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    msg = await message.answer("Введіть номер", reply_markup=keyboard)
    await recycle_add(message=msg, state=state)
    await state.set_state(Form.phone)

@form_router.message(F.content_type.in_({'contact', 'text'}), Form.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    await recycle_add(message=message, state=state)

    if message.content_type == 'contact':
        data = await state.update_data(phone=message.contact.phone_number)
    elif message.content_type == 'text':
        phone_regex = re.compile('^\+?\d+$')
        match = phone_regex.match(message.text)
        if match is None:
            await message.answer("Введіть валідний номер")
            message.text = ''
            await process_phone(message, state)   

        data = await state.update_data(phone=message.text)
    await summary(message=message, data=data)
    await state.clear()

# @form_router.message(Form.phone)
# async def process_phone(message: Message, state: FSMContext) -> None:
#     await recycle_add(message=message, state=state)
#     data = await state.update_data(phone=message.text)
#     await summary(message=message, data=data)
#     await state.clear()

# @form_router.message()
# async def fludder_del(msg: Message):
#     await msg.delete()

async def summary(message: Message, data: Dict[str, Any], positive: bool = True) -> None:
    name = data["name"]
    email = data["email"]
    phone = data["phone"]
    new_apply(message.chat.id, name, email, phone)
    text = "Авторський курс з ключовими стратегіями та порадами. Матеріали від провідного експерта у галузі Форекс 👉 https://youtu.be/--lqBskInHU\n\nВи успішного записались на курси, в найближчий час з вами зв'яжеться менеджер.\nлінк -  https://t.me/+qQIJM2_AeUExYWYy"

    kb = [[KeyboardButton(text="Записатися знову")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text=text, reply_markup=keyboard)
    await xlsx_save()

async def main():
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
