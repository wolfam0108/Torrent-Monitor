import logging
import logging.handlers
from flask_socketio import SocketIO
import re

# Функция для удаления ANSI-кодов
def strip_ansi_codes(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('torrent_monitor.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()  # Вывод в консоль
    ]
)
logger = logging.getLogger(__name__)

class SocketIOHandler(logging.Handler):
    def __init__(self, socketio: SocketIO):
        super().__init__()
        self.socketio = socketio

    def emit(self, record):
        try:
            msg = self.format(record)
            clean_msg = strip_ansi_codes(msg)  # Удаляем ANSI-коды
            self.socketio.emit('log', {'message': clean_msg, 'level': record.levelname}, namespace='/')
        except Exception as e:
            logger.error(f"Ошибка в SocketIOHandler: {str(e)}")

def load_logs():
    try:
        with open('torrent_monitor.log', 'r', encoding='utf-8') as f:
            lines = [strip_ansi_codes(line) for line in f.readlines()]  # Удаляем ANSI-коды из файла
            return lines[-100:] if len(lines) > 100 else lines  # Последние 100 строк
    except FileNotFoundError:
        return []

def setup_logging(socketio):
    socket_handler = SocketIOHandler(socketio)
    socket_handler.setLevel(logging.INFO)
    socket_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.handlers = [h for h in logger.handlers if not isinstance(h, SocketIOHandler)]  # Удаляем старые SocketIOHandler
    logger.addHandler(socket_handler)