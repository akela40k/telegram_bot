import sqlite3
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Загружаем переменные из .env файла
load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_IDS = {838959021,838959024}  # Список ID администраторов

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
                        poll_id INTEGER,
                        option_id INTEGER,
                        PRIMARY KEY (user_id, poll_id, option_id)
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
async def create_poll_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для создания опросов.")
        return

    try:
        command_text = message.text.split(' ', 1)[1].strip()

        if '?' not in command_text:
            raise ValueError("Не найден знак вопроса '?' в команде.")

        question, options_text = command_text.split('?', 1)
        question = question.strip() + '?'
        options = [option.strip() for option in options_text.split(',')]

        if len(options) < 2:
            raise ValueError("Необходимо указать как минимум два варианта ответа.")

        execute_query("UPDATE polls SET active = 0 WHERE active = 1")

        with sqlite3.connect('polls.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO polls (question, active) VALUES (?, 1)", (question,))
            poll_id = cursor.lastrowid

            for option in options:
                cursor.execute("INSERT INTO options (poll_id, option_text) VALUES (?, ?)", (poll_id, option))
            conn.commit()

        await message.answer("Опрос создан! Используй кнопку 'Запустить опрос', чтобы начать.",
                             reply_markup=create_main_menu(is_admin=True))

    except (IndexError, ValueError) as e:
        await message.answer(f"Ошибка: {str(e)}\nПример: /create_poll Вопрос? Вариант 1, Вариант 2, Вариант 3")


# Команда для старта опроса
@dp.message(F.text == "Запустить опрос")
async def start_poll_command(message: Message):
    poll = execute_query("SELECT id, question, active FROM polls WHERE active = 1", fetch=True)

    if not poll:
        await message.answer("Нет активных опросов.")
        return

    poll_id, question, is_active = poll[0]
    if is_active == 0:
        await message.answer("Опрос завершен. Результаты:")
        return

    user_votes = execute_query("SELECT option_id FROM votes WHERE user_id = ? AND poll_id = ?",
                               (message.from_user.id, poll_id), fetch=True)
    selected_options = {option_id for option_id, in user_votes}

    poll_keyboard = create_poll_keyboard(poll_id, selected_options)

    if not poll_keyboard:
        await message.answer("Ошибка: невозможно создать клавиатуру для опроса.")
        return

    await message.answer(f"Опрос: {question}\nВыберите один или несколько вариантов:", reply_markup=poll_keyboard)


# Команда для создания нового опроса
@dp.message(F.text == "Создать новый опрос")
async def new_poll(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для создания опросов.")
        return

    await message.answer(
        "Введите команду для создания нового опроса. Пример: /create_poll Вопрос? Вариант 1, Вариант 2, Вариант 3",
        reply_markup=create_main_menu(is_admin=True))


# Команда для показа результатов
@dp.message(F.text == "Показать результаты")
async def show_results(message: Message):
    active_poll = execute_query("SELECT id, question FROM polls WHERE active = 0", fetch=True)
    if not active_poll:
        await message.answer("Нет завершенных опросов.")
        return

    results_text = ""
    for poll_id, question in active_poll:
        results = execute_query("""
            SELECT option_text, COUNT(votes.option_id) 
            FROM options
            LEFT JOIN votes ON options.id = votes.option_id
            WHERE options.poll_id = ?
            GROUP BY options.id
        """, (poll_id,), fetch=True)

        result_text = "\n".join([f"{option}: {count} голосов" for option, count in results])
        results_text += f"\n\nОпрос: {question}\n{result_text}"

    await message.answer(results_text)


# Команда для завершения активного голосования
@dp.message(F.text == "Завершить активное голосование")
async def finish_active_poll(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для завершения активных опросов.")
        return

    active_poll = execute_query("SELECT id FROM polls WHERE active = 1", fetch=True)
    if not active_poll:
        await message.answer("Нет активных опросов для завершения.")
        return

    for poll_id, in active_poll:
        execute_query("UPDATE polls SET active = 0 WHERE id = ?", (poll_id,))

    await message.answer("Активные опросы завершены.", reply_markup=create_main_menu(is_admin=True))


# Обработчик нажатий на кнопки голосования
@dp.callback_query(F.data.startswith('vote'))
async def handle_vote(callback_query):
    user_id = callback_query.from_user.id
    _, poll_id, option_id = callback_query.data.split(':')

    option_id = int(option_id)
    poll_id = int(poll_id)

    # Получаем статус опроса
    poll_active = execute_query("SELECT active FROM polls WHERE id = ?", (poll_id,), fetch=True)
    if not poll_active or poll_active[0][0] == 0:
        await callback_query.answer("Опрос завершен.")
        return

    # Запись или удаление голоса в базе данных
    existing_vote = execute_query("SELECT 1 FROM votes WHERE user_id = ? AND poll_id = ? AND option_id = ?",
                                  (user_id, poll_id, option_id), fetch=True)

    if existing_vote:
        execute_query("DELETE FROM votes WHERE user_id = ? AND poll_id = ? AND option_id = ?", (user_id, poll_id,
        option_id))
    else:
        execute_query("INSERT INTO votes (user_id, poll_id, option_id) VALUES (?, ?, ?)", (user_id, poll_id, option_id))

    # Получаем обновленные выбранные варианты для текущего пользователя
    user_votes = execute_query("SELECT option_id FROM votes WHERE user_id = ? AND poll_id = ?", (user_id, poll_id), fetch=True)
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
        SELECT option_text, COUNT(votes.option_id) 
        FROM options
        LEFT JOIN votes ON options.id = votes.option_id
        WHERE options.poll_id = ?
        GROUP BY options.id
    """, (poll_id,), fetch=True)

    result_text = "\n".join([f"{option}: {count} голосов" for option, count in results])
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
        SELECT option_text, COUNT(votes.option_id) 
        FROM options
        LEFT JOIN votes ON options.id = votes.option_id
        WHERE options.poll_id = ?
        GROUP BY options.id
    """, (poll_id,), fetch=True)

    result_text = "\n".join([f"{option}: {count} голосов" for option, count in results])
    result_text = f"Результаты опроса:\nВопрос: {question}\n{result_text}"

    # Обновляем сообщение с результатами
    finish_keyboard = create_finish_keyboard()
    await callback_query.message.edit_text(
        text=result_text,
        reply_markup=finish_keyboard
    )

    await callback_query.answer()

# Запуск бота
async def main():
    init_db()  # Инициализация базы данных
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
