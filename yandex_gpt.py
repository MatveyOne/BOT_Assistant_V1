import requests  # Импорт библиотеки requests для выполнения HTTP-запросов.
import logging  # Импорт модуля logging для ведения журнала логов.
from config import IAM_TOKEN, FOLDER_ID, MAX_GPT_TOKENS, SYSTEM_PROMPT, LOGS, TOKENIZE_COMPLETION_URL, COMPLETION_URL, GPT_TEMPERATURE  # Импорт настроек из файла config.

logging.basicConfig(filename=LOGS, level=logging.ERROR)  # Настройка журналирования для записи ошибок в указанный файл логов.

def count_gpt_tokens(messages):  # Функция для подсчета количества токенов в сообщениях.
    headers = {'Authorization': f'Bearer {IAM_TOKEN}', 'Content-Type': 'application/json'}  # Заголовки для HTTP-запроса.
    data = {'modelUri': f"gpt://{FOLDER_ID}/yandexgpt-lite", "messages": messages}  # Данные для запроса, включая URI модели и сообщения.
    try:
        # Отправка POST-запроса и возвращение количества токенов, полученных из JSON-ответа.
        return len(requests.post(url=TOKENIZE_COMPLETION_URL, json=data, headers=headers).json()['tokens'])
    except Exception as e:  # Обработка исключений.
        logging.error(e)  # Запись ошибки в лог.
        return 0  # Возврат 0 в случае ошибки.

def ask_gpt(messages):  # Функция для запроса к модели GPT.
    headers = {'Authorization': f'Bearer {IAM_TOKEN}', 'Content-Type': 'application/json'}  # Заголовки для HTTP-запроса.
    data = {
        'modelUri': f"gpt://{FOLDER_ID}/yandexgpt-lite",  # URI модели GPT.
        "completionOptions": {"stream": False, "temperature": GPT_TEMPERATURE, "maxTokens": MAX_GPT_TOKENS},  # Опции для генерации ответа.
        "messages": SYSTEM_PROMPT + messages  # Сообщения, начиная с системного подсказа, следующие пользовательские сообщения.
    }
    try:
        response = requests.post(COMPLETION_URL, headers=headers, json=data)  # Отправка POST-запроса к GPT.
        if response.status_code != 200:  # Проверка статуса ответа.
            # Возврат ошибки, если статус код не равен 200.
            return False, f"Ошибка GPT. Статус-код: {response.status_code}", None
        answer = response.json()['result']['alternatives'][0]['message']['text']  # Извлечение текста ответа из JSON.
        tokens_in_answer = count_gpt_tokens([{'role': 'assistant', 'text': answer}])  # Подсчет токенов в ответе.
        return True, answer, tokens_in_answer  # Возврат результата.
    except Exception as e:  # Обработка исключений.
        logging.error(e)  # Запись ошибки в лог.
        return False, "Ошибка при обращении к GPT", None  # Возврат ошибки при возникновении исключения.