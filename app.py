from flask import Flask
from flask_socketio import SocketIO
from routes import setup_routes
from monitor import setup_scheduler, scheduler
from qbittorrent_manager import QBittorrentManager
from config import Config
from utils import setup_logging
from scrapers.anilibria_scraper import AnilibriaScraper
from scrapers.astar_bz_scraper import AstarBzScraper

app = Flask(__name__)
socketio = SocketIO(app)

# Инициализация логирования
setup_logging(socketio)

# Инициализация парсеров
scrapers = {
    "anilibria.top": AnilibriaScraper(),
    "astar.bz": AstarBzScraper()
}

# Инициализация конфигурации
config = Config()
qb_manager = QBittorrentManager(
    config.get("qbittorrent")["host"],
    config.get("qbittorrent")["username"],
    config.get("qbittorrent")["password"]
)

# Передаём объекты в маршруты и планировщик
setup_routes(app, socketio, qb_manager, scrapers, config)
setup_scheduler(socketio, qb_manager, scrapers, config)

# Автозапуск мониторинга только если auto_start включён
if config.get("auto_start", False):
    app.config['scheduler_running'] = True
    if not scheduler.running:
        scheduler.start()
        print("Мониторинг автоматически запущен при старте")
else:
    app.config['scheduler_running'] = False
    print("Мониторинг не запущен при старте (auto_start отключён)")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)