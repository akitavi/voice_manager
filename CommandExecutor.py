from flask import Flask, request, jsonify
import subprocess
import threading
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

app = Flask(__name__)

# Configure logging
log_directory = "logs"
log_file = os.path.join(log_directory, "homeai_comand.log")
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO in production
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Вывод логов в консоль
        logging.FileHandler(log_file, mode='a')  # Запись логов в файл
    ]
)

# Dictionary of programs and commands
programs = {
    'Google Chrome': {
        'start': '/usr/bin/google-chrome',
        'stop': 'chrome'
    },
    'Текстовый редактор': {
        'start': '/usr/bin/subl',
        'stop': 'subl'
    },
    'Терминал': {
        'start': '/usr/bin/terminator',
        'stop': 'terminator'
    },
    'Steam': {
        'start': '/usr/bin/steam',
        'stop': 'steam'
    },
    'Dota2': {
        'start': 'steam steam://rungameid/570',
        'stop': 'dota2'
    },
    'poweroff': {
        'stop': 'poweroff'
    }
}

browser_driver = None  # Глобальная переменная для управления браузером

@app.route('/execute', methods=['POST'])
def execute_command():
    data = request.get_json()
    command_type = data.get('command_type')
    command_name = data.get('command_name')
    parameters = data.get('parameters', {})
    logging.info(f"Получен запрос: {data}")

    if not command_type or not command_name:
        return jsonify({'status': 'error', 'message': 'Missing command_type or command_name'}), 400

    # Process the command asynchronously
    threading.Thread(target=process_command, args=(command_type, command_name, parameters)).start()

    return jsonify({'status': 'success', 'message': 'Команда выполняется'}), 200

def process_command(command_type, command_name, parameters):
    if command_type == 'start':
        start_program(command_name, parameters)
    elif command_type == 'stop':
        stop_program(command_name)
    elif command_type == 'music':
        handle_music_command(command_name, parameters)
    else:
        logging.error(f"Неизвестный тип команды: {command_type}")

def handle_music_command(command_name, parameters={}):
    global browser_driver

    # Если браузер не запущен, открываем его
    if browser_driver is None:
        logging.info("Браузер не открыт, открываем браузер для музыки")
        open_music_browser()

    try:
        # Проверяем наличие externalAPI на странице
        api_exists = browser_driver.execute_script("return typeof externalAPI !== 'undefined';")
        if not api_exists:
            logging.error("externalAPI не найден на странице.")
            return

        if command_name == 'play':
            logging.info("Выполнение команды: externalAPI.play(1)")
            browser_driver.execute_script("externalAPI.play(1);")
            logging.info("Музыка запущена")
        elif command_name == 'togglePause':
            logging.info("Выполнение команды: externalAPI.togglePause()")
            browser_driver.execute_script("externalAPI.togglePause();")
            logging.info("Музыка поставлена на паузу/продолжена")
        elif command_name == 'next':
            logging.info("Выполнение команды: externalAPI.next()")
            browser_driver.execute_script("externalAPI.next();")
            logging.info("Следующий трек")
        elif command_name == 'setVolume':
            volume_level = parameters.get('level', 5)  # По умолчанию 5
            volume = max(0, min(volume_level, 10)) / 10.0
            logging.info(f"Выполнение команды: externalAPI.setVolume({volume})")
            browser_driver.execute_script(f"externalAPI.setVolume({volume});")
            logging.info(f"Громкость установлена на {volume_level}")
        else:
            logging.error(f"Неизвестная команда для музыки: {command_name}")
    except Exception as e:
        logging.error(f"Ошибка при выполнении команды музыки: {e}", exc_info=True)

def start_program(program_name, parameters):
    logging.info(f"Команда распознана: запуск {program_name}")

    if program_name == 'Музыка':
        # Открываем музыкальный браузер напрямую
        open_music_browser()
    elif program_name == 'Google Chrome' and 'url' in parameters:
        # Используем Selenium для открытия браузера с URL
        url = parameters['url']
        open_browser(url)
    else:
        try:
            program_path = programs[program_name]['start']
            if program_path:  # Проверяем, что путь не пустой
                # Если путь программы это строка с аргументами, разбить её
                program_parts = program_path.split()
                subprocess.Popen(program_parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logging.info(f"{program_name} успешно запущен")
            else:
                logging.error(f"Не указан путь для запуска программы {program_name}")
        except Exception as e:
            logging.error(f"Ошибка при запуске {program_name}: {e}")

def stop_program(program_command):
    global browser_driver
    logging.info(f"Команда распознана: выключение {program_command}")
    if program_command == 'music':
        if browser_driver is not None:
            try:
                browser_driver.quit()
                logging.info("Музыкальный браузер закрыт")
                browser_driver = None
            except Exception as e:
                logging.error(f"Ошибка при закрытии музыкального браузера: {e}")
        else:
            logging.warning("Музыкальный браузер не запущен")
    elif program_command == 'poweroff':
        try:
            subprocess.Popen(["sudo", "/usr/sbin/poweroff"])
            logging.info("Система выключена")
        except Exception as e:
            logging.error(f"Ошибка при выключении системы: {e}")
    else:
        try:
            subprocess.Popen(["pkill", program_command])
            logging.info(f"{program_command} успешно закрыт")
        except Exception as e:
            logging.error(f"Ошибка при закрытии {program_command}: {e}")

def open_browser(url):
    logging.info(f"Открытие браузера с URL: {url}")
    try:
        options = Options()
        # options.add_argument('--headless')  # Закомментировано для запуска с UI
        options.add_argument("user-data-dir=/home/alex/.config/google-chrome/Default")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        # Keep the browser open or perform additional actions
        driver.quit()
        logging.info("Браузер успешно открыт и закрыт")
    except Exception as e:
        logging.error(f"Ошибка при открытии браузера: {e}")

def open_music_browser():
    global browser_driver
    logging.info("Открытие браузера для музыки")
    try:
        options = Options()
        # options.add_argument("--headless")
        options.add_argument("user-data-dir=/home/alex/.config/google-chrome-selenium")
        browser_driver = webdriver.Chrome(options=options)
        # browser_driver.set_page_load_timeout(15)
        # browser_driver.set_script_timeout(15)
        # browser_driver.implicitly_wait(15)

        music_url = 'https://music.yandex.ru'
        browser_driver.get(music_url)

        # Ожидаем загрузку страницы и доступность externalAPI
        wait = WebDriverWait(browser_driver, 5)
        wait.until(lambda driver: driver.execute_script("return typeof externalAPI !== 'undefined';"))

        logging.info("Браузер для музыки успешно открыт")
    except Exception as e:
        logging.error(f"Ошибка при открытии браузера для музыки: {e}", exc_info=True)
        browser_driver = None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
