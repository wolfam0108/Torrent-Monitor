import requests
from lxml import html
import logging
from datetime import datetime
import re
import asyncio
import os

logger = logging.getLogger(__name__)

# Флаг для включения/отключения сохранения HTML для отладки
DEBUG_SAVE_HTML = False

class RutrackerScraper:
    def __init__(self, username=None, password=None):
        self.session = requests.Session()
        self.login_url = "https://rutracker.org/forum/login.php"
        self.base_download_url = "https://rutracker.org/forum/dl.php?t="
        self.username = username
        self.password = password
        if username and password:
            self.login()

    def login(self):
        """Авторизация на сайте."""
        login_data = {
            "login_username": self.username.encode('windows-1251'),
            "login_password": self.password.encode('windows-1251'),
            "login": "%E2%F5%EE%E4"
        }
        response = self.session.post(self.login_url, data=login_data)
        response.encoding = "windows-1251"
        if response.url.startswith(self.login_url) or "bb_session" not in self.session.cookies:
            raise Exception("Ошибка авторизации на rutracker.org")
        logger.info("Успешная авторизация на rutracker.org")

    def get_torrent_id(self, url):
        """Извлечение ID торрента из URL."""
        match = re.search(r't=(\d+)', url)
        if match:
            return match.group(1)
        raise ValueError("Неверный URL для rutracker.org")

    async def get_episodes(self, series_url, quality=None):
        """Получение данных о раздаче с сохранением HTML для отладки, если включено."""
        if not self.username or not self.password:
            raise Exception("Требуется авторизация для rutracker.org")
        
        response = await asyncio.to_thread(self.session.get, series_url)
        if response.status_code != 200:
            logger.error(f"Ошибка загрузки страницы {series_url}: {response.status_code}")
            raise Exception(f"Не удалось загрузить страницу: {response.status_code}")
        
        # Принудительно декодируем как windows-1251
        response.encoding = "windows-1251"
        html_content = response.text
        
        # Сохраняем HTML для отладки, если DEBUG_SAVE_HTML включён
        if DEBUG_SAVE_HTML:
            debug_filename = f"debug_rutracker_{self.get_torrent_id(series_url)}.html"
            with open(debug_filename, "w", encoding="windows-1251") as f:
                f.write(html_content)
            logger.info(f"HTML страницы {series_url} сохранён в {debug_filename}")
        
        # Парсим с помощью lxml
        tree = html.fromstring(response.content)
        
        # Проверяем обновление через <span class="post-b torrent-updated">
        updated_elem = tree.xpath('//span[contains(@class, "post-b torrent-updated")]/following-sibling::a[contains(@class, "torTopic")]/text()')
        if updated_elem:
            date_text = updated_elem[0].strip()
            logger.info(f"Найденная дата обновления через span: {date_text}")
            last_updated = datetime.strptime(date_text, "%d-%b-%y %H:%M").replace(year=2025)
        else:
            # Fallback на "Зарегистрирован:"
            date_elem = tree.xpath('//tr[@class="row1"]//td[contains(text(), "Зарегистрирован:")]/following-sibling::td//li[1]/text()')
            if not date_elem:
                logger.error(f"Дата обновления не найдена для {series_url}")
                raise Exception("Дата обновления не найдена")
            date_text = date_elem[0].strip()
            logger.info(f"Найденная дата обновления через td: {date_text}")
            try:
                months = {
                    'Янв': '01', 'Фев': '02', 'Мар': '03', 'Апр': '04', 'Май': '05', 'Июн': '06',
                    'Июл': '07', 'Авг': '08', 'Сен': '09', 'Окт': '10', 'Ноя': '11', 'Дек': '12'
                }
                # Разделяем строку на дату и время (например, "09-Апр-25 16:08")
                date_part, time_part = date_text.split(" ", 1)
                day, month_abbr, year = date_part.split("-")
                month = months[month_abbr]
                year = f"20{year}"  # Преобразуем "25" в "2025"
                last_updated = datetime.strptime(f"{day}.{month}.{year} {time_part}", "%d.%m.%Y %H:%M")
            except (ValueError, KeyError) as e:
                logger.error(f"Ошибка парсинга даты: {date_text}, ошибка: {e}")
                raise Exception(f"Ошибка парсинга даты: {e}")
        
        torrent_id = self.get_torrent_id(series_url)
        return [{
            "name": "Полный сезон",
            "torrent_id": torrent_id,
            "torrent_url": f"{self.base_download_url}{torrent_id}",
            "last_updated": last_updated.isoformat()
        }]

    async def get_torrent_content(self, torrent_url):
        """Скачивание торрент-файла."""
        headers = {"Referer": "https://rutracker.org/forum/viewtopic.php?t=" + self.get_torrent_id(torrent_url)}
        response = await asyncio.to_thread(self.session.post, torrent_url, headers=headers)
        if response.status_code == 200 and "text/html" not in response.headers.get("Content-Type", ""):
            logger.info(f"Торрент-файл успешно получен для {torrent_url}")
            return response.content
        logger.error(f"Ошибка скачивания торрента {torrent_url}: {response.status_code}")
        raise Exception(f"Ошибка скачивания: {response.status_code}")
        
    async def scan_series(self, series_url: str):
        # Этот метод не использует сохранение HTML, поэтому изменений не требуется
        response = await asyncio.to_thread(self.session.get, series_url)
        if response.status_code != 200:
            return {"name": "Ошибка", "quality_options": []}

        response.encoding = "windows-1251"
        tree = html.fromstring(response.content)
        title_elem = tree.xpath('//h1[@class="maintitle"]/text()')
        series_name = title_elem[0].strip() if title_elem else "Неизвестно"

        logger.info(f"Найдено вариантов качества для {series_url}: отсутствуют")
        return {
            "name": series_name,
            "names": [series_name],
            "quality_options": []
        }