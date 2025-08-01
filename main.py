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

NOTES_TREBLE = {
    "до": {"image_path": "media/treble_nots/treble_do.png", "octave": "первой октавы"},
    "ре": {"image_path": "media/treble_nots/treble_re.png", "octave": "первой октавы"},
    "ми": {"image_path": "media/treble_nots/treble_mi.png", "octave": "первой октавы"},
    "фа": {"image_path": "media/treble_nots/treble_fa.png", "octave": "первой октавы"},
    "соль": {"image_path": "media/treble_nots/treble_sol.png", "octave": "первой октавы"},
    "ля": {"image_path": "media/treble_nots/treble_la.png", "octave": "первой октавы"},
    "си": {"image_path": "media/treble_nots/treble_si.png", "octave": "первой октавы"},
    "до2": {"image_path": "media/treble_nots/treble_do2.png", "octave": "второй октавы"},
    "ре2": {"image_path": "media/treble_nots/treble_re2.png", "octave": "второй октавы"},
    "ми2": {"image_path": "media/treble_nots/treble_mi2.png", "octave": "второй октавы"},
    "фа2": {"image_path": "media/treble_nots/treble_fa2.png", "octave": "второй октавы"},
    "соль2": {"image_path": "media/treble_nots/treble_sol2.png", "octave": "второй октавы"},
}

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


# Клавиатура для ответов
def get_note_quiz_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="До"), KeyboardButton(text="Ре")],
            [KeyboardButton(text="Ми"), KeyboardButton(text="Фа")],
            [KeyboardButton(text="Соль"), KeyboardButton(text="Ля")],
            [KeyboardButton(text="Си"), KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


# Обработчик старта викторины
@dp.message(F.text == "Ноты в скрипичном ключе")
async def start_treble_quiz(message: types.Message):
    user_states[message.from_user.id] = {
        "mode": "treble_quiz",
        "score": 0,
        "total": 0,
        "current_note": None
    }
    await message.answer(
        "🎼 Определите ноты в скрипичном ключе!\n"
        "Я покажу ноту - вы выбираете её название.",
        reply_markup=get_note_quiz_keyboard()
    )
    await send_random_treble_note(message)


# Функция отправки случайной ноты
async def send_random_treble_note(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("mode") != "treble_quiz":
        return

    note_name, note_data = random.choice(list(NOTES_TREBLE.items()))
    user_states[user_id]["current_note"] = note_name

    try:
        with open(note_data["image_path"], 'rb') as photo:
            await message.answer_photo(
                types.BufferedInputFile(photo.read(), filename="note.png"),
                caption="Какая это нота?",
                reply_markup=get_note_quiz_keyboard()
            )
    except Exception as e:
        logging.error(f"Ошибка загрузки ноты: {e}")
        await message.answer(
            f"Нота {note_name} {note_data['octave']}",
            reply_markup=get_note_quiz_keyboard()
        )


# Обработчик ответов
@dp.message(F.text.in_(["До", "Ре", "Ми", "Фа", "Соль", "Ля", "Си"]))
async def check_treble_answer(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})

    if user_state.get("mode") != "treble_quiz":
        return

    current_note = user_state.get("current_note")
    if not current_note:
        await message.answer("Ошибка! Начните викторину заново")
        return

    user_answer = message.text.lower()
    correct_note = current_note.replace("2", "")  # Убираем номер октавы для сравнения

    user_states[user_id]["total"] += 1

    if user_answer == correct_note:
        user_states[user_id]["score"] += 1
        response = f"✅ Правильно! Это нота {correct_note} {NOTES_TREBLE[current_note]['octave']}"
    else:
        response = f"❌ Почти! Это нота {correct_note}\nПопробуем ещё раз!"

    await message.answer(response, reply_markup=get_note_quiz_keyboard())
    await asyncio.sleep(1)
    await send_random_treble_note(message)


# Обновленный обработчик "Назад"
@dp.message(F.text == "Назад")
async def back_from_treble_quiz(message: types.Message):
    user_id = message.from_user.id
    if user_states.get(user_id, {}).get("mode") == "treble_quiz":
        score = user_states[user_id].get("score", 0)
        total = user_states[user_id].get("total", 0)
        await message.answer(
            f"🎉 Викторина завершена!\n"
            f"Ваш результат: {score} из {total}",
            reply_markup=get_music_keyboard()
        )
    user_states[user_id] = {}
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