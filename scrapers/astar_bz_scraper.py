import asyncio
import cloudscraper
from lxml import html
import logging
from datetime import datetime
from .base_scraper import BaseScraper
import hashlib
import os

logger = logging.getLogger(__name__)

# Флаг для включения/отключения сохранения HTML для отладки
# Установите в True, чтобы сохранять дебаг-файлы, или в False, чтобы отключить
DEBUG_SAVE_HTML = False

class AstarBzScraper(BaseScraper):
    def __init__(self, max_retries: int = 3):
        self.scraper = cloudscraper.create_scraper()
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://v6.astar.bz/",
            "Connection": "keep-alive"
        }

    async def fetch_page(self, url: str):
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(self.scraper.get, url, headers=self.headers)
                if response.status_code == 200:
                    html_content = response.text
                    if DEBUG_SAVE_HTML:
                        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                        debug_filename = f"debug_astar_bz_{url_hash}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        logger.info(f"HTML страницы {url} сохранён в {debug_filename}")
                    return html_content
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries}: Код ответа {response.status_code} для {url}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: Ошибка при запросе {url}: {e}")
            await asyncio.sleep(2 ** attempt)
        logger.error(f"Не удалось загрузить страницу {url} после {self.max_retries} попыток")
        return None

    async def get_episodes(self, series_url: str, quality: str = None):
        # quality игнорируется, так как Astar.bz не предоставляет варианты качества
        episodes = []
        html_content = await self.fetch_page(series_url)
        if not html_content:
            return episodes

        tree = html.fromstring(html_content)
        
        # Извлечение названия сериала
        title_elem = tree.xpath('//h1[@itemprop="name"]/text()')
        series_name = title_elem[0].strip() if title_elem else "Неизвестно"
        names = [name.strip() for name in series_name.split("/")]

        torrent_blocks = tree.xpath('//div[@class="torrent"]')
        base_torrent_id = hashlib.md5(series_url.encode()).hexdigest()[:8]

        for i, block in enumerate(torrent_blocks):
            torrent_link = block.xpath('.//a[contains(@href, "gettorrent.php?id=")]/@href')
            if not torrent_link:
                logger.warning(f"Ссылка на торрент не найдена для блока {i} в {series_url}")
                continue
            torrent_url = f"https://v6.astar.bz{torrent_link[0]}"
            torrent_id = f"{base_torrent_id}_{i:02d}"

            episode_name_elem = block.xpath('.//div[@class="info_d1"]/text()')
            episode_name = episode_name_elem[0].strip() if episode_name_elem else f"Эпизод {i+1}"

            # Извлечение даты
            date_elem = block.xpath('.//div[@class="bord_a1"][contains(., "Дата: ")]//text()')
            last_updated = ""
            if date_elem:
                date_str = "".join(date_elem).replace("Дата: ", "").strip()
                if date_str:
                    try:
                        last_updated = datetime.strptime(date_str, "%d-%m-%Y").isoformat()
                    except ValueError as e:
                        logger.error(f"Ошибка парсинга даты '{date_str}' для торрента {torrent_id}: {e}")
            if not last_updated:
                logger.warning(f"Дата не найдена для торрента {torrent_id}, используется значение по умолчанию")

            episodes.append({
                "torrent_url": torrent_url,
                "torrent_id": torrent_id,
                "name": names[0],  # Основное название сериала
                "episode_name": episode_name,  # Название конкретного торрента
                "last_updated": last_updated,
                "quality": "N/A"
            })

        logger.info(f"Найдено {len(episodes)} эпизодов для {series_url}")
        return episodes

    async def get_torrent_content(self, torrent_url: str):
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(self.scraper.get, torrent_url, headers=self.headers)
                if response.status_code == 200:
                    logger.info(f"Успешно загружен торрент-файл для {torrent_url}")
                    return response.content
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries}: Код ответа {response.status_code} для {torrent_url}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: Ошибка при запросе {torrent_url}: {e}")
            await asyncio.sleep(2 ** attempt)
        logger.error(f"Не удалось загрузить торрент-файл для {torrent_url} после {self.max_retries} попыток")
        return None

    async def scan_series(self, series_url: str):
        html_content = await self.fetch_page(series_url)
        if not html_content:
            return {"name": "Ошибка", "quality_options": []}

        tree = html.fromstring(html_content)
        title_elem = tree.xpath('//h1[@itemprop="name"]/text()')
        series_name = title_elem[0].strip() if title_elem else "Неизвестно"
        names = [name.strip() for name in series_name.split("/")]

        logger.info(f"Найдено вариантов качества для {series_url}: отсутствуют")
        return {
            "name": names[0],
            "names": names,
            "quality_options": []
        }