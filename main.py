import asyncio
import logging
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputFile
import os
from pathlib import Path
from config import BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Инициализация бота и диспетчера
dp = Dispatcher()
bot = Bot(token=BOT_TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('user.db')
cursor = conn.cursor()

# Получаем абсолютный путь к папке с ботом
BASE_DIR = Path(__file__).parent
MEDIA_DIR = BASE_DIR / "media"

if not MEDIA_DIR.exists():
    MEDIA_DIR.mkdir()
    logging.info(f"Создана папка для медиа: {MEDIA_DIR}")

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS music_progress (
    user_id INTEGER,
    test_type TEXT,
    score INTEGER,
    last_attempt TEXT,
    PRIMARY KEY (user_id, test_type)
);
''')

CLEFS_DATA = {
    "treble": {
        "name": "Скрипичный ключ",
        "description": "Используется для высоких нот",
        "image_path": str(MEDIA_DIR / "treble_clef.png")
    },
    "bass": {
        "name": "Басовый ключ",
        "description": "Используется для низких нот",
        "image_path": str(MEDIA_DIR / "bass_clef.png")
    }
}

conn.commit()

# Хранилища состояний
user_states = {}


# Основные клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 класс"), KeyboardButton(text="2 класс")],
            [KeyboardButton(text="3 класс"), KeyboardButton(text="4 класс")],
            [KeyboardButton(text="5 класс"), KeyboardButton(text="6 класс")],
            [KeyboardButton(text="7 класс")],
            [KeyboardButton(text="Планирование")],
            [KeyboardButton(text="Мои достижения"), KeyboardButton(text="Мой прогресс")]
        ],
        resize_keyboard=True
    )


def get_class_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Расписание")],
            [KeyboardButton(text="Домашние задания")],
            [KeyboardButton(text="Учебные материалы")],
            [KeyboardButton(text="Ноты")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


def get_music_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ключи")],
            [KeyboardButton(text="Ноты в скрипичном ключе")],
            [KeyboardButton(text="Ноты в басовом ключе")],
            [KeyboardButton(text="Клавиатура")],
            [KeyboardButton(text="Обозначение нот")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


def get_clef_quiz_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Скрипичный"), KeyboardButton(text="Басовый")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


# Основные обработчики команд
@dp.message(Command('start'))
async def start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            'INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
            (user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        )
        conn.commit()

    await message.answer(
        "Добро пожаловать в музыкальный бот! Выберите класс:",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command('help'))
async def help_command(message: types.Message):
    await message.answer(
        "Этот бот помогает изучать музыкальную теорию.\n\n"
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - помощь\n\n"
        "Выберите класс для продолжения.",
        reply_markup=get_main_keyboard()
    )


# Обработчики классов
@dp.message(F.text.endswith("класс"))
async def class_handler(message: types.Message):
    class_num = message.text.split(" ")[0]
    user_states[message.from_user.id] = {"current_class": class_num}
    await message.answer(
        f"Выберите раздел для класса {class_num}:",
        reply_markup=get_class_keyboard()
    )


# Обработчики музыкального раздела
@dp.message(F.text == "Ноты")
async def music_menu_handler(message: types.Message):
    await message.answer(
        "Музыкальные задания:",
        reply_markup=get_music_keyboard()
    )


@dp.message(F.text == "Ключи")
async def clefs_intro(message: types.Message):
    # Инициализируем состояние для викторины
    user_states[message.from_user.id] = {
        "mode": "clef_quiz",
        "score": 0,
        "total": 0,
        "current_answer": None  # Добавляем поле сразу
    }

    await message.answer(
        "🎵 Викторина по музыкальным ключам!\n"
        "Определите, какой ключ показан на изображении:",
        reply_markup=get_clef_quiz_keyboard()
    )
    await send_random_clef(message)


async def send_random_clef(message: types.Message):
    user_id = message.from_user.id

    # Проверяем, что пользователь в режиме викторины
    if user_id not in user_states or user_states[user_id].get("mode") != "clef_quiz":
        await message.answer("Пожалуйста, начните викторину через меню")
        return

    clef_type = random.choice(list(CLEFS_DATA.keys()))
    clef = CLEFS_DATA[clef_type]

    # Обновляем текущий правильный ответ
    user_states[user_id]["current_answer"] = clef_type

    try:
        with open(clef["image_path"], 'rb') as photo:
            await message.answer_photo(
                types.BufferedInputFile(photo.read(), filename="clef.png"),
                caption="Это скрипичный или басовый ключ?",
                reply_markup=get_clef_quiz_keyboard()
            )
    except Exception as e:
        logging.error(f"Ошибка отправки изображения: {e}")
        await message.answer(
            f"Изображение: {clef['name']}\n"
            f"Описание: {clef['description']}",
            reply_markup=get_clef_quiz_keyboard()
        )


@dp.message(F.text.in_(["Скрипичный", "Басовый"]))
async def check_clef_answer(message: types.Message):
    user_id = message.from_user.id

    # Проверяем состояние пользователя
    if user_id not in user_states or user_states[user_id].get("mode") != "clef_quiz":
        await message.answer("Пожалуйста, начните викторину сначала")
        return

    # Проверяем наличие текущего ответа
    if "current_answer" not in user_states[user_id]:
        await message.answer("Ошибка: вопрос не загружен. Начинаем заново.")
        await clefs_intro(message)
        return

    user_answer = message.text
    correct_type = user_states[user_id]["current_answer"]
    correct_name = CLEFS_DATA[correct_type]["name"]

    # Обновляем статистику
    user_states[user_id]["total"] += 1

    # Проверяем ответ
    is_correct = (user_answer == "Скрипичный" and correct_type == "treble") or \
                 (user_answer == "Басовый" and correct_type == "bass")

    if is_correct:
        user_states[user_id]["score"] += 1
        response = f"✅ Верно! Это {correct_name}"
    else:
        response = f"❌ Неверно. Это {correct_name}"

    await message.answer(
        f"{response}\n{CLEFS_DATA[correct_type]['description']}",
        reply_markup=get_clef_quiz_keyboard()
    )

    # Отправляем следующий вопрос
    await asyncio.sleep(1)
    await send_random_clef(message)


@dp.message(F.text == "Назад")
@dp.message(F.text == "Назад")
async def back_from_quiz(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_states and user_states[user_id].get("mode") == "clef_quiz":
        score = user_states[user_id].get("score", 0)
        total = user_states[user_id].get("total", 0)
        await message.answer(
            f"🏁 Викторина завершена!\n"
            f"Правильных ответов: {score} из {total}",
            reply_markup=get_music_keyboard()
        )
        user_states[user_id] = {}
    else:
        await message.answer("Выберите раздел:", reply_markup=get_class_keyboard())


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен")
    finally:
        conn.close()