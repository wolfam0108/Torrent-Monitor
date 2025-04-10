import asyncio
import cloudscraper
from bs4 import BeautifulSoup
import logging
from .base_scraper import BaseScraper
import hashlib

logger = logging.getLogger(__name__)

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

    async def get_episodes(self, series_url: str, quality: str = None):
        # quality игнорируется, так как для v6.astar.bz нет вариантов качества
        episodes = []
        html = await self.fetch_page(series_url)
        if not html:
            return episodes
        soup = BeautifulSoup(html, "html.parser")
        torrent_blocks = soup.find_all("div", class_="torrent")
        base_torrent_id = hashlib.md5(series_url.encode()).hexdigest()[:8]
        for i, block in enumerate(torrent_blocks):
            torrent_link = block.find("a", href=True)
            if not torrent_link or "gettorrent.php?id=" not in torrent_link["href"]:
                continue
            torrent_url = f"https://v6.astar.bz/{torrent_link['href']}"
            torrent_id = f"{base_torrent_id}_{i:02d}"
            episode_name = torrent_link.find("div", class_="info_d1").text.strip()
            date_elem = block.find("div", class_="bord_a1", string=lambda x: x and "Дата: " in x)
            date_str = date_elem.text.replace("Дата: ", "").strip() if date_elem else "Неизвестно"
            episodes.append({
                "torrent_url": torrent_url,
                "torrent_id": torrent_id,
                "name": episode_name,
                "date": date_str
                # Убираем magnet_link, так как используем торрент-файлы
            })
        logger.info(f"Найдено {len(episodes)} эпизодов для {series_url}")
        return episodes

    async def get_torrent_content(self, torrent_url: str):
        # Загружаем торрент-файл напрямую
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(self.scraper.get, torrent_url, headers=self.headers)
                if response.status_code == 200:
                    logger.info(f"Успешно загружен торрент-файл для {torrent_url}")
                    return response.content  # Возвращаем байты торрент-файла
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries}: Код ответа {response.status_code} для {torrent_url}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: Ошибка при запросе {torrent_url}: {e}")
            await asyncio.sleep(2 ** attempt)
        logger.error(f"Не удалось загрузить торрент-файл для {torrent_url} после {self.max_retries} попыток")
        return None

    async def scan_series(self, series_url: str):
        html = await self.fetch_page(series_url)
        if not html:
            return {"name": "Ошибка", "quality_options": []}
        soup = BeautifulSoup(html, "html.parser")
        title_elem = soup.find("h1", class_="post_h1")
        series_name = title_elem.text.strip() if title_elem else "Неизвестно"
        torrent_blocks = soup.find_all("div", class_="torrent")
        quality_options = []
        for block in torrent_blocks:
            torrent_link = block.find("a", href=True)
            if torrent_link and "gettorrent.php?id=" in torrent_link["href"]:
                quality_options.append({"link": f"https://v6.astar.bz/{torrent_link['href']}", "quality": "Стандартное"})
        logger.info(f"Найдено {len(quality_options)} уникальных вариантов качества для {series_url}")
        return {
            "name": series_name,
            "quality_options": quality_options if quality_options else [{"link": "", "quality": "Не найдено"}]
        }

    async def fetch_page(self, url: str):
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(self.scraper.get, url, headers=self.headers)
                if response.status_code == 200:
                    return response.text
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries}: Код ответа {response.status_code} для {url}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: Ошибка при запросе {url}: {e}")
            await asyncio.sleep(2 ** attempt)
        logger.error(f"Не удалось загрузить страницу {url} после {self.max_retries} попыток")
        return None