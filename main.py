import asyncio
import logging
import sqlite3
import random
import hashlib
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputFile
import os
from pathlib import Path
from config import BOT_TOKEN
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from enum import Enum

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
AUDIO_DIR = MEDIA_DIR / "audio_notes"

if not MEDIA_DIR.exists():
    MEDIA_DIR.mkdir()
    logging.info(f"Создана папка для медиа: {MEDIA_DIR}")

if not AUDIO_DIR.exists():
    AUDIO_DIR.mkdir()
    logging.info(f"Создана папка для аудио: {AUDIO_DIR}")

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

cursor.execute('''
CREATE TABLE IF NOT EXISTS voice_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    song_name TEXT,
    voice_file_id TEXT,
    submission_time TEXT,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
''')
conn.commit()

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


class Scales(Enum):
    C_MAJOR = "до мажор"
    G_MAJOR = "соль мажор"
    D_MAJOR = "ре мажор"
    A_MAJOR = "ля мажор"
    E_MAJOR = "ми мажор"
    B_MAJOR = "си мажор"
    F_MAJOR = "фа мажор"


SCALE_DEGREES = {
    1: "I (тоническая)",
    2: "II (нисходящий вводный)",
    3: "III (медианта)",
    4: "IV (субдоминанта)",
    5: "V (доминанта)",
    6: "VI (субмедианта)",
    7: "VII (восходящий вводный)"
}

STABLE_DEGREES = {
    "до мажор": ["до", "ми", "соль"],
    "соль мажор": ["соль", "си", "ре"],
    "ре мажор": ["ре", "фа", "ля"],
    "ля мажор": ["ля", "до", "ми"],
    "ми мажор": ["ми", "соль", "си"],
    "си мажор": ["си", "ре", "фа"],
    "фа мажор": ["фа", "ля", "до"],
    "ля минор": ["ля", "до", "ми"],
    "ми минор": ["ми", "соль", "си"],
    "си минор": ["си", "ре", "фа"],
    "фа# минор": ["фа", "ля", "до"],
    "до# минор": ["до", "ми", "соль"],
    "соль# минор": ["соль", "си", "ре"],
    "ре минор": ["ре", "фа", "ля"],
    "соль минор": ["соль", "си", "ре"],
    "до минор": ["до", "ми", "соль"],
    "фа минор": ["фа", "ля", "до"]
}

conn.commit()

# Хранилища состояний
user_states = {}


# Добавляем в обработчики команд
@dp.message(F.text == "Устойчивые ступени")
async def stable_degrees_game(message: types.Message):
    user_id = message.from_user.id

    # Получаем список всех возможных тональностей
    all_tonalities = list(STABLE_DEGREES.keys())

    # Если пользователь уже играл, исключаем предыдущую тональность
    previous_tonality = user_states.get(user_id, {}).get("tonality")
    available_tonalities = [t for t in all_tonalities if
                            t != previous_tonality] if previous_tonality else all_tonalities

    # Выбираем случайную тональность из доступных
    tonality = random.choice(available_tonalities)

    # Сохраняем состояние
    user_states[user_id] = {
        "mode": "stable_degrees",
        "tonality": tonality,
        "correct_answers": STABLE_DEGREES[tonality],
        "selected_notes": [],
        "score": user_states.get(user_id, {}).get("score", 0),
        "total": user_states.get(user_id, {}).get("total", 0) + 1
    }

    await message.answer(
        f"🎵 Выберите УСТОЙЧИВЫЕ ступени в тональности {tonality}:\n"
        "(Нажмите 3 ноты, которые считаете правильными)",
        reply_markup=get_stable_degrees_keyboard()
    )


def get_stable_degrees_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="до"), KeyboardButton(text="ре"), KeyboardButton(text="ми")],
            [KeyboardButton(text="фа"), KeyboardButton(text="соль"), KeyboardButton(text="ля")],
            [KeyboardButton(text="си"), KeyboardButton(text="Готово"), KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


@dp.message(F.text.in_(["до", "ре", "ми", "фа", "соль", "ля", "си"]))
async def process_note_selection(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})

    if user_state.get("mode") != "stable_degrees":
        return

    selected_note = message.text.lower()
    selected_notes = user_state.get("selected_notes", [])

    if selected_note in selected_notes:
        # Если нота уже выбрана - убираем её
        selected_notes.remove(selected_note)
        await message.answer(f"Нота {selected_note} убрана из выбора")
    else:
        if len(selected_notes) >= 3:
            await message.answer("Вы уже выбрали 3 ноты. Нажмите 'Готово' для проверки")
            return
        selected_notes.append(selected_note)
        await message.answer(f"Добавлена нота {selected_note}")

    # Обновляем состояние
    user_state["selected_notes"] = selected_notes
    user_states[user_id] = user_state

    # Показываем текущий выбор
    if selected_notes:
        await message.answer(f"Выбрано: {', '.join(selected_notes)}")


@dp.message(F.text == "Готово")
async def check_stable_degrees(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})

    if user_state.get("mode") != "stable_degrees":
        return

    selected_notes = user_state.get("selected_notes", [])
    correct_answers = user_state.get("correct_answers", [])
    tonality = user_state.get("tonality", "")

    if len(selected_notes) != 3:
        await message.answer("Нужно выбрать ровно 3 ноты!")
        return

    # Проверяем ответ
    is_correct = set(selected_notes) == set(correct_answers)

    # Обновляем статистику
    if is_correct:
        user_state["score"] += 1
    user_states[user_id] = user_state

    if is_correct:
        response = (
            "✅ Поздравляю! Вы правильно определили устойчивые ступени!\n"
            f"В тональности {tonality} устойчивые ступени: {', '.join(correct_answers)}\n"
            "Переходим к следующему заданию..."
        )
    else:
        response = (
            "❌ К сожалению, это неверный ответ.\n"
            f"В тональности {tonality} устойчивые ступени: {', '.join(correct_answers)}\n"
            "(Устойчивые ступени - это I, III и V ступени гаммы)\n"
            "Попробуем ещё раз!"
        )

    await message.answer(response)

    # Задержка перед новым вопросом
    await asyncio.sleep(2)

    # Задаем новый вопрос с другой тональностью
    await stable_degrees_game(message)

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
            [KeyboardButton(text="Ноты")],
            [KeyboardButton(text="Строение гаммы")],
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
            [KeyboardButton(text="Ноты на слух")],
            [KeyboardButton(text="Ноты в песнях")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )


def get_first_class_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ноты")],
            [KeyboardButton(text="Строение гаммы")],
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


def get_note_letters_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="C"), KeyboardButton(text="D")],
            [KeyboardButton(text="E"), KeyboardButton(text="F")],
            [KeyboardButton(text="G"), KeyboardButton(text="A")],
            [KeyboardButton(text="B"), KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )

@dp.message(F.text == "Строение гаммы")
async def scale_menu(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ступени в гамме")],
            [KeyboardButton(text="Устойчивые ступени")],
            [KeyboardButton(text="Неустойчивые ступени")],  # Добавляем новую кнопку
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Выберите тип вопросов по гаммам:",
        reply_markup=keyboard
    )


def get_songs_keyboard():
    songs_buttons = [
        [KeyboardButton(text=song_name)] for song_name in SONGS.keys()
    ]
    songs_buttons.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=songs_buttons, resize_keyboard=True)


def get_review_keyboard(submission_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Отлично (5)", callback_data=f"review_{submission_id}_5"),
            InlineKeyboardButton(text="😊 Хорошо (4)", callback_data=f"review_{submission_id}_4"),
        ],
        [
            InlineKeyboardButton(text="🤔 Удовлетворительно (3)", callback_data=f"review_{submission_id}_3"),
            InlineKeyboardButton(text="👎 Надо доработать (2)", callback_data=f"review_{submission_id}_2"),
        ]
    ])


# Словари с данными
NOTES_TREBLE = {
    "до": {"image_path": str(MEDIA_DIR / "treble_nots/treble_do.png"), "octave": "первой октавы"},
    "ре": {"image_path": str(MEDIA_DIR / "treble_nots/treble_re.png"), "octave": "первой октавы"},
    "ми": {"image_path": str(MEDIA_DIR / "treble_nots/treble_mi.png"), "octave": "первой октавы"},
    "фа": {"image_path": str(MEDIA_DIR / "treble_nots/treble_fa.png"), "octave": "первой октавы"},
    "соль": {"image_path": str(MEDIA_DIR / "treble_nots/treble_sol.png"), "octave": "первой октавы"},
    "ля": {"image_path": str(MEDIA_DIR / "treble_nots/treble_la.png"), "octave": "первой октавы"},
    "си": {"image_path": str(MEDIA_DIR / "treble_nots/treble_si.png"), "octave": "первой октавы"},
    "до2": {"image_path": str(MEDIA_DIR / "treble_nots/treble_do2.png"), "octave": "второй октавы"},
    "ре2": {"image_path": str(MEDIA_DIR / "treble_nots/treble_re2.png"), "octave": "второй октавы"},
    "ми2": {"image_path": str(MEDIA_DIR / "treble_nots/treble_mi2.png"), "octave": "второй октавы"},
    "фа2": {"image_path": str(MEDIA_DIR / "treble_nots/treble_fa2.png"), "octave": "второй октавы"},
    "соль2": {"image_path": str(MEDIA_DIR / "treble_nots/treble_sol2.png"), "octave": "второй октавы"},
}

NOTES_BASS = {
    "до_б": {"image_path": str(MEDIA_DIR / "bass_nots/bass_do_big.png"), "octave": "большой октавы"},
    "ре_б": {"image_path": str(MEDIA_DIR / "bass_nots/bass_re_big.png"), "octave": "большой октавы"},
    "ми_б": {"image_path": str(MEDIA_DIR / "bass_nots/bass_mi_big.png"), "octave": "большой октавы"},
    "фа_б": {"image_path": str(MEDIA_DIR / "bass_nots/bass_fa_big.png"), "octave": "большой октавы"},
    "соль_б": {"image_path": str(MEDIA_DIR / "bass_nots/bass_sol_big.png"), "octave": "большой октавы"},
    "ля_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_la_small.png"), "octave": "малой октавы"},
    "си_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_si_small.png"), "octave": "малой октавы"},
    "до_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_do_small.png"), "octave": "малой октавы"},
    "ре_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_re_small.png"), "octave": "малой октавы"},
    "ми_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_mi_small.png"), "octave": "малой октавы"},
    "фа_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_fa_small.png"), "octave": "малой октавы"},
    "соль_м": {"image_path": str(MEDIA_DIR / "bass_nots/bass_sol_small.png"), "octave": "малой октавы"},
    "ля_1": {"image_path": str(MEDIA_DIR / "bass_nots/bass_la_first.png"), "octave": "первой октавы"},
    "си_1": {"image_path": str(MEDIA_DIR / "bass_nots/bass_si_first.png"), "octave": "первой октавы"},
    "до_1": {"image_path": str(MEDIA_DIR / "bass_nots/bass_do_first.png"), "octave": "первой октавы"},
    "ре_1": {"image_path": str(MEDIA_DIR / "bass_nots/bass_re_first.png"), "octave": "первой октавы"},
    "ми_1": {"image_path": str(MEDIA_DIR / "bass_nots/bass_mi_first.png"), "octave": "первой октавы"}
}

KEYBOARD_NOTES = {
    "до": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_do.jpg"), "octave": ""},
    "ре": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_re.jpg"), "octave": ""},
    "ми": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_mi.jpg"), "octave": ""},
    "фа": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_fa.jpg"), "octave": ""},
    "соль": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_sol.jpg"), "octave": ""},
    "ля": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_la.jpg"), "octave": ""},
    "си": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_si.jpg"), "octave": ""},
    "до2": {"image_path": str(MEDIA_DIR / "keyboard/keyboard_do2.jpg"), "octave": ""}
}

NOTE_LETTERS = {
    "C": {"image_path": str(MEDIA_DIR / "note_letters/note_C.png"), "name": "До (C)"},
    "D": {"image_path": str(MEDIA_DIR / "note_letters/note_D.png"), "name": "Ре (D)"},
    "E": {"image_path": str(MEDIA_DIR / "note_letters/note_E.png"), "name": "Ми (E)"},
    "F": {"image_path": str(MEDIA_DIR / "note_letters/note_F.png"), "name": "Фа (F)"},
    "G": {"image_path": str(MEDIA_DIR / "note_letters/note_G.png"), "name": "Соль (G)"},
    "A": {"image_path": str(MEDIA_DIR / "note_letters/note_A.png"), "name": "Ля (A)"},
    "B": {"image_path": str(MEDIA_DIR / "note_letters/note_B.png"), "name": "Си (B)"}
}

AUDIO_NOTES = {
    "до": {"audio_path": str(AUDIO_DIR / "3f27a6.mp3"), "octave": "первой октавы"},
    "ре": {"audio_path": str(AUDIO_DIR / "8b1a99.mp3"), "octave": "первой октавы"},
    "ми": {"audio_path": str(AUDIO_DIR / "e4da3b.mp3"), "octave": "первой октавы"},
    "фа": {"audio_path": str(AUDIO_DIR / "a87ff6.mp3"), "octave": "первой октавы"},
    "соль": {"audio_path": str(AUDIO_DIR / "e4da3c.mp3"), "octave": "первой октавы"},
    "ля": {"audio_path": str(AUDIO_DIR / "8b1a98.mp3"), "octave": "первой октавы"},
    "си": {"audio_path": str(AUDIO_DIR / "3f27a7.mp3"), "octave": "первой октавы"}
}

SONGS = {
    "Во поле береза стояла": {
        "image_path": str(MEDIA_DIR / "songs/berezka.png"),
        "notes": "",
        "level": "1 класс"
    },
    "В лесу родилась ёлочка": {
        "image_path": str(MEDIA_DIR / "songs/elochka.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Жили у бабуси": {
        "image_path": str(MEDIA_DIR / "songs/gusi.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Как под горкой": {
        "image_path": str(MEDIA_DIR / "songs/gora.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Маки": {
        "image_path": str(MEDIA_DIR / "songs/maki.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Савка и Гриша": {
        "image_path": str(MEDIA_DIR / "songs/savka.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Василек": {
        "image_path": str(MEDIA_DIR / "songs/vasilok.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Качи": {
        "image_path": str(MEDIA_DIR / "songs/kachi.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Я гуляю": {
        "image_path": str(MEDIA_DIR / "songs/ya_gulay.png"),
        "notes": "",
        "level": "1 класс"
    },
    "Песенка без слов": {
        "image_path": str(MEDIA_DIR / "songs/bes_slov.png"),
        "notes": "",
        "level": "1 класс"
    },
}

SCALE_NOTES = {
    Scales.C_MAJOR: ["до", "ре", "ми", "фа", "соль", "ля", "си"],
    Scales.G_MAJOR: ["соль", "ля", "си", "до", "ре", "ми", "фа"],
    Scales.D_MAJOR: ["ре", "ми", "фа", "соль", "ля", "си", "до"],
    Scales.A_MAJOR: ["ля", "си", "до", "ре", "ми", "фа", "соль"],
    Scales.E_MAJOR: ["ми", "фа", "соль", "ля", "си", "до", "ре"],
    Scales.B_MAJOR: ["си", "до", "ре", "ми", "фа", "соль", "ля"],
    Scales.F_MAJOR: ["фа", "соль", "ля", "сиb", "до", "ре", "ми"]
}

UNSTABLE_DEGREES = {
    "до мажор": ["ре", "фа", "ля", "си"],
    "соль мажор": ["ля", "до", "ми", "фа"],
    "ре мажор": ["ми", "соль", "си", "до"],
    "ля мажор": ["си", "ре", "фа", "соль"],
    "ми мажор": ["фа", "ля", "до", "ре"],
    "си мажор": ["до", "ми", "соль", "ля"],
    "фа мажор": ["соль", "си", "ре", "ми"],
    "ля минор": ["си", "ре", "фа", "соль"],
    "ми минор": ["фа", "ля", "до", "ре"],
    "си минор": ["до", "ми", "соль", "ля"],
    "фа# минор": ["соль", "си", "ре", "ми"],
    "до# минор": ["ре", "фа", "ля", "си"],
    "соль# минор": ["ля", "до", "ми", "фа"],
    "ре минор": ["ми", "соль", "си", "до"],
    "соль минор": ["ля", "до", "ми", "фа"],
    "до минор": ["ре", "фа", "ля", "си"],
    "фа минор": ["соль", "си", "ре", "ми"]
}

# Добавляем обработчик для неустойчивых ступеней
@dp.message(F.text == "Неустойчивые ступени")
async def unstable_degrees_game(message: types.Message):
    user_id = message.from_user.id

    # Получаем список всех возможных тональностей
    all_tonalities = list(UNSTABLE_DEGREES.keys())

    # Если пользователь уже играл, исключаем предыдущую тональность
    previous_tonality = user_states.get(user_id, {}).get("tonality")
    available_tonalities = [t for t in all_tonalities if
                            t != previous_tonality] if previous_tonality else all_tonalities

    # Выбираем случайную тональность из доступных
    tonality = random.choice(available_tonalities)

    # Сохраняем состояние
    user_states[user_id] = {
        "mode": "unstable_degrees",
        "tonality": tonality,
        "correct_answers": UNSTABLE_DEGREES[tonality],
        "selected_notes": [],
        "score": user_states.get(user_id, {}).get("score", 0),
        "total": user_states.get(user_id, {}).get("total", 0) + 1
    }

    await message.answer(
        f"🎵 Выберите НЕУСТОЙЧИВЫЕ ступени в тональности {tonality}:\n"
        "(Нажмите 4 ноты, которые считаете правильными)",
        reply_markup=get_unstable_degrees_keyboard()
    )

# Клавиатура для неустойчивых ступеней (4 ноты нужно выбрать)
def get_unstable_degrees_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="до"), KeyboardButton(text="ре"), KeyboardButton(text="ми")],
            [KeyboardButton(text="фа"), KeyboardButton(text="соль"), KeyboardButton(text="ля")],
            [KeyboardButton(text="си"), KeyboardButton(text="Готово"), KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )

# Обработчик выбора нот (используем тот же, что и для устойчивых ступеней)
@dp.message(F.text.in_(["до", "ре", "ми", "фа", "соль", "ля", "си"]))
async def process_note_selection(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})

    if user_state.get("mode") not in ["stable_degrees", "unstable_degrees"]:
        return

    selected_note = message.text.lower()
    selected_notes = user_state.get("selected_notes", [])
    max_notes = 3 if user_state.get("mode") == "stable_degrees" else 4  # Для неустойчивых - 4 ноты

    if selected_note in selected_notes:
        # Если нота уже выбрана - убираем её
        selected_notes.remove(selected_note)
        await message.answer(f"Нота {selected_note} убрана из выбора")
    else:
        if len(selected_notes) >= max_notes:
            await message.answer(f"Вы уже выбрали {max_notes} ноты. Нажмите 'Готово' для проверки")
            return
        selected_notes.append(selected_note)
        await message.answer(f"Добавлена нота {selected_note}")

    # Обновляем состояние
    user_state["selected_notes"] = selected_notes
    user_states[user_id] = user_state

    # Показываем текущий выбор
    if selected_notes:
        await message.answer(f"Выбрано: {', '.join(selected_notes)}")

# Обработчик проверки ответа для неустойчивых ступеней
@dp.message(F.text == "Готово")
async def check_unstable_degrees(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})

    if user_state.get("mode") != "unstable_degrees":
        return

    selected_notes = user_state.get("selected_notes", [])
    correct_answers = user_state.get("correct_answers", [])
    tonality = user_state.get("tonality", "")

    if len(selected_notes) != 4:
        await message.answer("Нужно выбрать ровно 4 ноты!")
        return

    # Проверяем, что все выбранные ноты есть в correct_answers
    is_correct = all(note in correct_answers for note in selected_notes) and \
                 len(selected_notes) == len(correct_answers)

    # Обновляем статистику
    if is_correct:
        user_state["score"] += 1
        response = (
            "✅ Верно! Неустойчивые ступени в тональности "
            f"{tonality}: {', '.join(correct_answers)}\n"
            "(II, IV, VI и VII ступени)"
        )
    else:
        # Показываем конкретные ошибки
        wrong_notes = [n for n in selected_notes if n not in correct_answers]
        missing_notes = [n for n in correct_answers if n not in selected_notes]

        feedback = []
        if wrong_notes:
            feedback.append(f"Неправильно: {', '.join(wrong_notes)}")
        if missing_notes:
            feedback.append(f"Пропущено: {', '.join(missing_notes)}")

        response = (
            "❌ Есть ошибки:\n"
            f"{'; '.join(feedback)}\n\n"
            f"Правильный ответ: {', '.join(correct_answers)}\n"
            "(Неустойчивые ступени - это II, IV, VI и VII ступени гаммы)"
        )

    user_states[user_id] = user_state
    await message.answer(response)
    await asyncio.sleep(2)
    await unstable_degrees_game(message)  # Новый вопрос

def rename_audio_files():
    audio_mapping = {
        "do.mp3": "3f27a6.mp3",
        "re.mp3": "8b1a99.mp3",
        "mi.mp3": "e4da3b.mp3",
        "fa.mp3": "a87ff6.mp3",
        "sol.mp3": "e4da3c.mp3",
        "la.mp3": "8b1a98.mp3",
        "si.mp3": "3f27a7.mp3"
    }

    for original, new_name in audio_mapping.items():
        original_path = AUDIO_DIR / original
        if original_path.exists():
            original_path.rename(AUDIO_DIR / new_name)
            logging.info(f"Переименован {original} в {new_name}")


# Проверяем и переименовываем файлы при старте
if AUDIO_DIR.exists():
    rename_audio_files()
else:
    logging.warning(f"Папка с аудио не найдена: {AUDIO_DIR}")


# Обработчики команд
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

    if class_num == "1":
        await message.answer(
            f"Выберите раздел для 1 класса:",
            reply_markup=get_first_class_keyboard()
        )
    else:
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
    user_states[message.from_user.id] = {
        "mode": "clef_quiz",
        "score": 0,
        "total": 0,
        "current_answer": None
    }

    await message.answer(
        "🎵 Викторина по музыкальным ключам!\n"
        "Определите, какой ключ показан на изображении:",
        reply_markup=get_clef_quiz_keyboard()
    )
    await send_random_clef(message)


async def send_random_clef(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("mode") != "clef_quiz":
        await message.answer("Пожалуйста, начните викторину через меню")
        return

    clef_type = random.choice(list(CLEFS_DATA.keys()))
    clef = CLEFS_DATA[clef_type]
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
    if user_id not in user_states or user_states[user_id].get("mode") != "clef_quiz":
        await message.answer("Пожалуйста, начните викторину сначала")
        return

    if "current_answer" not in user_states[user_id]:
        await message.answer("Ошибка: вопрос не загружен. Начинаем заново.")
        await clefs_intro(message)
        return

    user_answer = message.text
    correct_type = user_states[user_id]["current_answer"]
    correct_name = CLEFS_DATA[correct_type]["name"]

    user_states[user_id]["total"] += 1
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
    await asyncio.sleep(1)
    await send_random_clef(message)


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


@dp.message(F.text == "Ноты в басовом ключе")
async def start_bass_quiz(message: types.Message):
    user_states[message.from_user.id] = {
        "mode": "bass_quiz",
        "score": 0,
        "total": 0,
        "current_note": None
    }
    await message.answer(
        "🎵 Определите ноты в басовом ключе!\n"
        "Я покажу ноту - вы выбираете её название.",
        reply_markup=get_note_quiz_keyboard()
    )
    await send_random_bass_note(message)


async def send_random_bass_note(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("mode") != "bass_quiz":
        return

    note_name, note_data = random.choice(list(NOTES_BASS.items()))
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


@dp.message(F.text == "Клавиатура")
async def start_keyboard_quiz(message: types.Message):
    user_states[message.from_user.id] = {
        "mode": "keyboard_quiz",
        "score": 0,
        "total": 0,
        "current_note": None
    }
    await message.answer(
        "🎹 Викторина по клавиатуре!\n"
        "Я покажу клавишу - вы определяете её ноту.",
        reply_markup=get_note_quiz_keyboard()
    )
    await send_random_keyboard_note(message)


async def send_random_keyboard_note(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("mode") != "keyboard_quiz":
        return

    note_name, note_data = random.choice(list(KEYBOARD_NOTES.items()))
    user_states[user_id]["current_note"] = note_name

    try:
        with open(note_data["image_path"], 'rb') as photo:
            await message.answer_photo(
                types.BufferedInputFile(photo.read(), filename="keyboard.png"),
                caption="Какая это нота?",
                reply_markup=get_note_quiz_keyboard()
            )
    except Exception as e:
        logging.error(f"Ошибка загрузки изображения клавиатуры: {e}")
        await message.answer(
            "Изображение клавиши не загружено",
            reply_markup=get_note_quiz_keyboard()
        )


@dp.message(F.text == "Обозначение нот")
async def start_note_letters_quiz(message: types.Message):
    user_states[message.from_user.id] = {
        "mode": "note_letters_quiz",
        "score": 0,
        "total": 0,
        "current_note": None
    }
    await message.answer(
        "🔤 Викторина по буквенным обозначениям нот!\n"
        "Я покажу ноту - вы определяете её буквенное обозначение.",
        reply_markup=get_note_letters_keyboard()
    )
    await send_random_note_letter(message)


async def send_random_note_letter(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("mode") != "note_letters_quiz":
        return

    note_letter, note_data = random.choice(list(NOTE_LETTERS.items()))
    user_states[user_id]["current_note"] = note_letter

    try:
        with open(note_data["image_path"], 'rb') as photo:
            await message.answer_photo(
                types.BufferedInputFile(photo.read(), filename="note_letter.png"),
                caption="Какое буквенное обозначение этой ноты?",
                reply_markup=get_note_letters_keyboard()
            )
    except Exception as e:
        logging.error(f"Ошибка загрузки изображения ноты: {e}")
        await message.answer(
            f"Нота: {note_data['name']}",
            reply_markup=get_note_letters_keyboard()
        )


@dp.message(F.text == "Ноты на слух")
async def start_audio_notes_quiz(message: types.Message):
    user_states[message.from_user.id] = {
        "mode": "audio_notes_quiz",
        "score": 0,
        "total": 0,
        "current_note": None
    }
    await message.answer(
        "🎵 Викторина по нотам на слух!\n"
        "Я сыграю ноту - вы определяете её название.",
        reply_markup=get_note_quiz_keyboard()
    )
    await send_random_audio_note(message)


async def send_random_audio_note(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("mode") != "audio_notes_quiz":
        return

    note_name, note_data = random.choice(list(AUDIO_NOTES.items()))
    user_states[user_id]["current_note"] = note_name

    try:
        audio = types.FSInputFile(note_data["audio_path"])
        await message.answer_audio(
            audio,
            reply_markup=get_note_quiz_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка загрузки аудио: {e}")
        await message.answer(
            "Не удалось загрузить аудио, попробуйте еще раз",
            reply_markup=get_note_quiz_keyboard()
        )


@dp.message(F.text == "Ступени в гамме")
async def scale_structure(message: types.Message):
    user_id = message.from_user.id

    # Инициализируем состояние только если его нет или это новый запуск
    if user_id not in user_states or user_states[user_id].get("mode") != "scale_quiz":
        user_states[user_id] = {
            "mode": "scale_quiz",
            "score": 0,
            "total": 0
        }

    # Выбираем случайную гамму и ступень
    scale_name = random.choice(list(Scales)).value
    scale = Scales(scale_name)
    degree_num = random.randint(1, 7)
    degree = ["I", "II", "III", "IV", "V", "VI", "VII"][degree_num - 1]
    correct_note = SCALE_NOTES[scale][degree_num - 1]

    # Обновляем текущий вопрос в состоянии
    user_states[user_id].update({
        "current_scale": scale_name,
        "current_degree": degree,
        "current_answer": correct_note
    })

    # Формируем вопрос
    degree_names = {
        "I": "тоническую (I)",
        "II": "нисходящий вводный (II)",
        "III": "медианту (III)",
        "IV": "субдоминанту (IV)",
        "V": "доминанту (V)",
        "VI": "субмедианту (VI)",
        "VII": "восходящий вводный (VII)"
    }

    question = f"🎼 Назовите ноту для {degree_names[degree]} ступени в гамме {scale_name}:"

    await message.answer(
        question,
        reply_markup=get_note_quiz_keyboard()
    )
@dp.message(F.text == "Устойчивые ступени")
async def stable_degrees(message: types.Message):
    await message.answer(
        "Функция для устойчивых ступеней будет реализована позже",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Ступени в гамме")],
                [KeyboardButton(text="Назад")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(F.text.in_(["До", "Ре", "Ми", "Фа", "Соль", "Ля", "Си"]))
async def check_note_answer(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    mode = user_state.get("mode")

    if not mode:
        await message.answer("Пожалуйста, начните викторину через меню")
        return

    # Обработка викторины по ступеням гаммы
    if mode == "scale_quiz":
        degree = user_state.get("current_degree")
        correct_note = user_state.get("current_answer")
        scale_name = user_state.get("current_scale")

        if None in [degree, correct_note, scale_name]:
            await message.answer("Ошибка! Начните викторину заново")
            return

        user_answer = message.text.lower()
        user_state["total"] += 1

        if user_answer == correct_note:
            user_state["score"] += 1
            response = f"✅ Верно! {degree} ступень в гамме {scale_name} - это {correct_note}"
        else:
            response = f"❌ Неверно! {degree} ступень в гамме {scale_name} - это {correct_note}"

        await message.answer(response)

        # Задаем новый вопрос, не сбрасывая состояние
        await scale_structure(message)
        return

    # Обработка других викторин (как было ранее)
    current_note = user_state.get("current_note")
    if not current_note:
        await message.answer("Ошибка! Начните викторину заново")
        return

    # Определяем правильный ответ в зависимости от режима
    if mode == "treble_quiz":
        correct_note = current_note.replace("2", "")
        octave_info = NOTES_TREBLE[current_note]["octave"]
    elif mode == "bass_quiz":
        correct_note = current_note.split("_")[0]
        octave_info = NOTES_BASS[current_note]["octave"]
    elif mode == "keyboard_quiz":
        correct_note = current_note.replace("2", "")
        octave_info = ""
    elif mode == "audio_notes_quiz":
        correct_note = current_note
        octave_info = AUDIO_NOTES[current_note]["octave"]
    elif mode == "note_letters_quiz":
        correct_note = current_note
        note_name = NOTE_LETTERS[correct_note]["name"]
    else:
        await message.answer("Неизвестный режим викторины")
        return

    user_answer = message.text.lower()
    user_state["total"] += 1

    if mode == "note_letters_quiz":
        if user_answer == correct_note.lower():
            user_state["score"] += 1
            response = f"✅ Верно! Это нота {note_name}"
        else:
            response = f"❌ Неверно! Это нота {note_name}"
    else:
        if user_answer == correct_note:
            user_state["score"] += 1
            response = f"✅ Верно! Это нота {correct_note}"
            if octave_info:
                response += f" {octave_info}"
        else:
            response = f"❌ Неверно! Это нота {correct_note}"
            if octave_info:
                response += f" {octave_info}"

    await message.answer(response,
                         reply_markup=get_note_quiz_keyboard() if mode != "note_letters_quiz" else get_note_letters_keyboard())
    await asyncio.sleep(1)

    # Отправляем следующий вопрос в зависимости от режима
    if mode == "treble_quiz":
        await send_random_treble_note(message)
    elif mode == "bass_quiz":
        await send_random_bass_note(message)
    elif mode == "keyboard_quiz":
        await send_random_keyboard_note(message)
    elif mode == "audio_notes_quiz":
        await send_random_audio_note(message)
    elif mode == "note_letters_quiz":
        await send_random_note_letter(message)


@dp.message(F.text.in_(["C", "D", "E", "F", "G", "A", "B"]))
async def check_note_letter_answer(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    mode = user_state.get("mode")

    if mode != "note_letters_quiz":
        return

    current_note = user_state.get("current_note")
    if not current_note:
        await message.answer("Ошибка! Начните викторину заново")
        return

    user_answer = message.text
    correct_note = current_note
    note_name = NOTE_LETTERS[correct_note]["name"]

    user_states[user_id]["total"] += 1

    if user_answer == correct_note:
        user_states[user_id]["score"] += 1
        response = f"✅ Верно! Это нота {note_name}"
    else:
        response = f"❌ Неверно! Это нота {note_name}"

    await message.answer(response, reply_markup=get_note_letters_keyboard())
    await asyncio.sleep(1)
    await send_random_note_letter(message)


@dp.message(F.text == "Ноты в песнях")
async def songs_menu(message: types.Message):
    await message.answer(
        "🎶 Выбери песню и спой её по нотам!",
        reply_markup=get_songs_keyboard()
    )


@dp.message(F.text.in_(SONGS.keys()))
async def send_song_notes(message: types.Message):
    song_name = message.text
    song_data = SONGS[song_name]

    try:
        with open(song_data["image_path"], 'rb') as photo:
            await message.answer_photo(
                types.BufferedInputFile(photo.read(), filename="song.png"),
                caption=f"🎵 {song_name}\n"
                        f"Ноты: {song_data['notes']}\n\n"
                        f"Спой эту мелодию и отправь голосовое сообщение!",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Отмена")]],
                    resize_keyboard=True
                )
            )
        # Сохраняем текущую песню в состоянии пользователя
        user_states[message.from_user.id] = {
            "mode": "song_recording",
            "song_name": song_name
        }
    except Exception as e:
        await message.answer("Ошибка загрузки нот. Попробуйте позже.")
        logging.error(f"Ошибка загрузки песни: {e}")


@dp.message(F.voice)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})

    if user_state.get("mode") != "song_recording":
        return

    song_name = user_state.get("song_name")
    voice_file_id = message.voice.file_id

    try:
        # Сохраняем голосовое в базу
        cursor.execute(
            '''INSERT INTO voice_notes 
            (user_id, username, first_name, last_name, song_name, voice_file_id, submission_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name,
                song_name,
                voice_file_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
        submission_id = cursor.lastrowid

        # Отправляем подтверждение ученику
        await message.answer(
            "✅ Твоё голосовое отправлено учителю на проверку!\n"
            "Скоро получишь обратную связь.",
            reply_markup=get_music_keyboard()
        )

        # Отправляем голосовое учителю
        try:
            # Вариант 1: Пересылка голосового сообщения
            await bot.send_voice(
                chat_id=5157087391,  # Замените на ваш реальный ID
                voice=voice_file_id,
                caption=f"🎵 Новое задание (#{submission_id}) от @{message.from_user.username}:\n"
                        f"Песня: {song_name}\n"
                        f"Ученик: {message.from_user.full_name}\n"
                        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=get_review_keyboard(submission_id)
            )
        except Exception as e:
            logging.error(f"Ошибка отправки голосового учителю: {e}", exc_info=True)
            # Вариант 2: Отправка информации без голосового, если не получается
            await bot.send_message(
                chat_id=5157087391,
                text=f"🎵 Новое задание (#{submission_id}) от @{message.from_user.username}:\n"
                     f"Песня: {song_name}\nУченик: {message.from_user.full_name}\n"
                     f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"Голосовое сообщение: {voice_file_id}",
                reply_markup=get_review_keyboard(submission_id)
            )

    except Exception as e:
        logging.error(f"Ошибка при обработке голосового сообщения: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте позже.",
            reply_markup=get_music_keyboard()
        )

    # Сбрасываем состояние пользователя
    user_states[user_id] = {}


@dp.callback_query(F.data.startswith("review_"))
async def process_review(callback: types.CallbackQuery):
    _, submission_id, grade = callback.data.split('_')

    # Обновляем статус в базе
    cursor.execute(
        "UPDATE voice_notes SET status = ? WHERE id = ?",
        (f"Оценено: {grade}", submission_id)
    )
    conn.commit()

    # Получаем данные об ученике
    cursor.execute(
        "SELECT user_id, song_name FROM voice_notes WHERE id = ?",
        (submission_id,)
    )
    user_id, song_name = cursor.fetchone()

    # Отправляем уведомление ученику
    feedback = {
        '5': "🎉 Отлично! 5 баллов!",
        '4': "😊 Хорошо! 4 балла!",
        '3': "🤔 Удовлетворительно. 3 балла.",
        '2': "👎 Нужно доработать. 2 балла."
    }.get(grade, "Ваша работа оценена.")

    await bot.send_message(
        chat_id=user_id,
        text=f"Ваша работа по песне '{song_name}':\n{feedback}"
    )

    # Убираем кнопки у учителя
    await callback.answer("Оценка сохранена")
    await callback.message.edit_reply_markup()


@dp.message(F.text == "Назад")
async def back_handler(message: types.Message):
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    mode = user_state.get("mode", "")
    current_class = user_state.get("current_class", "")

    # Обработка выхода из режимов викторин
    if mode in ["scale_quiz", "treble_quiz", "bass_quiz",
                "keyboard_quiz", "note_letters_quiz", "audio_notes_quiz",
                "clef_quiz", "stable_degrees"]:

        score = user_state.get("score", 0)
        total = user_state.get("total", 0)

        quiz_names = {
            "scale_quiz": "по ступеням гаммы",
            "treble_quiz": "по нотам в скрипичном ключе",
            "bass_quiz": "по нотам в басовом ключе",
            "keyboard_quiz": "по клавиатуре",
            "note_letters_quiz": "по буквенным обозначениям нот",
            "audio_notes_quiz": "по нотам на слух",
            "clef_quiz": "по музыкальным ключам",
            "stable_degrees": "на устойчивые ступени"
        }

        # Формируем сообщение о результатах
        result_message = (
            f"🏁 Викторина {quiz_names.get(mode, '')} завершена!\n"
            f"Правильных ответов: {score} из {total}"
        )

        # Для режима устойчивых ступеней добавляем пояснение
        if mode == "stable_degrees":
            result_message += (
                "\n\nЗапомни: устойчивые ступени - это I, III и V ступени гаммы"
            )

        await message.answer(
            result_message,
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Ступени в гамме")],
                    [KeyboardButton(text="Устойчивые ступени")],
                    [KeyboardButton(text="Назад")]
                ],
                resize_keyboard=True
            )
        )

        # Сбрасываем состояние викторины, но сохраняем класс
        user_state["mode"] = f"class_{current_class}" if current_class else ""
        return

    # Возврат в меню класса
    if mode.startswith("class_"):
        class_num = mode.split("_")[1]
        await message.answer(
            f"Выберите раздел для {class_num} класса:",
            reply_markup=get_class_keyboard()
        )
        user_state["mode"] = ""
        return

    # Возврат в главное меню из любого другого места
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )
    user_state["mode"] = ""


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен")
    finally:
        conn.close()