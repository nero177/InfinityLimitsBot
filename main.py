import asyncio, logging, sys, sqlite3
from typing import Any, Dict

import pandas as pd
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.exceptions import TelegramBadRequest

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# SAMPLE_SPREADSHEET_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
# SAMPLE_RANGE_NAME = "Class Data!A2:E"

load_dotenv()

con = sqlite3.connect("app.db")
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS applies(user_id INT, name VARCHAR(100), email VARCHAR(100), phone VARCHAR(100))')

form_router = Router()

class Form(StatesGroup):
    name = State()
    email = State()
    phone = State()
    recycle = State()

def new_apply(user_id, name, email, phone):
    user = cur.execute(f'SELECT * FROM applies WHERE user_id={user_id}').fetchall()
    if len(user) == 0:
        cur.execute('INSERT INTO applies VALUES(?,?,?,?)', (user_id, name, email, phone,))
        con.commit()
    else:
        cur.execute('UPDATE applies SET user_id=?, name=?, email=?, phone=? WHERE user_id=?', (user_id, name, email, phone, user_id,))
        con.commit()



# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = "1Lgs-syGY_22oPH9rzPzPdIVyaoqke2cDVF9RYPyliqo"
SAMPLE_RANGE_NAME = "Class Data!A2:E"

def spreadsheet_init():
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = (
        sheet.values()
        .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME)
        .execute()
    )
    values = result.get("values", [])

    if not values:
      print("No data found.")
      return

    print("Name, Major:")
    for row in values:
      # Print columns A and E, which correspond to indices 0 and 4.
      print(f"{row[0]}, {row[4]}")
  except HttpError as err:
    print(err)

async def xlsx_save():
    file = 'applies.xlsx'
    users_id = []
    users_name = []
    users_email = []
    users_phone = []
    data = cur.execute('SELECT * FROM applies').fetchall()
    for user in data:
        users_id.append(str(user[0]))
        users_name.append(user[1])
        users_email.append(user[2])
        users_phone.append(user[3])
    
    new_dat = {'user_id' : users_id,
               'name' : users_name,
               'email' : users_email,
               'phone' : users_phone}
    
    df_new = pd.DataFrame(new_dat)
    # if os.path.exists(file):
    #     df_existing = pd.read_excel(file)
    #     df_updated = pd.concat([df_existing, df_new], ignore_index=True)
    # else:
    #     df_updated = df_new
    df_new.to_excel(file, index=False, header=True)

async def recycle_add(message: Message, state: FSMContext):
    recycle = (await state.get_data())['recycle']
    recycle[message.message_id] = message
    await state.update_data(recycle = recycle)

async def clear_recycle(state: FSMContext):
    recycle = (await state.get_data())['recycle']
    for x in recycle:
        try:
            await recycle[x].delete()
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
    await clear_recycle(state=state)
    await state.clear()
    await command_start(message, state)

@form_router.message(F.text.lower() == 'записатися знову')
async def update_applied(message: Message, state: FSMContext):
    await command_start(message, state)

@form_router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    # await spreadsheet_init()
    await state.update_data(recycle = {})
    await recycle_add(message=message, state=state)
    kb = [[KeyboardButton(text="Почати спочатку")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    msg = await message.answer("Ваше ім'я", reply_markup=keyboard)
    await recycle_add(message=msg, state=state)
    await state.set_state(Form.name)

@form_router.message(Form.name)
async def process_name(message: Message, state: FSMContext) -> None:
    await recycle_add(message=message, state=state)
    await state.update_data(name=message.text)
    msg = await message.answer("Введіть почту")
    await recycle_add(message=msg, state=state)
    await state.set_state(Form.email)

@form_router.message(Form.email)
async def process_email(message: Message, state: FSMContext) -> None:
    await recycle_add(message=message, state=state)
    data = await state.update_data(email=message.text)
    msg = await message.answer("Введіть номер")
    await recycle_add(message=msg, state=state)
    await state.set_state(Form.phone)

@form_router.message(Form.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    await recycle_add(message=message, state=state)
    data = await state.update_data(phone=message.text)
    await summary(message=message, data=data)
    await state.clear()

@form_router.message()
async def fludder_del(msg: Message):
    await msg.delete()

async def summary(message: Message, data: Dict[str, Any], positive: bool = True) -> None:
    name = data["name"]
    email = data["email"]
    phone = data["phone"]
    new_apply(message.chat.id, name, email, phone)
    text = "Ви успішного записались на вебінар, в ближайший час з вами зв'яжеться менеджер."
    users = cur.execute('SELECT * FROM applies').fetchall()
    print(users)
    kb = [[KeyboardButton(text="Записатися знову")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text=text, reply_markup=keyboard)
    await xlsx_save()

async def main():
    bot = Bot(token=os.environ.get("BOT_TOKEN"), parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())