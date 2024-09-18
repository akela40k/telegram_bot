create .env file with you data

API_TOKEN = 'You token'

ADMIN_IDS = {}  # Список ID администраторов через запятую

GROUP_ID = -1001234567890  # Замените на ID вашей группы или канала

gpt_bot.py storing data in json files

test_sqlite.py storage in sqlite database

bot_sqlite_group.py same as test_sqlite with group functional

Для получения ID группы/канала, можно использовать методы Telegram API. Отправьте сообщение в группе/канале и выполните команду /getUpdates через ваш бот, чтобы получить ID.
