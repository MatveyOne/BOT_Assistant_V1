import telebot
from config import TOKEN, LOGS
from validators import process_and_respond, is_under_user_limit, manage_user_session, is_user_active, check_voice_limits
from speech_kit import speech_to_text, text_to_speech
from database import create_database
import threading
import time


bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])  # Обработчик команды /start
def start(message):  # Определение функции start
    user_id = message.from_user.id  # Получение ID пользователя
    if not is_under_user_limit():  # Проверка, не превышен ли лимит пользователей
        bot.send_message(user_id, "Извините, все операторы заняты. Попробуйте позже.")  # Отправка сообщения о занятости операторов
    else:
        user_first_name = message.from_user.first_name  # Получение имени пользователя
        bot.send_message(user_id, f'Привет, {user_first_name}!Я бот помощник.\n'
                                  f'Задавай мне вопросы голосом или текстом и я отвечу на них.\n'
                                  f'Если тебе не нужен мой ответ, а ты просто хочешь перевести голосовое сообщение в текст или наоборот, то вопспользуйся командами:\n'
                                  f'/stt - голос в текст\n'
                                  f'/tts - текст в голос\n'
                                  f'Если тебе нужен файл с логами, напиши /debug')
        manage_user_session(user_id)

@bot.message_handler(commands=['debug'])  # Обработчик команды /debug
def send_log_file(message):  # Определение функции send_log_file
    user_id = message.from_user.id  # Получение ID пользователя
    try:
        with open(LOGS, 'rb') as log_file:  # Открытие файла журнала
            bot.send_document(user_id, log_file)  # Отправка документа пользователю
    except Exception as e:
        bot.send_message(user_id, f"Ошибка при отправке файла: {e}")  # Отправка сообщения об ошибке при отправке файла

@bot.message_handler(func=lambda message: not is_user_active(message.from_user.id))  # Обработчик неактивных пользователей
def inactive_user(message):  # Определение функции для неактивных пользователей
    bot.send_message(message.from_user.id, "Пожалуйста, воспользуйтесь командой /start для начала работы с ботом.")  # Отправка сообщения о начале работы с ботом

@bot.message_handler(commands=['stt'])  # Обработчик команды /stt
def prompt_voice(message):  # Определение функции prompt_voice
    user_id = message.from_user.id  # Получение ID пользователя
    msg = bot.send_message(user_id, 'Отправьте голосовое сообщение для распознавания.')  # Отправка запроса на отправку голосового сообщения
    bot.register_next_step_handler(msg, handle_stt)  # Регистрация следующего шага обработки сообщения

def handle_stt(message):  # Определение функции handle_stt
    user_id = message.from_user.id  # Получение ID пользователя
    if message.content_type == 'voice':  # Проверка, является ли сообщение голосовым
        file_info = bot.get_file(message.voice.file_id)  # Получение информации о файле
        file = bot.download_file(file_info.file_path)  # Загрузка файла
        status, text = speech_to_text(file)  # Преобразование голоса в текст
        if status:
            bot.send_message(user_id, text)  # Отправка текста пользователю
        else:
            bot.send_message(user_id, "Не удалось распознать текст.")  # Отправка сообщения об ошибке
    else:
        bot.send_message(user_id, "Пожалуйста, отправьте голосовое сообщение.")  # Отправка сообщения с просьбой отправить голосовое сообщение

@bot.message_handler(commands=['tts'])  # Обработчик команды /tts для синтеза речи
def prompt_text(message):  # Определение функции prompt_text
    user_id = message.from_user.id  # Получение ID пользователя
    msg = bot.send_message(user_id, 'Отправьте текст для синтеза речи.')  # Отправка запроса на отправку текста
    bot.register_next_step_handler(msg, handle_tts)  # Регистрация следующего шага обработки сообщения

def handle_tts(message):  # Определение функции handle_tts
    user_id = message.from_user.id  # Получение ID пользователя
    if message.content_type == 'text':  # Проверка, является ли сообщение текстом
        status, audio_content = text_to_speech(message.text)  # Синтез речи из полученного текста
        if status:
            bot.send_voice(user_id, audio_content)  # Отправка синтезированной речи в виде голосового сообщения
        else:
            bot.send_message(user_id, "Ошибка при синтезе речи.")  # Отправка сообщения об ошибке
    else:
        bot.send_message(user_id, "Пожалуйста, отправьте текст.")  # Отправка сообщения с просьбой отправить текст

@bot.message_handler(content_types=['text'])  # Обработчик текстовых сообщений
def handle_text(message):  # Определение функции handle_text
    user_id = message.from_user.id  # Получение ID пользователя
    text = message.text  # Получение текста сообщения
    if is_user_active(user_id):  # Проверка, активен ли пользователь
        process_and_respond(bot, user_id, text, 0)  # Обработка и ответ на текстовое сообщение

@bot.message_handler(content_types=['voice'])  # Обработчик голосовых сообщений
def handle_voice(message):  # Определение функции handle_voice
    user_id = message.from_user.id  # Получение ID пользователя
    if not is_user_active(user_id):  # Проверка, неактивен ли пользователь
        bot.send_message(user_id, "Пожалуйста, воспользуйтесь командой /start для начала работы с ботом.")  # Отправка сообщения с просьбой начать работу с ботом
        return
    duration = message.voice.duration  # Получение длительности голосового сообщения
    success, msg, audio_blocks = check_voice_limits(user_id, duration)  # Проверка лимитов голосовых сообщений
    if not success:
        bot.send_message(user_id, msg)  # Отправка сообщения об ошибке, если лимит превышен
        return
    file_info = bot.get_file(message.voice.file_id)  # Получение информации о голосовом сообщении
    file = bot.download_file(file_info.file_path)  # Загрузка голосового сообщения
    status, text = speech_to_text(file)  # Преобразование голоса в текст
    if status:
        process_and_respond(bot, user_id, text, duration)  # Обработка и ответ на текстовое сообщение
    else:
        bot.send_message(user_id, text)  # Отправка сообщения об ошибке при преобразовании голоса в текст


bot.polling()  # Запуск цикла обработки событий

if __name__ == "__main__":  # Проверка, запущен ли скрипт напрямую
    create_database()  # Инициализация базы данных