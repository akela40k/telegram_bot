import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
import asyncio
from dotenv import load_dotenv
import os


load_dotenv()
API_TOKEN = os.getenv('API_TOKEN')
DATABASE = 'polls.db'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Подключение к базе данных SQLite
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Создание таблиц для хранения данных
    cursor.execute('''CREATE TABLE IF NOT EXISTS polls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT,
                        active INTEGER DEFAULT 0
                      )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS options (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        poll_id INTEGER,
                        option_text TEXT,
                        FOREIGN KEY (poll_id) REFERENCES polls(id)
                      )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS responses (
                        user_id INTEGER,
                        poll_id INTEGER,
                        option_id INTEGER,
                        PRIMARY KEY (user_id, poll_id, option_id),
                        FOREIGN KEY (poll_id) REFERENCES polls(id),
                        FOREIGN KEY (option_id) REFERENCES options(id)
                      )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS answered_users (
                        user_id INTEGER,
                        poll_id INTEGER,
                        PRIMARY KEY (user_id, poll_id),
                        FOREIGN KEY (poll_id) REFERENCES polls(id)
                      )''')

    conn.commit()
    conn.close()


# Функция для выполнения запросов к базе данных
def execute_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(query, params)

    if fetch:
        result = cursor.fetchall()
    else:
        result = None

    conn.commit()
    conn.close()
    return result


# Функция создания главного меню
def create_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать новый опрос")],
            [KeyboardButton(text="Запустить опрос")],
            [KeyboardButton(text="Показать результаты")]
        ],
        resize_keyboard=True
    )
    return keyboard


# Команда /start - отправляем приветствие и показываем меню
@dp.message(Command('start'))
async def start_command(message: Message):
    await message.answer(
        "Привет! Я бот для проведения опросов. Используй меню для управления опросами.",
        reply_markup=create_main_menu()
    )


# Обработчик нажатий на кнопки меню с использованием лямбда-функции
@dp.message(lambda message: message.text == "Создать новый опрос")
async def create_new_poll(message: Message):
    await message.answer(
        "Чтобы создать новый опрос, используй команду в формате:\n"
        "/create_poll Вопрос? Вариант 1, Вариант 2, Вариант 3"
    )


@dp.message(lambda message: message.text == "Запустить опрос")
async def launch_poll(message: Message):
    poll_data = execute_query("SELECT id, question FROM polls WHERE active = 1", fetch=True)

    if not poll_data:
        await message.answer("Сейчас нет активного опроса. Сначала создайте новый опрос.")
    else:
        await send_poll(message.chat.id)


@dp.message(lambda message: message.text == "Показать результаты")
async def show_poll_results(message: Message):
    poll_data = execute_query("SELECT id, question FROM polls WHERE active = 1", fetch=True)

    if not poll_data:
        await message.answer("Сейчас нет активного опроса.")
    else:
        poll_id = poll_data[0][0]
        question = poll_data[0][1]

        # Подсчет голосов
        options = execute_query("SELECT id, option_text FROM options WHERE poll_id = ?", (poll_id,), fetch=True)
        stats = {option[1]: 0 for option in options}

        responses = execute_query("SELECT option_id FROM responses WHERE poll_id = ?", (poll_id,), fetch=True)
        for response in responses:
            option_id = response[0]
            option_text = execute_query("SELECT option_text FROM options WHERE id = ?", (option_id,), fetch=True)[0][0]
            stats[option_text] += 1

        # Формирование текста с результатами
        stats_text = f"Статистика по опросу: {question}\n\n"
        for option, count in stats.items():
            stats_text += f"{option}: {count} голосов\n"

        await message.answer(stats_text)


# Команда для создания опроса
@dp.message(Command('create_poll'))
async def create_poll_command(message: Message):
    try:
        # Получаем текст после команды
        command_text = message.text.split(' ', 1)[1].strip()

        # Выводим команду для отладки
        print(f"Command text: {command_text}")

        # Проверяем, есть ли в тексте знак вопроса (разделитель между вопросом и вариантами)
        if '?' not in command_text:
            raise ValueError("Не найден знак вопроса '?' в команде.")

        # Разделяем вопрос и варианты ответов
        question, options_text = command_text.split('?', 1)
        question = question.strip() + '?'
        options = [option.strip() for option in options_text.split(',')]

        # Проверяем, что хотя бы два варианта ответа
        if len(options) < 2:
            raise ValueError("Необходимо указать как минимум два варианта ответа.")

        # Деактивируем предыдущие опросы
        execute_query("UPDATE polls SET active = 0 WHERE active = 1")

        # Сохранение нового опроса
        execute_query("INSERT INTO polls (question, active) VALUES (?, 1)", (question,))
        poll_id = execute_query("SELECT last_insert_rowid()", fetch=True)[0][0]

        # Сохранение вариантов ответов
        for option in options:
            execute_query("INSERT INTO options (poll_id, option_text) VALUES (?, ?)", (poll_id, option))

        await message.answer("Опрос создан! Используй кнопку 'Запустить опрос', чтобы начать.",
                             reply_markup=create_main_menu())

    except Exception as e:
        # Выводим информацию об ошибке для отладки
        print(f"Ошибка в create_poll_command: {e}")
        await message.answer(
            f"Произошла ошибка: {e}\nУбедитесь, что команда введена правильно.\nПример: /create_poll Вопрос? Вариант 1, Вариант 2, Вариант 3")


# Функция для создания inline-клавиатуры для опроса
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Функция для создания клавиатуры с вариантами ответов для опроса
def create_poll_keyboard(poll_id):
    # Получаем варианты ответов для данного опроса
    options = execute_query("SELECT id, option_text FROM options WHERE poll_id = ?", (poll_id,), fetch=True)

    # Создаем список для хранения кнопок
    buttons = []
    for option_id, option_text in options:
        # Создаем кнопку для каждого варианта
        buttons.append(InlineKeyboardButton(text=option_text, callback_data=f'vote:{poll_id}:{option_id}'))

    # Создаем и возвращаем клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
    return keyboard


# Функция отправки опроса
async def send_poll(chat_id):
    poll_data = execute_query("SELECT id, question FROM polls WHERE active = 1", fetch=True)

    if poll_data:
        poll_id = poll_data[0][0]
        question = poll_data[0][1]
        keyboard = create_poll_keyboard(poll_id)
        await bot.send_message(chat_id, question, reply_markup=keyboard)


# Обработчик нажатий на inline-кнопки
@dp.callback_query()
async def poll_response_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    poll_data = execute_query("SELECT id FROM polls WHERE active = 1", fetch=True)

    if not poll_data:
        return

    poll_id = poll_data[0][0]

    # Проверяем, ответил ли пользователь уже на этот опрос
    if execute_query("SELECT 1 FROM answered_users WHERE user_id = ? AND poll_id = ?", (user_id, poll_id), fetch=True):
        await callback_query.answer("Вы уже ответили на этот опрос.")
        return

    if callback_query.data == "done":
        responses = execute_query("SELECT option_id FROM responses WHERE user_id = ? AND poll_id = ?",
                                  (user_id, poll_id), fetch=True)
        if not responses:
            await callback_query.answer("Вы не выбрали ни одного варианта.")
        else:
            option_texts = [
                execute_query("SELECT option_text FROM options WHERE id = ?", (response[0],), fetch=True)[0][0] for
                response in responses]
            await callback_query.message.answer(f"Ваши ответы: {', '.join(option_texts)}")

            # Добавляем пользователя в список тех, кто ответил
            execute_query("INSERT INTO answered_users (user_id, poll_id) VALUES (?, ?)", (user_id, poll_id))

        return

    # Сохраняем выбранные пользователем ответы
    option_id = int(callback_query.data)
    if execute_query("SELECT 1 FROM responses WHERE user_id = ? AND poll_id = ? AND option_id = ?",
                     (user_id, poll_id, option_id), fetch=True):
        execute_query("DELETE FROM responses WHERE user_id = ? AND poll_id = ? AND option_id = ?",
                      (user_id, poll_id, option_id))
    else:
        execute_query("INSERT INTO responses (user_id, poll_id, option_id) VALUES (?, ?, ?)", (user_id, poll_id, option_id))


    # Обновляем сообщение с клавиатурой
    await callback_query.message.edit_reply_markup(create_poll_keyboard(poll_id))
async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
