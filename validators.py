from database import select_n_last_messages, add_message, count_all_blocks, count_all_limits
from config import MAX_USER_STT_BLOCKS, MAX_USER_GPT_TOKENS, MAX_USER_TTS_SYMBOLS, MAX_TIME_VOICE, MAX_USERS, TIME_NOT_ACTIVE
from yandex_gpt import ask_gpt
from speech_kit import text_to_speech
import time
from threading import Lock

active_sessions = {}  # Словарь для отслеживания активных сессий пользователей
session_lock = Lock()  # Создание объекта блокировки для безопасного доступа к активным сессиям

def manage_user_session(user_id):
    with session_lock:  # Использование блокировки для безопасного доступа к активным сессиям
        current_time = time.time()  # Получение текущего времени
        active_sessions[user_id] = current_time  # Обновление времени активной сессии для данного пользователя
        # Очистка неактивных сессий
        for user in list(active_sessions):  # Итерация по копии списка активных сессий
            if current_time - active_sessions[user] > TIME_NOT_ACTIVE:  # Проверка времени неактивности пользователя
                del active_sessions[user]  # Удаление неактивной сессии из словаря

def is_under_user_limit():
    manage_user_session(None)  # Обновление активных сессий без добавления новой
    return len(active_sessions) < MAX_USERS  # Проверка, не превышен ли лимит активных пользователей

def is_user_active(user_id):
    manage_user_session(None)  # Обновление активных сессий
    return user_id in active_sessions  # Проверка, активен ли пользователь

def process_message(text, user_id, context):
    if count_all_limits(user_id, 'total_gpt_tokens') + len(text) > MAX_USER_GPT_TOKENS:
        # Если превышен лимит токенов
        return "Превышен лимит токенов GPT. Для продолжения работы докупите токены.", None
    try:
        # Запрос к GPT и другая логика
        response, tokens_used = ask_gpt([{'role': 'user', 'text': text}])  # Предполагаемая функция запроса к GPT
        if response:
            return response, tokens_used
        else:
            return "Ошибка при обращении к GPT.", None
    except Exception as e:
        return f"Произошла внутренняя ошибка: {str(e)}", None
def check_voice_limits(user_id, duration):
    current_blocks = (duration // 15) + (1 if duration % 15 > 0 else 0)  # Вычисление текущего количества аудиоблоков
    total_blocks = count_all_blocks(user_id) + current_blocks  # Вычисление общего количества аудиоблоков
    if total_blocks > MAX_USER_STT_BLOCKS:  # Проверка лимита аудиоблоков
        return False, 'Превышен лимит аудиоблоков.', current_blocks  # Возврат сообщения об ошибке, если превышен лимит
    return True, None, current_blocks  # Возврат успеха без сообщения об ошибке, если лимит не превышен


def process_and_respond(bot, user_id, text, duration):
    manage_user_session(user_id)  # Обновляет информацию о последней активности пользователя, чтобы сессия считалась активной.

    messages, _ = select_n_last_messages(user_id,5)  # Получает последние 5 сообщений пользователя для формирования контекста общения.
    context = [m['text'] for m in messages] + [text]  # Создает список всех сообщений включая текущее, для контекста обработки GPT.

    # Перед обработкой сообщения проверяет, не превышен ли лимит токенов GPT для пользователя.
    if count_all_limits(user_id, 'total_gpt_tokens') + len(text) > MAX_USER_GPT_TOKENS:
        bot.send_message(user_id, "Превышен лимит токенов GPT. Для продолжения работы докупите токены.")
        return  # Завершает функцию, если лимит токенов превышен.

    response, tokens_used = process_message(text, user_id, context)  # Обрабатывает входящее сообщение и получает ответ от GPT.

    if response is None or tokens_used is None:  # Проверяет, вернул ли GPT корректный ответ и информацию о использованных токенах.
        response = "Произошла ошибка, попробуйте ещё раз."  # Устанавливает сообщение об ошибке, если ответ от GPT не был получен.
        tokens_used = 0  # Задает количество использованных токенов как 0 для избежания ошибки при сложении.

    # Обрезает ответ до максимально допустимого количества символов для синтеза речи.
    response_trimmed = response[:MAX_USER_TTS_SYMBOLS] if len(response) > MAX_USER_TTS_SYMBOLS else response
    tts_symbols_count = len(response_trimmed)  # Считает количество символов в обрезанном ответе.

    success, msg, audio_blocks = check_voice_limits(user_id, duration)  # Проверяет, не превышены ли лимиты на длительность голосовых сообщений.
    if not success:  # Если лимиты превышены,
        bot.send_message(user_id, msg)  # Отправляет сообщение об ошибке.
        return  # Завершает функцию.

    total_gpt_tokens = count_all_limits(user_id,'total_gpt_tokens') + tokens_used  # Обновляет общее количество использованных GPT токенов.

    # Сохраняет информацию о пользовательском сообщении в базе данных.
    add_message(user_id, text, 'user', 0, 0, audio_blocks if duration > 0 else 0)
    # Сохраняет ответ бота в базе данных, учитывая новое общее количество токенов и символов для TTS.
    add_message(user_id, response_trimmed, 'bot', total_gpt_tokens, tts_symbols_count, 0)

    if duration > 0:  # Если сообщение содержало голосовую запись,
        voice_status, voice_message = text_to_speech(response_trimmed)  # Преобразует текст в голосовое сообщение.
        if voice_status:  # Если преобразование прошло успешно,
            bot.send_voice(user_id, voice_message)  # Отправляет голосовое сообщение пользователю.
        else:
            bot.send_message(user_id,"Ошибка при генерации голосового сообщения.")  # Отправляет сообщение об ошибке при синтезе.
    else:
        bot.send_message(user_id, response_trimmed)  # Отправляет текстовое сообщение пользователю, если не было голосового.
