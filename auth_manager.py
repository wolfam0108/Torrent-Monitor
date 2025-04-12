import asyncio
from typing import Dict, Optional
from qbittorrentapi import Client, LoginFailed
import logging
from scrapers.anilibria_scraper import AnilibriaScraper
from scrapers.astar_bz_scraper import AstarBzScraper
from scrapers.kinozal_scraper import KinozalScraper
from scrapers.rutracker_scraper import RutrackerScraper
from scrapers.nnmclub_scraper import NnmClubScraper

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, config, socketio, enable_nnmclub_scraper: bool = False):
        self.config = config
        self.socketio = socketio
        self.qb_client = None
        self.enable_nnmclub_scraper = enable_nnmclub_scraper
        self.scrapers: Dict[str, Optional[object]] = {
            "anilibria.top": AnilibriaScraper(),
            "astar.bz": AstarBzScraper(),
            "kinozal.tv": None,  # Ленивая инициализация
            "kinozal.me": None,  # Ленивая инициализация
            "rutracker.org": None,  # Ленивая инициализация
            "nnmclub.to": NnmClubScraper() if enable_nnmclub_scraper else None
        }
        self.statuses = {
            "qbittorrent": {"status": "Проверка...", "spinner": True},
            "kinozal": {"status": "Проверка...", "spinner": True},
            "rutracker": {"status": "Проверка...", "spinner": True}
        }

    async def connect_qbittorrent(self):
        try:
            qb_config = self.config.get("qbittorrent")
            client = Client(
                host=qb_config["host"],
                username=qb_config["username"],
                password=qb_config["password"],
                VERIFY_WEBUI_CERTIFICATE=False
            )
            client.auth_log_in()
            version = client.app.version
            self.qb_client = client
            self.statuses["qbittorrent"] = {"status": f"Подключено (версия: {version})", "spinner": False}
            logger.info(f"Подключено к qBittorrent, версия: {version}")
        except LoginFailed as e:
            self.statuses["qbittorrent"] = {"status": f"Ошибка: Неверный логин/пароль", "spinner": False}
            logger.error(f"Ошибка входа в qBittorrent: {e}")
        except Exception as e:
            self.statuses["qbittorrent"] = {"status": f"Ошибка: Сервис недоступен", "spinner": False}
            logger.error(f"Ошибка подключения к qBittorrent: {e}")
        finally:
            self.socketio.emit('auth_status', self.statuses)

    async def connect_kinozal(self):
        kinozal_auth = self.config.get("kinozal_auth")
        if not kinozal_auth["username"] or not kinozal_auth["password"]:
            self.statuses["kinozal"] = {"status": "Нет данных для авторизации", "spinner": False}
        else:
            try:
                scraper = KinozalScraper(kinozal_auth["username"], kinozal_auth["password"])
                self.scrapers["kinozal.tv"] = scraper
                self.scrapers["kinozal.me"] = scraper
                self.statuses["kinozal"] = {"status": "Авторизация успешна", "spinner": False}
                logger.info("Успешная авторизация на Kinozal")
            except Exception as e:
                self.statuses["kinozal"] = {"status": f"Ошибка: {str(e)}", "spinner": False}
                logger.error(f"Ошибка авторизации на Kinozal: {e}")
        self.socketio.emit('auth_status', self.statuses)

    async def connect_rutracker(self):
        rutracker_auth = self.config.get("rutracker_auth")
        if not rutracker_auth["username"] or not rutracker_auth["password"]:
            self.statuses["rutracker"] = {"status": "Нет данных для авторизации", "spinner": False}
        else:
            try:
                scraper = RutrackerScraper(rutracker_auth["username"], rutracker_auth["password"])
                self.scrapers["rutracker.org"] = scraper
                self.statuses["rutracker"] = {"status": "Авторизация успешна", "spinner": False}
                logger.info("Успешная авторизация на RuTracker")
            except Exception as e:
                self.statuses["rutracker"] = {"status": f"Ошибка: {str(e)}", "spinner": False}
                logger.error(f"Ошибка авторизации на RuTracker: {e}")
        self.socketio.emit('auth_status', self.statuses)

    async def initialize(self):
        tasks = [
            asyncio.wait_for(self.connect_qbittorrent(), timeout=15),
            asyncio.wait_for(self.connect_kinozal(), timeout=10),
            asyncio.wait_for(self.connect_rutracker(), timeout=10)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Инициализация AuthManager завершена")

    def get_scraper(self, series_url: str):
        from urllib.parse import urlparse
        parsed_url = urlparse(series_url)
        domain = parsed_url.netloc
        if domain.startswith('v6.'):
            domain = domain[3:]
        if domain == "nnmclub.to" and not self.enable_nnmclub_scraper:
            logger.info(f"Парсер для {domain} отключён")
            return None
        if domain in ["kinozal.tv", "kinozal.me"] and not self.scrapers[domain]:
            kinozal_auth = self.config.get("kinozal_auth")
            if kinozal_auth["username"] and kinozal_auth["password"]:
                scraper = KinozalScraper(kinozal_auth["username"], kinozal_auth["password"])
                self.scrapers["kinozal.tv"] = scraper
                self.scrapers["kinozal.me"] = scraper
        elif domain == "rutracker.org" and not self.scrapers[domain]:
            rutracker_auth = self.config.get("rutracker_auth")
            if rutracker_auth["username"] and rutracker_auth["password"]:
                self.scrapers[domain] = RutrackerScraper(rutracker_auth["username"], rutracker_auth["password"])
        return self.scrapers.get(domain)

    def get_qb_client(self):
        return self.qb_client