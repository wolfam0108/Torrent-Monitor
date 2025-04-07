from flask import Flask
from flask_socketio import SocketIO
from routes import setup_routes
from monitor import setup_scheduler, scheduler  # Добавляем импорт scheduler
from qbittorrent_manager import QBittorrentManager
from config import Config
from utils import setup_logging
import asyncio

app = Flask(__name__)
socketio = SocketIO(app)

# Инициализация логирования
setup_logging(socketio)

# Инициализация qb_manager при старте
config = Config()
qb_manager = QBittorrentManager(
    config.get("qbittorrent")["host"],
    config.get("qbittorrent")["username"],
    config.get("qbittorrent")["password"]
)
asyncio.run(qb_manager.connect())

# Передаём qb_manager в маршруты и планировщик
setup_routes(app, socketio, qb_manager)
setup_scheduler(socketio, qb_manager)

# Автозапуск мониторинга, если включён в конфигурации
if config.get("auto_start", False):
    app.config['scheduler_running'] = True
    if not scheduler.running:
        scheduler.start()  # Запускаем планировщик, если он ещё не запущен
        print("Мониторинг автоматически запущен при старте")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)