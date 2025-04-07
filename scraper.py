import asyncio
import cloudscraper
from bs4 import BeautifulSoup
import logging
import logging.handlers
from typing import List, Dict, Optional

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

class AstarBzScraper:
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

    async def fetch_page(self, url: str) -> Optional[str]:
        """Загрузка страницы с повторными попытками через cloudscraper."""
        loop = asyncio.get_event_loop()
        for attempt in range(self.max_retries):
            try:
                response = await loop.run_in_executor(None, lambda: self.scraper.get(url, headers=self.headers))
                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(f"Попытка {attempt + 1}/{self.max_retries}: статус {response.status_code} для {url}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: ошибка при загрузке {url}: {e}")
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        logger.error(f"Не удалось загрузить страницу {url} после {self.max_retries} попыток")
        return None

    async def get_episodes(self, series_url: str) -> List[Dict[str, str]]:
        """Извлечение списка эпизодов с страницы сериала."""
        episodes = []
        html = await self.fetch_page(series_url)
        if not html:
            return episodes

        soup = BeautifulSoup(html, "html.parser")
        torrent_blocks = soup.find_all("div", class_="torrent")

        for block in torrent_blocks:
            torrent_link = block.find("a", href=True)
            if not torrent_link or "gettorrent.php?id=" not in torrent_link["href"]:
                continue

            torrent_url = torrent_link["href"]
            torrent_id = torrent_url.split("id=")[-1]
            episode_name = torrent_link.find("div", class_="info_d1").text.strip()
            date_elem = block.find("div", class_="bord_a1", string=lambda x: x and "Дата: " in x)
            date_str = date_elem.text.replace("Дата: ", "").strip() if date_elem else "Неизвестно"

            episodes.append({
                "torrent_url": torrent_url,
                "torrent_id": torrent_id,
                "name": episode_name,
                "date": date_str
            })

        logger.info(f"Найдено {len(episodes)} эпизодов для {series_url}")
        return episodes

    async def get_torrent_content(self, torrent_url: str) -> Optional[bytes]:
        """Загрузка содержимого торрент-файла."""
        if not torrent_url.startswith("http"):
            torrent_url = f"https://v6.astar.bz/{torrent_url}"
        
        loop = asyncio.get_event_loop()
        for attempt in range(self.max_retries):
            try:
                response = await loop.run_in_executor(None, lambda: self.scraper.get(torrent_url, headers=self.headers))
                if response.status_code == 200:
                    return response.content
                logger.warning(f"Попытка {attempt + 1}/{self.max_retries}: статус {response.status_code} для {torrent_url}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: ошибка при загрузке {torrent_url}: {e}")
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        logger.error(f"Не удалось загрузить торрент {torrent_url} после {self.max_retries} попыток")
        return None