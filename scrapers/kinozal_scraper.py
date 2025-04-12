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

class KinozalScraper:
    def __init__(self, username=None, password=None):
        self.session = requests.Session()
        self.login_url = "https://kinozal.tv/takelogin.php"
        self.base_download_url = "https://dl.kinozal.tv/download.php?id="
        self.username = username
        self.password = password
        if username and password:
            self.login()

    def login(self):
        """Авторизация на сайте."""
        login_data = {
            "username": self.username,
            "password": self.password,
            "returnto": ""
        }
        response = self.session.post(self.login_url, data=login_data)
        response.encoding = "windows-1251"
        if response.url.startswith(self.login_url) or "uid" not in self.session.cookies:
            raise Exception("Ошибка авторизации на kinozal.tv")
        logger.info("Успешная авторизация на kinozal.tv")

    def get_torrent_id(self, url):
        """Извлечение ID торрента из URL."""
        match = re.search(r'id=(\d+)', url)
        if match:
            return match.group(1)
        raise ValueError("Неверный URL для kinozal.tv")

    async def get_episodes(self, series_url, quality=None):
        """Получение данных о раздаче с сохранением HTML для отладки, если включено."""
        if not self.username or not self.password:
            raise Exception("Требуется авторизация для kinozal.tv")
        
        response = await asyncio.to_thread(self.session.get, series_url)
        if response.status_code != 200:
            logger.error(f"Ошибка загрузки страницы {series_url}: {response.status_code}")
            raise Exception(f"Не удалось загрузить страницу: {response.status_code}")
        
        response.encoding = "windows-1251"
        html_content = response.text
        
        if DEBUG_SAVE_HTML:
            debug_filename = f"debug_kinozal_{self.get_torrent_id(series_url)}.html"
            with open(debug_filename, "w", encoding="windows-1251") as f:
                f.write(html_content)
            logger.info(f"HTML страницы {series_url} сохранён в {debug_filename}")
        
        tree = html.fromstring(html_content)
        update_date_text = tree.xpath('//li[contains(., "Обновлен")]//span[contains(@class, "green n")]/text()')
        
        if not update_date_text:
            available_li = tree.xpath('//li/text()')
            logger.error(f"Дата обновления не найдена для {series_url}. Доступные <li>: {', '.join([text.strip() for text in available_li if text.strip()])}")
            raise Exception("Дата обновления не найдена")
        
        date_text = update_date_text[0].strip()
        logger.info(f"Найденная дата обновления: {date_text}")
        
        # Преобразуем дату
        current_date = datetime.now().date()
        months = {
            'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04', 'мая': '05', 'июня': '06',
            'июля': '07', 'августа': '08', 'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
        }
        
        if "сегодня" in date_text.lower():
            time_match = re.search(r"(\d{2}:\d{2})", date_text)
            if not time_match:
                logger.error(f"Не удалось извлечь время из {date_text}")
                raise Exception("Не удалось извлечь время из даты обновления")
            updated_time = datetime.strptime(time_match.group(1), "%H:%M").time()
            last_updated = datetime.combine(current_date, updated_time)
        elif "вчера" in date_text.lower():
            time_match = re.search(r"(\d{2}:\d{2})", date_text)
            if not time_match:
                logger.error(f"Не удалось извлечь время из {date_text}")
                raise Exception("Не удалось извлечь время из даты обновления")
            updated_time = datetime.strptime(time_match.group(1), "%H:%M").time()
            last_updated = datetime.combine(current_date.replace(day=current_date.day - 1), updated_time)
        else:
            # Формат: "10 апреля 2025 в 13:26"
            match = re.match(r"(\d{1,2})\s+([а-яА-Я]+)\s+(\d{4})\s+в\s+(\d{2}:\d{2})", date_text)
            if not match:
                logger.error(f"Неизвестный формат даты: {date_text}")
                raise Exception("Неизвестный формат даты обновления")
            day, month_name, year, time = match.groups()
            month = months.get(month_name.lower())
            if not month:
                logger.error(f"Неизвестный месяц в дате: {month_name}")
                raise Exception("Неизвестный месяц в дате обновления")
            last_updated = datetime.strptime(f"{day.zfill(2)}.{month}.{year} {time}", "%d.%m.%Y %H:%M")
        
        torrent_id = self.get_torrent_id(series_url)
        return [{
            "name": "Полный сезон",
            "torrent_id": torrent_id,
            "torrent_url": series_url,
            "last_updated": last_updated.isoformat()
        }]

    async def get_torrent_content(self, torrent_url):
        """Скачивание торрент-файла."""
        torrent_id = self.get_torrent_id(torrent_url)
        download_url = f"{self.base_download_url}{torrent_id}"
        headers = {"Referer": torrent_url}
        response = await asyncio.to_thread(self.session.get, download_url, headers=headers)
        if response.status_code == 200:
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
        title_elem = tree.xpath('//h1[@class="mn1"]/text()')
        series_name = title_elem[0].strip() if title_elem else "Неизвестно"

        logger.info(f"Найдено вариантов качества для {series_url}: отсутствуют")
        return {
            "name": series_name,
            "names": [series_name],
            "quality_options": []
        }