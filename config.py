import json
import os
import threading
from datetime import datetime
import logging
import logging.handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('torrent_monitor.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = "torrent_monitor_config.json"
CONFIG_LOCK = threading.Lock()

class Config:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self) -> dict:
        """Загрузка конфигурации из файла или создание по умолчанию."""
        with CONFIG_LOCK:
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            return json.loads(content)
                        logger.warning(f"Файл {CONFIG_FILE} пуст, возвращаем настройки по умолчанию")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка разбора {CONFIG_FILE}: {e}, возвращаем настройки по умолчанию")
            return self.ensure_config_exists()

    def save_config(self):
        """Сохранение конфигурации в файл."""
        with CONFIG_LOCK:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=4)
                logger.info(f"Конфигурация сохранена в {CONFIG_FILE}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении конфигурации: {e}")

    def ensure_config_exists(self) -> dict:
        """Создание файла конфигурации с настройками по умолчанию, если его нет."""
        if not os.path.exists(CONFIG_FILE):
            default_config = {
                "qbittorrent": {
                    "host": "http://localhost:8080",
                    "username": "",
                    "password": ""
                },
                "scan_interval": 30,
                "series": {},
                "last_scan": None,
                "auto_start": False  # Добавляем новый параметр
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
            logger.info(f"Создан новый файл конфигурации: {CONFIG_FILE}")
            return default_config
        return self.load_config()

    def get(self, key: str, default=None):
        """Получение значения из конфигурации."""
        return self.config.get(key, default)

    def set(self, key: str, value):
        """Установка значения в конфигурации с последующим сохранением."""
        self.config[key] = value
        self.save_config()

    def add_series(self, series_url: str, save_path: str, series_name: str, season: str):
        """Добавление сериала в конфигурацию."""
        if series_url in self.config["series"]:
            logger.warning(f"Сериал {series_url} уже добавлен")
            return False
        self.config["series"][series_url] = {
            "save_path": save_path,
            "series_name": series_name,
            "season": season,
            "rename_enabled": False
        }
        self.save_config()
        logger.info(f"Добавлен сериал: {series_url}")
        return True

    def remove_series(self, series_url: str):
        """Удаление сериала из конфигурации."""
        if series_url in self.config["series"]:
            del self.config["series"][series_url]
            self.save_config()
            logger.info(f"Удален сериал: {series_url}")
            return True
        logger.warning(f"Сериал {series_url} не найден")
        return False

    def update_last_scan(self):
        """Обновление времени последнего сканирования."""
        self.config["last_scan"] = datetime.utcnow().isoformat()
        self.save_config()
        logger.info(f"Обновлено время последнего сканирования: {self.config['last_scan']}")