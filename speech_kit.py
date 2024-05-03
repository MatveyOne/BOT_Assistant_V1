import requests
import logging

# Импорт различных констант из модуля config.
from config import IAM_TOKEN, FOLDER_ID, STT_URL, TTS_URL, RECOGNITION_TOPIC, LANGUAGE_CODE, TTS_VOICE, TTS_EMOTION, TTS_FORMAT, LOGS

logging.basicConfig(filename=LOGS, level=logging.DEBUG)

def text_to_speech(text: str) -> (bool, bytes | str):
    # Аутентификация через IAM-токен
    headers = {
        'Authorization': f'Bearer {IAM_TOKEN}',
    }
    data = {
        'text': text,  # текст, который нужно преобразовать в голосовое сообщение
        'lang': LANGUAGE_CODE,  # язык текста - русский
        'voice': TTS_VOICE,
        'folderId': FOLDER_ID,
    }

    # Выполняем запрос
    response = requests.post(f"{TTS_URL}", headers=headers, data=data)

    if response.status_code == 200:  # Проверка успешного запроса
        return True, response.content  # Возвращаем успешный статус и аудио-данные
    else:
        return False, "При запросе в SpeechKit возникла ошибка"  # Возвращаем неуспешный статус и сообщение об ошибке


def speech_to_text(data: bytes) -> (bool, str):
    params = {
        "topic": RECOGNITION_TOPIC,
        "folderId": FOLDER_ID,
        "lang": LANGUAGE_CODE
    }
    headers = {"Authorization": f"Bearer {IAM_TOKEN}"}
    response = requests.post(f"{STT_URL}", headers=headers, params=params, data=data)  # Отправка запроса на распознавание речи
    if response.status_code == 200:  # Проверка успешного запроса
        decoded_data = response.json()  # Декодирование JSON ответа
        if "error_code" not in decoded_data:  # Проверка наличия ошибок
            return True, decoded_data.get("result", "Текст не распознан.")  # Возвращаем успешный статус и распознанный текст
        else:
            return False, f"При запросе в SpeechKit возникла ошибка: {decoded_data.get('error_message', 'Unknown error')}"  # Возвращаем неуспешный статус и сообщение об ошибке
    else:
        return False, f"Ошибка HTTP {response.status_code}: {response.text}"  # Возвращаем неуспешный статус и сообщение об ошибке
