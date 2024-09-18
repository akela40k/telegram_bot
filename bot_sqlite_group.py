import sqlite3
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Загружаем переменные из .env файла
load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_IDS = set(map(int, os.getenv('ADMIN_IDS').split(',')))
GROUP_ID = int(os.getenv('GROUP_ID'))

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# Соединение с базой данных SQLite
def execute_query(query, args=(), fetch=False):
    with sqlite3.connect('polls.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        conn.commit()
        if fetch:
            return cursor.fetchall()


# Инициализация базы данных
def init_db():
    execute_query('''CREATE TABLE IF NOT EXISTS polls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT,
                        active INTEGER
                    )''')
    execute_query('''CREATE TABLE IF NOT EXISTS options (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        poll_id INTEGER,
                        option_text TEXT,
                        FOREIGN KEY (poll_id) REFERENCES polls (id)
                    )''')
    execute_query('''CREATE TABLE IF NOT EXISTS votes (
                        user_id INTEGER,
                        user_name TEXT,
                        poll_id INTEGER,
                        option_id INTEGER,
                        PRIMARY KEY (user_id, poll_id, option_id),
                        FOREIGN KEY (poll_id) REFERENCES polls (id)
                    )''')


# Функция для создания клавиатуры с вариантами ответов
def create_poll_keyboard(poll_id, selected_options=None, is_voting=True):
    options = execute_query("SELECT id, option_text FROM options WHERE poll_id = ?", (poll_id,), fetch=True)

    if not options:
        print(f"Не найдены варианты для опроса с poll_id = {poll_id}")
        return None

    buttons = []
    for option_id, option_text in options:
        button_text = f"✓ {option_text}" if selected_options and option_id in selected_options else option_text
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f'vote:{poll_id}:{option_id}')])

    if is_voting:
        buttons.append([InlineKeyboardButton(text="Проголосовать", callback_data=f'finish_vote:{poll_id}')])
    else:
        buttons.append([InlineKeyboardButton(text="Посмотреть результаты", callback_data=f'show_results:{poll_id}')])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


# Функция для создания клавиатуры с завершением голосования
def create_finish_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Голосование завершено", callback_data='voting_ended')]
    ])


# Функция для создания главного меню
def create_main_menu(is_admin=False):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать новый опрос")] if is_admin else [],
            [KeyboardButton(text="Запустить опрос")],
            [KeyboardButton(text="Показать результаты")],
            [KeyboardButton(text="Завершить активное голосование")] if is_admin else []
        ],
        resize_keyboard=True
    )
    return keyboard


# Проверка на администратора
def is_admin(user_id):
    return user_id in ADMIN_IDS


# Команда для создания опроса
@dp.message(Command('create_poll'))
async def create_poll(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав для создания опроса.")
        return

    await message.reply("Введите команду для создания опроса в формате: Вопрос? Вариант 1, Вариант 2, Вариант 3",
                        reply_markup=ReplyKeyboardMarkup(
                            keyboard=[[KeyboardButton(text="Отмена")]],
                            resize_keyboard=True
                        ))


# Обработчик текста для создания опроса
@dp.message(F.text)
async def handle_create_poll(message: Message):
    if message.text.lower() == "отмена":
        await message.reply("Создание опроса отменено.",
                            reply_markup=create_main_menu(is_admin=is_admin(message.from_user.id)))
        return

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split('?')
    if len(parts) != 2:
        await message.reply("Неправильный формат команды. Пример: Вопрос? Вариант 1, Вариант 2, Вариант 3")
        return

    question = parts[0].strip()
    options = parts[1].split(',')
    options = [option.strip() for option in options]

    # Вставляем вопрос в базу данных
    execute_query("INSERT INTO polls (question, active) VALUES (?, 0)", (question,))
    poll_id = execute_query("SELECT last_insert_rowid()", fetch=True)[0][0]

    # Вставляем варианты в базу данных
    for option in options:
        execute_query("INSERT INTO options (poll_id, option_text) VALUES (?, ?)", (poll_id, option))

    await message.reply(f"Опрос создан. Используйте команду /start_poll {poll_id} для запуска опроса.",
                        reply_markup=create_main_menu(is_admin=is_admin(message.from_user.id)))


# Команда для запуска опроса
@dp.message(Command('start_poll'))
async def start_poll(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав для запуска опроса.")
        return

    try:
        poll_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.reply("Введите команду для запуска опроса. Пример: /start_poll 1")
        return

    # Помечаем опрос как активный
    execute_query("UPDATE polls SET active = 1 WHERE id = ?", (poll_id,))

    # Получаем вопрос и варианты
    question = execute_query("SELECT question FROM polls WHERE id = ?", (poll_id,), fetch=True)
    if question:
        question = question[0][0]
    else:
        await message.reply("Опрос не найден.")
        return

    options = execute_query("SELECT id, option_text FROM options WHERE poll_id = ?", (poll_id,), fetch=True)
    if not options:
        await message.reply("Варианты для опроса не найдены.")
        return

    # Отправляем сообщение с опросом
    poll_keyboard = create_poll_keyboard(poll_id)
    if poll_keyboard:
        await message.reply(f"Опрос: {question}\nВыберите один или несколько вариантов:", reply_markup=poll_keyboard)
    else:
        await message.reply("Ошибка: невозможно создать клавиатуру для опроса.")


# Обработчик голосования
@dp.callback_query(F.data.startswith('vote:'))
async def handle_vote(callback_query):
    _, poll_id, option_id = callback_query.data.split(':')
    poll_id = int(poll_id)
    option_id = int(option_id)
    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.username or "Unknown"  # Используйте username или "Unknown" если его нет

    # Обработка голосования
    existing_vote = execute_query("SELECT option_id FROM votes WHERE user_id = ? AND poll_id = ?", (user_id, poll_id),
                                  fetch=True)
    existing_votes = {vote_id for vote_id, in existing_vote}

    if option_id in existing_votes:
        execute_query("DELETE FROM votes WHERE user_id = ? AND poll_id = ? AND option_id = ?",
                      (user_id, poll_id, option_id))
    else:
        execute_query("INSERT INTO votes (user_id, user_name, poll_id, option_id) VALUES (?, ?, ?, ?)",
                      (user_id, user_name, poll_id, option_id))

    # Получаем обновленные выбранные варианты для текущего пользователя
    user_votes = execute_query("SELECT option_id FROM votes WHERE user_id = ? AND poll_id = ?", (user_id, poll_id),
                               fetch=True)
    selected_options = {option_id for option_id, in user_votes}

    # Получаем вопрос опроса
    question = execute_query("SELECT question FROM polls WHERE id = ?", (poll_id,), fetch=True)
    if question:
        question = question[0][0]
    else:
        question = "Вопрос не найден"

    # Создаем клавиатуру с обновленным состоянием
    new_poll_keyboard = create_poll_keyboard(poll_id, selected_options)

    if new_poll_keyboard:
        # Обновляем сообщение с опросом
        await callback_query.message.edit_text(
            text=f"Опрос: {question}\nВыберите один или несколько вариантов:",
            reply_markup=new_poll_keyboard
        )
    else:
        # Сообщаем об ошибке
        await callback_query.answer("Ошибка: невозможно обновить клавиатуру для опроса.", show_alert=True)

    await callback_query.answer()


# Обработчик завершения голосования (кнопка "Проголосовать")
@dp.callback_query(F.data.startswith('finish_vote'))
async def finish_vote(callback_query):
    _, poll_id = callback_query.data.split(':')
    poll_id = int(poll_id)

    user_id = callback_query.from_user.id

    # Получаем вопрос и варианты ответа
    question = execute_query("SELECT question FROM polls WHERE id = ?", (poll_id,), fetch=True)
    if question:
        question = question[0][0]
    else:
        question = "Вопрос не найден"

    # Получаем результаты
    results = execute_query("""
        SELECT option_text, user_name, COUNT(votes.option_id) 
        FROM options
        LEFT JOIN votes ON options.id = votes.option_id
        WHERE options.poll_id = ?
        GROUP BY options.id, user_name
    """, (poll_id,), fetch=True)

    result_text = "\n".join(
        [f"{option_text} - {user_name}: {count} голосов" for option_text, user_name, count in results])
    result_text = f"Ваш голос учтен.\n\nОпрос: {question}\n{result_text}"

    # Обновляем сообщение с результатами
    finish_keyboard = create_finish_keyboard()
    await callback_query.message.edit_text(
        text=result_text,
        reply_markup=finish_keyboard
    )

    await callback_query.answer()


# Обработчик показа результатов
@dp.callback_query(F.data.startswith('show_results'))
async def show_results(callback_query):
    _, poll_id = callback_query.data.split(':')
    poll_id = int(poll_id)

    # Получаем вопрос и результаты
    question = execute_query("SELECT question FROM polls WHERE id = ?", (poll_id,), fetch=True)
    if question:
        question = question[0][0]
    else:
        question = "Вопрос не найден"

    results = execute_query("""
        SELECT option_text, user_name, COUNT(votes.option_id) 
        FROM options
        LEFT JOIN votes ON options.id = votes.option_id
        WHERE options.poll_id = ?
        GROUP BY options.id, user_name
    """, (poll_id,), fetch=True)

    result_text = "\n".join(
        [f"{option_text} - {user_name}: {count} голосов" for option_text, user_name, count in results])
    result_text = f"Результаты опроса:\nВопрос: {question}\n{result_text}"

    # Обновляем сообщение с результатами
    finish_keyboard = create_finish_keyboard()
    await callback_query.message.edit_text(
        text=result_text,
        reply_markup=finish_keyboard
    )

    await callback_query.answer()


# Обработчик создания нового опроса
@dp.message(F.text == "Создать новый опрос")
async def create_new_poll(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав для создания опроса.")
        return
    await message.reply("Введите команду для создания опроса в формате: Вопрос? Вариант 1, Вариант 2, Вариант 3",
                        reply_markup=ReplyKeyboardMarkup(
                            keyboard=[[KeyboardButton(text="Отмена")]],
                            resize_keyboard=True
                        ))


# Обработчик запуска опроса
@dp.message(F.text == "Запустить опрос")
async def start_poll_menu(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав для запуска опроса.")
        return
    await message.reply("Введите команду для запуска опроса в формате: /start_poll <poll_id>")


# Обработчик показа результатов
@dp.message(F.text == "Показать результаты")
async def show_results_menu(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав для показа результатов.")
        return
    await message.reply("Введите команду для показа результатов в формате: /show_results <poll_id>")


# Обработчик завершения активного голосования
@dp.message(F.text == "Завершить активное голосование")
async def end_active_poll(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав для завершения голосования.")
        return
    execute_query("UPDATE polls SET active = 0 WHERE active = 1")
    await message.reply("Активное голосование завершено.", reply_markup=create_main_menu(is_admin=True))


# Основной блок
if __name__ == "__main__":
    init_db()
    from aiogram import executor

    executor.start_polling(dp, skip_updates=True)
