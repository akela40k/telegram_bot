create .env file with you data

API_TOKEN = 'You token'

ADMIN_IDS = {}  # Список ID администраторов через запятую

GROUP_ID = -1001234567890  # Замените на ID вашей группы или канала

gpt_bot.py storing data in json files

test_sqlite.py storage in sqlite database

bot_sqlite_group.py same as test_sqlite with group functional

1. Добавление бота в группу или канал
Добавьте бота в группу:

Перейдите в Telegram и откройте вашу группу.
Нажмите на название группы, чтобы открыть настройки.
Выберите "Добавить участника" и найдите вашего бота (по имени пользователя, который вы указали при создании).
Добавьте бота в группу и дайте ему соответствующие права.
Добавьте бота в канал:

Перейдите в Telegram и откройте ваш канал.
Нажмите на название канала, чтобы открыть настройки.
Выберите "Управление каналом" и далее "Добавить участника".
Найдите вашего бота и добавьте его в канал как администратора, чтобы он мог отправлять сообщения.


Для получения ID группы/канала, можно использовать методы Telegram API. Отправьте сообщение в группе/канале и выполните команду /getUpdates через ваш бот, чтобы получить ID.
