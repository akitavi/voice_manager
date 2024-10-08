#Модуль для записи и воспроизведения звука
import sounddevice as sd
import queue
import re
import soundfile as sf  # For playing sound
import logging
import os
import sys
import json
import requests  # For sending REST API requests
from vosk import Model, KaldiRecognizer

# Configure logging
log_directory = "logs"
log_file = os.path.join(log_directory, "homai_voice.log")
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO in production
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Вывод логов в консоль
        logging.FileHandler(log_file, mode='a')  # Запись логов в файл
    ]
)

q = queue.Queue()

def callback(indata, frames, time_info, status):
    if status:
        logging.warning(f"Audio stream status: {status}")
    q.put(bytes(indata))

# Verify Vosk model path
model_path = "/home/alex/learn/voise_py/model"
if not os.path.exists(model_path):
    logging.error(f"Vosk model not found at {model_path}")
    sys.exit(1)

model = Model(model_path)
rec = KaldiRecognizer(model, 16000)

activation_detected = False  # Flag to prevent multiple activations

pops_sound = "/home/alex/homeAI/voise_py/sounds/pops.mp3"

def play_alert_sound(file_path=pops_sound):
    try:
        # Чтение аудиофайла
        data, sample_rate = sf.read(file_path)  # Используем file_path, переданный в функцию
        # Воспроизведение аудиофайла через sounddevice
        sd.play(data, samplerate=sample_rate)
        sd.wait()  # Ожидание завершения воспроизведения
        logging.info("Звуковой сигнал воспроизведён")
    except Exception as e:
        logging.error(f"Ошибка при воспроизведении звука: {e}")

# Dictionary of programs and commands with synonyms
programs = {
    ('браузер', 'брауер', 'chrome'): {
        'start': ('Google Chrome', '/usr/bin/google-chrome'),
        'stop': 'chrome'
    },
    ('музыка', 'музыку', 'yandex'): {
        'start': ('Музыка', None), 
        'stop': 'music'
    },
    ('редактор', 'саблайм', 'sublime', 'текстовый'): {
        'start': ('Текстовый редактор', '/usr/bin/subl'),
        'stop': 'subl'
    },
    ('терминал', 'консоль', 'terminator'): {
        'start': ('Терминал', '/usr/bin/terminator'),
        'stop': 'terminator'
    },
    ('стим', 'steam'): {
        'start': ('Steam', '/usr/bin/steam'),
        'stop': 'steam'
    },
    ('дота', 'доту', 'dota', 'дотан', 'дотанчик', 'дотку', 'дотка'): {
        'start': ('Dota2', 'steam steam://rungameid/570'),
        'stop': 'dota2'
    },
    ('ноут', 'ноутбук', 'комп', 'компьютер', 'shutdown', 'poweroff'): {
        'stop': 'poweroff'
    }
}

# Activation words and compiled patterns
activation_words = ["лили", "лилли", "лелли", "лилие", "лилия", "лиля", "лия", "лилль"]
activation_pattern = re.compile(
    r"(?:\b(" + "|".join([re.escape(word) for word in activation_words]) + r")\b)|(^или\b)"
)
activation_removal_pattern = re.compile(
    r"\b(" + "|".join([re.escape(word) for word in activation_words]) + r")\b|^или\b"
)


start_pattern = re.compile(r"(включ[иы]|запуст[иы]|откр[оа]й|покаж[иы]|откр[юу]|открыть|включить)")
stop_pattern = re.compile(r"(выключ[иы]|закрыть|закр[оа]й|останов[иы]|прекрат[иы]|выключить)")
music_play_pattern = re.compile(r"(включ[иыть] музы[ку]|нач[ао]ть воспроизвед[её]ние)")
music_pause_pattern = re.compile(r"(пауз[ау]|продолж(и|ил|ить|ать|им|ишь|ит|им|ите|ат))")
music_next_pattern = re.compile(r"(следующ(ий|ие|ее|ей))")
music_volume_pattern = re.compile(r"громкость\s*(\d+)")



def send_command(command_type, command_name, parameters):
    url = 'http://localhost:5000/execute'  # URL вашего Flask-сервера
    payload = {
        'command_type': command_type,
        'command_name': command_name,
        'parameters': parameters
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info(f"Команда отправлена успешно: {response.json()}")
        else:
            logging.error(f"Ошибка при отправке команды: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке команды: {e}")

number_words_to_digits = {
    'ноль': 0, 'один': 1, 'два': 2, 'три': 3, 'четыре': 4, 
    'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10
}

def replace_number_words_with_digits(text):
    for word, digit in number_words_to_digits.items():
        text = re.sub(rf"\b{word}\b", str(digit), text)
    return text


def process_command(text):
    global activation_detected
    text = text.lower()

    # Удаляем слова активации из текста команды
    text = activation_removal_pattern.sub("", text).strip()

    if not text:
        logging.warning("Команда пуста после удаления слов активации.")
        activation_detected = False  # Сбрасываем флаг активации
        return
    text = replace_number_words_with_digits(text)

    # Проверка команды громкости
    volume_match = music_volume_pattern.search(text)
    if volume_match:
        volume_level = int(volume_match.group(1))
        send_command('music', 'setVolume', {'level': volume_level})
        activation_detected = False
        return

    # **Проверяем музыкальные команды перед программными**
    if music_play_pattern.search(text):
        send_command('music', 'play', {})
        activation_detected = False
        return
    elif music_pause_pattern.search(text):
        send_command('music', 'togglePause', {})
        activation_detected = False
        return
    elif music_next_pattern.search(text):
        send_command('music', 'next', {})
        activation_detected = False
        return

    # Теперь обрабатываем программные команды
    for program_keywords, program_info in programs.items():
        program_pattern = r"\b(" + "|".join([re.escape(keyword) for keyword in program_keywords]) + r")\b"

        # Проверка команды запуска
        if start_pattern.search(text) and re.search(program_pattern, text):
            if 'start' in program_info:
                command_type = 'start'
                program_name, program_path = program_info['start']
                parameters = {}
                send_command(command_type, program_name, parameters)
                activation_detected = False
            return

        # Проверка команды остановки
        if stop_pattern.search(text) and re.search(program_pattern, text):
            if 'stop' in program_info:
                command_type = 'stop'
                command_name = program_info['stop']
                parameters = {}
                send_command(command_type, command_name, parameters)
                activation_detected = False
            return


    logging.warning(f"Неизвестная команда: {text}")
    # Существующая обработка программ
    for program_keywords, program_info in programs.items():
        program_pattern = r"\b(" + "|".join([re.escape(keyword) for keyword in program_keywords]) + r")\b"

        # Check for start command
        if start_pattern.search(text) and re.search(program_pattern, text):
            if 'start' in program_info:
                command_type = 'start'
                program_name, program_path = program_info['start']
                parameters = {}
                # For browser commands, check if there is a URL in text
                if program_name == 'Google Chrome':
                    # Extract URL from text if possible
                    url_match = re.search(r'\b(https?://[^\s]+)', text)
                    if url_match:
                        parameters['url'] = url_match.group(0)
                send_command(command_type, program_name, parameters)
                activation_detected = False
            return

        # Check for stop command
        if stop_pattern.search(text) and re.search(program_pattern, text):
            if 'stop' in program_info:
                command_type = 'stop'
                command_name = program_info['stop']
                parameters = {}
                send_command(command_type, command_name, parameters)
                activation_detected = False
            return

    logging.warning(f"Неизвестная команда: {text}")

def recognize_loop():
    global activation_detected
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = rec.Result()
            try:
                result_json = json.loads(result)
                text = result_json.get("text", "").lower()
                logging.debug(f"Распознанный текст: {text}")

                process_text(text)
            except json.JSONDecodeError as e:
                logging.error(f"Ошибка декодирования JSON результата: {e}")
        else:
            partial_result = rec.PartialResult()
            try:
                partial_json = json.loads(partial_result)
                partial_text = partial_json.get("partial", "").lower()

                # Only log if partial_text is not empty
                if partial_text.strip():
                    logging.debug(f"Промежуточный текст: {partial_text}")

                if not activation_detected and activation_pattern.search(partial_text):
                    logging.info(f"Слово активации распознано (промежуточно): '{partial_text}'. Ожидание команды...")
                    play_alert_sound()
                    activation_detected = True
            except json.JSONDecodeError as e:
                logging.error(f"Ошибка декодирования JSON промежуточного результата: {e}")

def process_text(text):
    global activation_detected

    if not activation_detected:
        if activation_pattern.search(text):
            logging.info(f"Слово активации распознано: '{text}'. Ожидание команды...")
            play_alert_sound("/home/alex/homeAI/voise_py/sounds/pops.wav")
            activation_detected = True
    else:
        # Remove activation words from the command text to prevent re-activation
        text = activation_removal_pattern.sub("", text).strip()

        if text:
            logging.info(f"Команда после активации: {text}")
            process_command(text)
            activation_detected = False  # Reset activation flag
        else:
            logging.debug("Нет команды после активации.")

def main():
    try:
        with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype='int16',
                               channels=1, callback=callback):
            logging.info("Начато прослушивание...")
            recognize_loop()
    except KeyboardInterrupt:
        logging.info("Прерывание пользователем. Завершение работы.")
    except Exception as e:
        logging.error(f"Неизвестная ошибка: {e}")

if __name__ == "__main__":
    main()