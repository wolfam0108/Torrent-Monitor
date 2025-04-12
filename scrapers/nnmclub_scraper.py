import requests
from lxml import html
import logging
from datetime import datetime
import re
import asyncio
import os

logger = logging.getLogger(__name__)

DEBUG_SAVE_HTML = True

class NnmClubScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://nnmclub.to/",
            "Upgrade-Insecure-Requests": "1"
        })

    def get_torrent_id(self, url):
        """Извлечение ID торрента из URL."""
        match = re.search(r't=(\d+)', url)
        if match:
            return match.group(1)
        raise ValueError("Неверный URL для nnmclub.to")

    async def get_episodes(self, series_url, quality=None):
        """Получение данных о раздаче с сохранением HTML для отладки."""
        for attempt in range(3):
            try:
                response = await asyncio.to_thread(self.session.get, "https://nnmclub.to/")
                if response.status_code != 200:
                    logger.warning(f"Не удалось загрузить главную страницу nnmclub.to: {response.status_code}")
                
                response = await asyncio.to_thread(self.session.get, series_url)
                if response.status_code != 200:
                    logger.error(f"Ошибка загрузки страницы {series_url}: {response.status_code}")
                    raise Exception(f"Не удалось загрузить страницу: {response.status_code}")
                
                response.encoding = "windows-1251"
                html_content = response.text
                
                if DEBUG_SAVE_HTML:
                    debug_filename = f"debug_nnmclub_{self.get_torrent_id(series_url)}.html"
                    with open(debug_filename, "w", encoding="windows-1251") as f:
                        f.write(html_content)
                    logger.info(f"HTML страницы {series_url} сохранён в {debug_filename}")
                
                tree = html.fromstring(response.content)
                
                magnet_link = tree.xpath('//a[starts-with(@href, "magnet:")]/@href')
                if not magnet_link:
                    logger.error(f"Magnet-ссылка не найдена для {series_url}")
                    raise Exception("Magnet-ссылка не найдена")
                magnet_link = magnet_link[0]
                
                date_elements = tree.xpath('//tr[@class="row1"]//td[contains(text(), "Зарегистрирован:")]/following-sibling::td/text()')
                if not date_elements:
                    logger.error(f"Дата обновления не найдена для {series_url}")
                    raise Exception("Дата обновления не найдена")
                
                date_text = date_elements[0].strip()
                logger.info(f"Найденная дата обновления: {date_text}")
                
                try:
                    months = {
                        'Янв': '01', 'Фев': '02', 'Мар': '03', 'Апр': '04', 'Май': '05', 'Июн': '06',
                        'Июл': '07', 'Авг': '08', 'Сен': '09', 'Окт': '10', 'Ноя': '11', 'Дек': '12'
                    }
                    day, month_abbr, year, time = date_text.split()
                    month = months[month_abbr]
                    last_updated = datetime.strptime(f"{day}.{month}.{year} {time}", "%d.%m.%Y %H:%M:%S")
                except (ValueError, KeyError) as e:
                    logger.error(f"Ошибка парсинга даты: {date_text}, ошибка: {e}")
                    raise Exception(f"Ошибка парсинга даты: {e}")
                
                torrent_id = self.get_torrent_id(series_url)
                return [{
                    "name": "Полный сезон",
                    "torrent_id": torrent_id,
                    "magnet_link": magnet_link,
                    "last_updated": last_updated.isoformat()
                }]
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/3: Ошибка для {series_url}: {e}")
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise Exception("Не удалось получить эпизоды после 3 попыток")

    async def get_torrent_content(self, torrent_url):
        """Получение magnet-ссылки."""
        episodes = await self.get_episodes(torrent_url)
        return episodes[0]["magnet_link"]

    async def scan_series(self, series_url: str):
        """Получение метаданных сериала."""
        for attempt in range(3):
            try:
                response = await asyncio.to_thread(self.session.get, "https://nnmclub.to/")
                if response.status_code != 200:
                    logger.warning(f"Не удалось загрузить главную страницу nnmclub.to: {response.status_code}")
                
                response = await asyncio.to_thread(self.session.get, series_url)
                if response.status_code != 200:
                    logger.error(f"Ошибка загрузки страницы {series_url}: {response.status_code}")
                    raise Exception(f"Не удалось загрузить страницу: {response.status_code}")
                
                response.encoding = "windows-1251"
                html_content = response.text
                
                if DEBUG_SAVE_HTML:
                    debug_filename = f"debug_nnmclub_{self.get_torrent_id(series_url)}.html"
                    with open(debug_filename, "w", encoding="windows-1251") as f:
                        f.write(html_content)
                    logger.info(f"HTML страницы {series_url} сохранён в {debug_filename}")
                
                tree = html.fromstring(response.content)
                title_elem = tree.xpath('//h1[@class="maintitle"]/text()')
                series_name = title_elem[0].strip() if title_elem else "Неизвестно"
                
                logger.info(f"Найдено вариантов качества для {series_url}: отсутствуют")
                return {
                    "name": series_name,
                    "names": [series_name],
                    "quality_options": []
                }
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/3: Ошибка для {series_url}: {e}")
                if attempt == 2:
                    return {"name": "Ошибка", "quality_options": []}
                await asyncio.sleep(2 ** attempt)
        return {"name": "Ошибка", "quality_options": []}