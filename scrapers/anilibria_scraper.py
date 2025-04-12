import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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

            # Сохранение HTML для отладки, если включено
            if DEBUG_SAVE_HTML:
                url_hash = hashlib.md5(series_url.encode()).hexdigest()[:8]
                debug_filename = f"debug_anilibria_{url_hash}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"HTML страницы {series_url} сохранён в {debug_filename}")

            # Парсинг с использованием lxml
            tree = html.fromstring(html_content)

            # Извлечение названия сериала
            title_elem = tree.xpath('//div[@class="fz-70 ff-heading text-grey-darken-2 mb-3"]/text()')
            if not title_elem:
                logger.error(f"Название сериала не найдено для {series_url}")
                raise Exception("Название сериала не найдено")
            series_name = title_elem[0].strip()
            # Удаляем суффикс "2nd Season" или аналогичные
            series_name = series_name.replace(" 2nd Season", "").replace(" 1st Season", "").replace(" 3rd Season", "")

            # Извлечение данных о торрентах
            torrent_items = tree.xpath('//div[contains(@class, "v-list-item--density-default v-list-item--one-line")]')
            episodes = []
            for item in torrent_items:
                # Качество
                quality_elem = item.xpath('.//div[@class="fz-65 text-grey-darken-2"]/text()')
                if not quality_elem:
                    continue
                quality_text = quality_elem[0].strip().replace(" • ", " ")

                # Если указано качество и оно не совпадает, пропускаем
                if quality and quality_text != quality:
                    continue

                # Дата обновления
                date_elem = item.xpath('.//div[@class="fz-75 text-grey" and contains(text(), ",")]/text()')
                if not date_elem:
                    logger.error(f"Дата обновления не найдена для {series_url}, качество {quality_text}")
                    continue
                date_text = date_elem[0].strip()
                try:
                    last_updated = datetime.strptime(date_text, "%d.%m.%Y, %H:%M:%S").isoformat()
                except ValueError as e:
                    logger.error(f"Ошибка парсинга даты {date_text}: {e}")
                    continue

                # Magnet-ссылка
                magnet_elem = item.xpath('.//a[contains(@href, "magnet:")]/@href')
                if not magnet_elem:
                    logger.error(f"Magnet-ссылка не найдена для {series_url}, качество {quality_text}")
                    continue
                magnet_link = magnet_elem[0]

                # Torrent ID
                torrent_id = hashlib.md5(f"{series_url}_{quality_text}".encode()).hexdigest()[:8]

                episodes.append({
                    "name": series_name,
                    "torrent_url": series_url,
                    "torrent_id": torrent_id,
                    "magnet_link": magnet_link,
                    "quality": quality_text,
                    "last_updated": last_updated
                })

            if not episodes:
                logger.warning(f"Эпизоды не найдены для {series_url}")
                return []

            logger.info(f"Получено {len(episodes)} эпизодов для {series_url}")
            return episodes

        except Exception as e:
            logger.error(f"Ошибка при получении эпизодов для {series_url}: {e}")
            return []
        finally:
            self._quit_driver()

    async def get_torrent_content(self, torrent_url: str):
        # Этот метод теперь не нужен, так как magnet-ссылки извлекаются напрямую
        logger.warning(f"Метод get_torrent_content не используется для {torrent_url}, magnet-ссылки извлекаются в get_episodes")
        return None

    async def scan_series(self, series_url: str):
        self._init_driver()
        try:
            self.driver.get(series_url)
            await asyncio.sleep(10)
            html_content = self.driver.page_source

            # Сохранение HTML для отладки, если включено
            if DEBUG_SAVE_HTML:
                url_hash = hashlib.md5(series_url.encode()).hexdigest()[:8]
                debug_filename = f"debug_anilibria_{url_hash}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"HTML страницы {series_url} сохранён в {debug_filename}")

            # Парсинг с использованием lxml
            tree = html.fromstring(html_content)

            # Извлечение названия сериала
            title_elem = tree.xpath('//div[@class="fz-70 ff-heading text-grey-darken-2 mb-3"]/text()')
            if not title_elem:
                logger.error(f"Название сериала не найдено для {series_url}")
                return {"name": "Ошибка", "quality_options": []}
            series_name = title_elem[0].strip()
            series_name = series_name.replace(" 2nd Season", "").replace(" 1st Season", "").replace(" 3rd Season", "")

            # Извлечение вариантов качества
            quality_elems = tree.xpath('//div[@class="fz-65 text-grey-darken-2"]/text()')
            quality_options = []
            for quality_text in quality_elems:
                formatted_quality = quality_text.strip().replace(" • ", " ")
                quality_options.append({"link": "", "quality": formatted_quality})

            if not quality_options:
                logger.warning(f"Варианты качества не найдены для {series_url}")
                quality_options = [{"link": "", "quality": "Не найдено"}]

            logger.info(f"Найдено {len(quality_options)} вариантов качества для {series_url}: {quality_options}")
            return {
                "name": series_name,
                "quality_options": quality_options
            }

        except Exception as e:
            logger.error(f"Ошибка при сканировании серии: {e}")
            return {"name": "Ошибка", "quality_options": []}
        finally:
            self._quit_driver()