import json
import os
import threading
from datetime import datetime
import logging
import logging.handlers
from typing import List  # Добавляем импорт List

logging.basicConfig(
    level=logging.DEBUG,
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
        self.config = self.load_or_create_config()

    def get_default_config(self):
        return {
            "qbittorrent": {
                "host": "http://localhost:8080",
                "username": "",
                "password": ""
            },
            "scan_interval": 30,
            "series": {},
            "last_scan": None,
            "auto_start": False
        }

    def load_or_create_config(self):
        with CONFIG_LOCK:
            if not os.path.exists(CONFIG_FILE):
                logger.info(f"Файл {CONFIG_FILE} не найден, создаём новый")
                return self.ensure_config_exists()
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning(f"Файл {CONFIG_FILE} пуст, возвращаем настройки по умолчанию")
                        return self.ensure_config_exists()
                    config = json.loads(content)
                    default = self.get_default_config()
                    for key in default:
                        if key not in config:
                            logger.warning(f"Отсутствует ключ {key} в конфигурации, восстанавливаем")
                            config[key] = default[key]
                    return config
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Ошибка чтения {CONFIG_FILE}: {e}, воссоздаём файл")
                return self.ensure_config_exists()

    def save_config(self):
        with CONFIG_LOCK:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=4)
                logger.info(f"Конфигурация сохранена в {CONFIG_FILE}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении конфигурации: {e}")

    def ensure_config_exists(self):
        default_config = self.get_default_config()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        logger.info(f"Создан новый файл конфигурации: {CONFIG_FILE}")
        return default_config

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save_config()

    def add_series(self, series_url: str, save_path: str, series_name: str, season: str, quality: str = None, is_seasonal_torrent: bool = False, torrent_ids: List[str] = None):
        if series_url in self.config["series"]:
            logger.warning(f"Сериал {series_url} уже добавлен")
            return False
        self.config["series"][series_url] = {
            "save_path": save_path,
            "series_name": series_name,
            "season": season,
            "rename_enabled": False,
            "quality": quality,
            "is_seasonal_torrent": is_seasonal_torrent,
            "torrent_ids": torrent_ids or []
        }
        self.save_config()
        logger.info(f"Добавлен сериал: {series_url}")
        return True

    def remove_series(self, series_url: str):
        if series_url in self.config["series"]:
            del self.config["series"][series_url]
            self.save_config()
            logger.info(f"Удален сериал: {series_url}")
            return True
        logger.warning(f"Сериал {series_url} не найден")
        return False

    def update_last_scan(self):
        self.config["last_scan"] = datetime.utcnow().isoformat()
        self.save_config()
        logger.info(f"Обновлено время последнего сканирования: {self.config['last_scan']}")