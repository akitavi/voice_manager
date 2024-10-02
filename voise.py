import sounddevice as sd
import queue
import subprocess
from vosk import Model, KaldiRecognizer
import json
import re
import pygame  # For playing sound
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO in production
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]
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

# Initialize Pygame mixer
pygame.mixer.init()

def play_alert_sound():
    try:
        pygame.mixer.music.load("/home/alex/homeAI/voise_py/sounds/pops.wav")  # Provide absolute path if necessary
        pygame.mixer.music.play()
        logging.info("Звуковой сигнал воспроизведён")
    except Exception as e:
        logging.error(f"Ошибка при воспроизведении звука: {e}")

def start_program(program_name, program_path):
    logging.info(f"Команда распознана: запуск {program_name}")
    try:
        # Если в команде есть аргументы (например, для Steam), разделяем её на отдельные части
        program_parts = program_path.split()  # Разбиваем строку на команду и её аргументы
        subprocess.Popen(program_parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"{program_name} успешно запущен")
    except Exception as e:
        logging.error(f"Ошибка при запуске {program_name}: {e}")

def stop_program(program_command, is_shutdown=False):
    if is_shutdown:
        logging.info("Команда распознана: выключение системы")
        try:
            subprocess.Popen(["sudo", "/usr/sbin/poweroff"])
            logging.info("Система выключена")
        except Exception as e:
            logging.error(f"Ошибка при выключении системы: {e}")
    else:
        logging.info(f"Команда распознана: выключение {program_command}")
        try:
            subprocess.Popen(["pkill", program_command])
            logging.info(f"{program_command} успешно закрыт")
        except Exception as e:
            logging.error(f"Ошибка при закрытии {program_command}: {e}")

# Dictionary of programs and commands with synonyms
programs = {
    ('браузер', 'брауер', 'chrome'): {
        'start': ('Google Chrome', '/usr/bin/google-chrome'),
        'stop': 'chrome'
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
start_pattern = re.compile(r"\b(включ[иы]|запуст[иы]|откр[оа]й|покаж[иы]|откр[юу]|открыть|включить)\b")
stop_pattern = re.compile(r"\b(выключ[иы]|закрыть|закр[оа]й|останов[иы]|прекрат[иы]|выключить)\b")

def process_command(text):
    global activation_detected
    text = text.lower()

    # Remove activation words from the command text to prevent re-activation
    text = activation_removal_pattern.sub("", text).strip()

    if not text:
        logging.warning("Команда пуста после удаления слов активации.")
        activation_detected = False  # Reset activation flag
        return

    for program_keywords, program_info in programs.items():
        # Create regex pattern for program keywords
        program_pattern = r"\b(" + "|".join([re.escape(keyword) for keyword in program_keywords]) + r")\b"

        # Check for start command
        if start_pattern.search(text) and re.search(program_pattern, text):
            if 'start' in program_info:
                program_name, program_path = program_info['start']
                start_program(program_name, program_path)
            return

        # Check for stop command
        if stop_pattern.search(text) and re.search(program_pattern, text):
            if 'stop' in program_info:
                stop_command = program_info['stop']
                is_shutdown = stop_command == 'poweroff'
                stop_program(stop_command, is_shutdown=is_shutdown)
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
            play_alert_sound()
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
