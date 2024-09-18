import json
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
DATA_FILE = 'polls_data.json'
RESULTS_FOLDER = 'poll_results'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Загружаем данные опросов из файла, если он существует
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)

with open(DATA_FILE, 'r') as f:
    polls = json.load(f)


# Функция для сохранения данных опросов в файл
def save_polls_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(polls, f)


# Глобальный идентификатор для активного опроса
ACTIVE_POLL_KEY = "active_poll"


# Функция создания главного меню
def create_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton(text="Создать новый опрос"),
        KeyboardButton(text="Запустить опрос"),
        KeyboardButton(text="Показать результаты")
    ]
    keyboard.add(*buttons)
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
    poll_data = polls.get(ACTIVE_POLL_KEY)

    if not poll_data:
        await message.answer("Сейчас нет активного опроса. Сначала создайте новый опрос.")
    else:
        await send_poll(message.chat.id)


@dp.message(lambda message: message.text == "Показать результаты")
async def show_poll_results(message: Message):
    poll_data = polls.get(ACTIVE_POLL_KEY)

    if not poll_data:
        await message.answer("Сейчас нет активного опроса.")
    else:
        # Подсчет голосов
        stats = {option: 0 for option in poll_data['options']}
        for user_responses in poll_data['responses'].values():
            for response in user_responses:
                stats[response] += 1

        # Формирование текста с результатами
        stats_text = f"Статистика по опросу: {poll_data['question']}\n\n"
        for option, count in stats.items():
            stats_text += f"{option}: {count} голосов\n"

        await message.answer(stats_text)


# Команда для создания опроса
@dp.message(Command('create_poll'))
async def create_poll_command(message: Message):
    try:
        command_text = message.text.split(' ', 1)[1]
        question, options = command_text.split('?')
        question = question.strip() + '?'
        options = [option.strip() for option in options.split(',')]

        if len(options) < 2:
            await message.answer("Необходимо указать как минимум два варианта ответа.")
            return

        # Сохранение опроса
        polls[ACTIVE_POLL_KEY] = {
            "question": question,
            "options": options,
            "responses": {},  # Для хранения ответов пользователей
            "answered_users": []  # Список пользователей, которые уже ответили
        }

        # Сохраняем данные в файл
        save_polls_data()

        await message.answer("Опрос создан! Используй кнопку 'Запустить опрос', чтобы начать.",
                             reply_markup=create_main_menu())

    except (IndexError, ValueError):
        await message.answer(
            "Неправильный формат команды. Пример: /create_poll Вопрос? Вариант 1, Вариант 2, Вариант 3")


# Функция для создания inline-клавиатуры для опроса
def create_poll_keyboard():
    keyboard_builder = InlineKeyboardBuilder()
    poll_data = polls.get(ACTIVE_POLL_KEY)

    if poll_data:
        options = poll_data['options']
        for option in options:
            keyboard_builder.add(InlineKeyboardButton(text=option, callback_data=option))

        # Кнопка завершения ответа
        keyboard_builder.add(InlineKeyboardButton(text="Готово", callback_data="done"))

    return keyboard_builder.as_markup()


# Функция отправки опроса
async def send_poll(chat_id):
    poll_data = polls.get(ACTIVE_POLL_KEY)

    if poll_data:
        question = poll_data["question"]
        keyboard = create_poll_keyboard()
        await bot.send_message(chat_id, question, reply_markup=keyboard)


# Обработчик нажатий на inline-кнопки
@dp.callback_query()
async def poll_response_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    poll_data = polls.get(ACTIVE_POLL_KEY)

    if not poll_data:
        return

    # Проверяем, ответил ли пользователь уже на этот опрос
    if user_id in poll_data['answered_users']:
        await callback_query.answer("Вы уже ответили на этот опрос.")
        return

    if callback_query.data == "done":
        # Отправляем результаты выбранных вариантов пользователю
        responses = poll_data['responses'].get(user_id, [])
        if not responses:
            await callback_query.answer("Вы не выбрали ни одного варианта.")
        else:
            await callback_query.message.answer(f"Ваши ответы: {', '.join(responses)}")
            # Добавляем пользователя в список тех, кто ответил
            poll_data['answered_users'].append(user_id)

            # Сохраняем результаты опроса
            save_poll_results(poll_data)

        # Сохраняем данные в файл
        save_polls_data()
        return

    # Сохраняем выбранные пользователем ответы
    if user_id not in poll_data['responses']:
        poll_data['responses'][user_id] = []

    if callback_query.data in poll_data['responses'][user_id]:
        # Если вариант уже выбран, убираем его из списка
        poll_data['responses'][user_id].remove(callback_query.data)
    else:
        # Добавляем выбранный вариант
        poll_data['responses'][user_id].append(callback_query.data)

    # Обновляем сообщение с клавиатурой
    await callback_query.message.edit_reply_markup(create_poll_keyboard())

    # Сохраняем данные в файл
    save_polls_data()


# Функция для сохранения результатов опроса в файл
def save_poll_results(poll_data):
    if not os.path.exists(RESULTS_FOLDER):
        os.makedirs(RESULTS_FOLDER)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    results_filename = os.path.join(RESULTS_FOLDER, f"poll_{timestamp}.json")

    with open(results_filename, 'w') as f:
        json.dump(poll_data, f)


# Функция запуска бота
async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
