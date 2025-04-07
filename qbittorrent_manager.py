import asyncio
import re
from qbittorrentapi import Client, LoginFailed
import logging
import logging.handlers
from typing import List, Dict, Optional, Tuple

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

class QBittorrentManager:
    def __init__(self, host: str, username: str, password: str, max_retries: int = 3):
        self.host = host
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.client = None

    async def connect(self) -> Tuple[bool, str]:
        """Подключение к qBittorrent с повторными попытками."""
        for attempt in range(self.max_retries):
            try:
                self.client = Client(
                    host=self.host,
                    username=self.username,
                    password=self.password,
                    VERIFY_WEBUI_CERTIFICATE=False
                )
                self.client.auth_log_in()
                version = self.client.app.version
                logger.info(f"Подключено к qBittorrent, версия: {version}")
                return True, f"Подключено (версия: {version})"
            except LoginFailed as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: Ошибка входа: {e}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries}: Ошибка подключения: {e}")
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        self.client = None
        return False, "Не удалось подключиться к qBittorrent"

    def disconnect(self):
        """Отключение от qBittorrent."""
        if self.client:
            self.client.auth_log_out()
            logger.info("Отключено от qBittorrent")
            self.client = None

    async def add_torrent(self, torrent_content: bytes, save_path: str, torrent_id: str, rename_enabled: bool, series_name: str, season: str, socketio=None) -> Tuple[bool, str]:
        """Добавление торрента в qBittorrent."""
        if not self.client:
            return False, "Нет подключения к qBittorrent"

        try:
            self.client.torrents_add(
                torrent_files=torrent_content,
                save_path=save_path,
                category="",
                is_paused=False,
                use_auto_torrent_management=False,
                content_layout="Original",
                tags=[torrent_id]
            )
            logger.info(f"Добавлен торрент с ID {torrent_id} в {save_path}")
            await asyncio.sleep(2)  # Даем время qBittorrent обработать торрент

            torrents = self.client.torrents_info()
            torrent_hash = next((t.hash for t in torrents if torrent_id in t.tags), None)
            if not torrent_hash:
                return True, f"Торрент добавлен, но не найден в списке (ID: {torrent_id})"

            if rename_enabled:
                await self.rename_torrent_files(torrent_hash, save_path, series_name, season, socketio)
            return True, f"Торрент добавлен: {series_name} в {save_path}"
        except Exception as e:
            logger.error(f"Ошибка добавления торрента {torrent_id}: {e}")
            return False, f"Ошибка: {e}"

    def get_new_filename(self, old_name: str, series_name: str, season: str) -> Optional[str]:
        """Генерация нового имени файла на основе паттернов."""
        patterns = [
            r'Серия\s+(\d+)',          # "Серия 5"
            r'Серии\s+(\d+)-(\d+)',    # "Серии 1-3" (берем первый номер)
            r'\s(\d+)\s',              # " 5 "
            r'\.(\d+)\.',              # ".5."
            r'_(\d+)_',                # "_5_"
            r'\[(\d+)\]',              # "[5]"
            r'[eE](\d+)',              # "e5"
        ]
        resolution_patterns = [
            r'(720p)',
            r'(1080p)',
            r'(2160p)'
        ]

        base_name, ext = old_name.rsplit('.', 1) if '.' in old_name else (old_name, '')
        episode_num = None
        for pattern in patterns:
            match = re.search(pattern, base_name)
            if match:
                episode_num = match.group(1).zfill(2)  # "5" -> "05"
                break

        resolution = ''
        for res_pattern in resolution_patterns:
            match = re.search(res_pattern, base_name, re.IGNORECASE)
            if match:
                resolution = f" {match.group(1)}"
                break

        if episode_num:
            return f"{series_name} {season}e{episode_num}{resolution}.{ext}"
        logger.warning(f"Не удалось извлечь номер эпизода из {old_name}")
        return None

    async def rename_torrent_files(self, torrent_hash: str, save_path: str, series_name: str, season: str, socketio=None):
        """Переименование файлов торрента."""
        if not self.client:
            logger.error("Нет подключения к qBittorrent для переименования")
            raise Exception("Нет подключения к qBittorrent")

        try:
            qb_torrents = self.client.torrents_info()
            target_torrents = [t for t in qb_torrents if t.save_path == save_path] if not torrent_hash else [t for t in qb_torrents if t.hash == torrent_hash]
            
            if not target_torrents:
                logger.warning(f"Не найдено торрентов для пути {save_path} или хеша {torrent_hash}")
                raise Exception(f"Не найдено торрентов для переименования по пути {save_path}")

            for torrent in target_torrents:
                logger.info(f"Выполняется переименование файлов торрента с тегами {torrent.tags}")
                files = self.client.torrents_files(torrent_hash=torrent.hash)
                if not files:
                    logger.warning(f"Нет файлов для переименования в торренте {torrent.hash}")
                    continue
                for file in files:
                    new_name = self.get_new_filename(file.name, series_name, season)
                    if new_name and file.name != new_name:
                        for other_torrent in qb_torrents:
                            if other_torrent.hash != torrent.hash and other_torrent.save_path == save_path:
                                other_files = self.client.torrents_files(torrent_hash=other_torrent.hash)
                                if any(of.name == new_name for of in other_files):
                                    self.client.torrents_delete(delete_files=True, torrent_hashes=other_torrent.hash)
                                    logger.info(f"Удален старый торрент {other_torrent.name} для замены на {new_name}")
                        self.client.torrents_rename_file(torrent_hash=torrent.hash, old_path=file.name, new_path=new_name)
                        logger.info(f"Переименован: {file.name} -> {new_name}")
                        if socketio:  # Отправляем уведомление
                            socketio.emit('notification', {'message': f"Переименован: {file.name} -> {new_name}", 'type': 'info'})
                    else:
                        logger.info(f"Файл {file.name} не требует переименования или паттерн не найден")
        except Exception as e:
            logger.error(f"Ошибка при переименовании торрента {torrent_hash}: {str(e)}")
            raise

    async def get_torrent_files(self, save_path: str) -> List[Dict[str, str]]:
        """Получение списка файлов для предпросмотра переименования."""
        if not self.client:
            logger.error("Нет подключения к qBittorrent для получения файлов")
            return [{"current_name": "Ошибка", "new_name": "Нет подключения к qBittorrent"}]
        
        try:
            qb_torrents = self.client.torrents_info()
            files_list = []
            for torrent in qb_torrents:
                if torrent.save_path == save_path:
                    files = self.client.torrents_files(torrent_hash=torrent.hash)
                    for file in files:
                        files_list.append({"current_name": file.name})
            if not files_list:
                logger.warning(f"Не найдено файлов для пути {save_path}")
                return [{"current_name": "Нет файлов", "new_name": "Торренты не найдены"}]
            return files_list
        except Exception as e:
            logger.error(f"Ошибка при получении файлов торрентов: {e}")
            return [{"current_name": "Ошибка", "new_name": str(e)}]