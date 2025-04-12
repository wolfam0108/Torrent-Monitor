from flask import Flask
from flask_socketio import SocketIO
from routes import setup_routes
from monitor import setup_scheduler, scheduler
from config import Config
from utils import setup_logging
from auth_manager import AuthManager
import asyncio

app = Flask(__name__)
socketio = SocketIO(app)

# Флаг для включения/отключения парсера nnmclub.to
ENABLE_NNMCLUB_SCRAPER = False

# Инициализация логирования
setup_logging(socketio)

# Инициализация конфигурации
config = Config()

# Инициализация менеджера авторизации
auth_manager = AuthManager(config, socketio, enable_nnmclub_scraper=ENABLE_NNMCLUB_SCRAPER)

# Передаём объекты в маршруты и планировщик
setup_routes(app, socketio, auth_manager, config)
setup_scheduler(socketio, auth_manager, config)

# Автозапуск мониторинга только если auto_start включён
if config.get("auto_start", False):
    app.config['scheduler_running'] = True
    if not scheduler.running:
        scheduler.start()
        print("Мониторинг автоматически запущен при старте")
else:
    app.config['scheduler_running'] = False
    print("Мониторинг не запущен при старте (auto_start отключён)")

# Запускаем инициализацию авторизации после старта приложения
@socketio.on('connect')
def handle_connect():
    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(auth_manager.initialize())
        finally:
            loop.close()
    
    import threading
    threading.Thread(target=run_async_task, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)