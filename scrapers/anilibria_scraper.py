import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import re
import time
import logging
from .base_scraper import BaseScraper
from urllib.parse import unquote
import hashlib

logger = logging.getLogger(__name__)

class AnilibriaScraper(BaseScraper):
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
        self.service = Service(executable_path="/usr/local/bin/chromedriver", log_path="chromedriver.log")
        self.driver = None

    def _init_driver(self):
        if self.driver is None:
            self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
            logger.info("Selenium driver запущен")

    def _quit_driver(self):
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
            logger.info("Selenium driver закрыт")

    async def get_episodes(self, series_url: str, quality: str = None):
        self._init_driver()
        try:
            logger.info(f"Запрос эпизодов для {series_url} через AnilibriaScraper с качеством {quality}")
            self.driver.get(series_url)
            await asyncio.sleep(10)  # Ждём загрузки страницы
            html_content = self.driver.page_source
            magnet_pattern = r'(magnet:\?xt=urn:btih:[a-zA-Z0-9]+[^"]*)'
            magnet_links = list(set(re.findall(magnet_pattern, html_content)))
            episodes = []
            for link in magnet_links:
                dn_match = re.search(r'dn=([^&]+)', link)
                link_quality = "Неизвестно"
                if dn_match:
                    dn = unquote(dn_match.group(1))
                    quality_match = re.search(r'\[([^]]+)\]', dn)
                    link_quality = quality_match.group(1) if quality_match else "Неизвестно"
                if quality and link_quality != quality:
                    continue
                torrent_id = hashlib.md5(series_url.encode()).hexdigest()[:8] + (f"_{link_quality}" if link_quality else "")
                episodes.append({
                    "name": f"Сезон целиком ({link_quality})",
                    "torrent_url": series_url,
                    "torrent_id": torrent_id,
                    "magnet_link": link  # Добавляем magnet-ссылку
                })
                break  # Выходим после нужного качества
            logger.info(f"Получено {len(episodes)} эпизодов для {series_url}")
            return episodes if episodes else [{"name": "Сезон целиком", "torrent_url": series_url, "torrent_id": hashlib.md5(series_url.encode()).hexdigest()[:8], "magnet_link": None}]
        except Exception as e:
            logger.error(f"Ошибка при получении эпизодов для {series_url}: {e}")
            return []
        finally:
            self._quit_driver()

    async def get_torrent_content(self, torrent_url: str):
        # Оставляем для совместимости, но теперь не используется в scan_series
        self._init_driver()
        try:
            self.driver.get(torrent_url)
            await asyncio.sleep(10)
            html_content = self.driver.page_source
            magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+[^"]*'
            magnet_links = re.findall(magnet_pattern, html_content)
            return magnet_links[0] if magnet_links else None
        except Exception as e:
            logger.error(f"Ошибка при получении magnet-ссылки: {e}")
            return None
        finally:
            self._quit_driver()

    async def scan_series(self, series_url: str):
        self._init_driver()
        try:
            self.driver.get(series_url)
            await asyncio.sleep(10)
            html_content = self.driver.page_source
            title_match = re.search(r'<meta property="og:title" content="([^"]+)', html_content)
            series_name = title_match.group(1).split(" | ")[0] if title_match else "Неизвестно"
            magnet_pattern = r'(magnet:\?xt=urn:btih:[a-zA-Z0-9]+[^"]*)'
            magnet_links = list(set(re.findall(magnet_pattern, html_content)))
            quality_options = []
            for link in magnet_links:
                dn_match = re.search(r'dn=([^&]+)', link)
                if dn_match:
                    dn = unquote(dn_match.group(1))
                    quality_match = re.search(r'\[([^]]+)\]', dn)
                    quality = quality_match.group(1) if quality_match else "Неизвестно"
                else:
                    quality = "Неизвестно"
                quality_options.append({"link": link, "quality": quality})
            logger.info(f"Найдено {len(quality_options)} уникальных вариантов качества для {series_url}: {quality_options}")
            return {
                "name": series_name,
                "quality_options": quality_options if quality_options else [{"link": "", "quality": "Не найдено"}]
            }
        except Exception as e:
            logger.error(f"Ошибка при сканировании серии: {e}")
            return {"name": "Ошибка", "quality_options": []}
        finally:
            self._quit_driver()