import asyncio
import re
from qbittorrentapi import Client
import logging
import logging.handlers
from typing import List, Dict, Optional, Tuple
import os

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
    def __init__(self, client: Client):
        self.client = client

    async def add_torrent(self, torrent_content: bytes | str, save_path: str, torrent_id: str, rename_enabled: bool, series_name: str, season: str, socketio=None) -> Tuple[bool, str]:
        if not self.client:
            return False, "Нет подключения к qBittorrent"
        try:
            if isinstance(torrent_content, bytes):
                self.client.torrents_add(
                    torrent_files=torrent_content,
                    save_path=save_path,
                    category="",
                    is_paused=False,
                    use_auto_torrent_management=False,
                    content_layout="Original",
                    tags=[torrent_id]
                )
            elif isinstance(torrent_content, str) and torrent_content.startswith("magnet:"):
                self.client.torrents_add(
                    urls=torrent_content,
                    save_path=save_path,
                    category="",
                    is_paused=False,
                    use_auto_torrent_management=False,
                    content_layout="Original",
                    tags=[torrent_id]
                )
            else:
                return False, "Неподдерживаемый формат торрента"
            logger.info(f"Добавлен торрент с ID {torrent_id} в {save_path}")
            await asyncio.sleep(2)
            torrents = self.client.torrents_info()
            torrent_hash = next((t.hash for t in torrents if torrent_id in t.tags), None)
            if not torrent_hash:
                return True, f"Торрент добавлен, но не найден в списке (ID: {torrent_id})"
            if rename_enabled:
                await self.rename_torrent_files(torrent_hash, save_path, series_name, season, torrent_id, socketio)
            return True, f"Торрент добавлен: {series_name} в {save_path}"
        except Exception as e:
            logger.error(f"Ошибка добавления торрента {torrent_id}: {e}")
            return False, f"Ошибка: {e}"

    async def wait_for_completion(self, torrent_hash: str):
        while True:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if not torrents:
                logger.error(f"Торрент {torrent_hash} не найден")
                return False
            torrent = torrents[0]
            if torrent.progress == 1.0 or torrent.state in ["uploading", "stalledUP"]:
                logger.info(f"Торрент {torrent_hash} полностью загружен")
                return True
            await asyncio.sleep(10)

    def get_new_filename(self, old_name: str, series_name: str, season: str) -> Optional[str]:
        """Генерирует новое имя файла с учётом нового паттерна, сохраняя расширение."""
        patterns = [
            r"(\d{2})\.\s*(.+?)(?:\s*\(.*\))?$",  # "01. Name..."
            r".+\s+-\s+(\d{2})$",  # "Name - 06..."
            r'Серия\s+(\d+)', r'Серии\s+(\d+)-(\d+)', r'\s(\d+)\s', r'_(\d+)_',
            r'\[(\d+)\]', r'[eE](\d+)'
        ]
        resolution_patterns = [r'(720p)', r'(1080p)', r'(2160p)']

        # Разделяем путь, имя файла и расширение
        directory, filename = os.path.split(old_name)
        base_name, extension = os.path.splitext(filename)

        episode_num = None
        for pattern in patterns:
            match = re.search(pattern, base_name)
            if match:
                episode_num = match.group(1).zfill(2)
                break
    
        resolution = ''
        for res_pattern in resolution_patterns:
            match = re.search(res_pattern, base_name, re.IGNORECASE)
            if match:
                resolution = f" {match.group(1)}"
                break
    
        if episode_num:
            # Формируем новое имя с расширением, если оно есть
            new_name = f"{series_name} {season}e{episode_num}{resolution}{extension}"
            return os.path.join(directory, new_name) if directory else new_name
    
        logger.warning(f"Не удалось извлечь номер эпизода из {old_name}")
        return old_name  # Возвращаем исходное имя, если паттерн не найден

    async def rename_torrent_files(self, torrent_hash: str, save_path: str, series_name: str, season: str, torrent_id: str, socketio=None):
        if not self.client:
            raise Exception("Нет подключения к qBittorrent")
        if not await self.wait_for_completion(torrent_hash):
            raise Exception("Торрент не загружен полностью")
        try:
            qb_torrents = self.client.torrents_info()
            target_torrent = next((t for t in qb_torrents if t.hash == torrent_hash and torrent_id in t.tags), None)
            if not target_torrent:
                logger.warning(f"Не найдено торрента с хэшем {torrent_hash} и ID {torrent_id}")
                raise Exception(f"Торрент не найден или ID не совпадает")
            
            logger.info(f"Выполняется переименование файлов торрента с хэшем {torrent_hash} и ID {torrent_id}")
            files = self.client.torrents_files(torrent_hash=torrent_hash)
            if not files:
                logger.warning(f"Нет файлов для переименования в торренте {torrent_hash}")
                return

            for file in files:
                new_name = self.get_new_filename(file.name, series_name, season)
                if new_name and file.name != new_name:
                    for other_torrent in qb_torrents:
                        if other_torrent.hash != torrent_hash and other_torrent.save_path == save_path:
                            other_files = self.client.torrents_files(torrent_hash=other_torrent.hash)
                            if any(of.name == new_name for of in other_files):
                                self.client.torrents_delete(delete_files=True, torrent_hashes=other_torrent.hash)
                                logger.info(f"Удалён старый торрент {other_torrent.name} для замены на {new_name}")
                    self.client.torrents_rename_file(torrent_hash=torrent_hash, old_path=file.name, new_path=new_name)
                    logger.info(f"Переименован: {file.name} -> {new_name}")
                    if socketio:
                        socketio.emit('notification', {'message': f"Переименован: {file.name} -> {new_name}", 'type': 'info'})
                else:
                    logger.info(f"Файл {file.name} не требует переименования или паттерн не найден")
        except Exception as e:
            logger.error(f"Ошибка при переименовании торрента {torrent_hash} с ID {torrent_id}: {str(e)}")
            raise

    async def get_torrent_files(self, save_path: str) -> List[Dict[str, str]]:
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

    def get_torrent_status(self, torrent_hash: str) -> Optional[Dict[str, str]]:
        if not self.client:
            return None
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if not torrents:
                return None
            torrent = torrents[0]
            status_map = {
                'downloading': 'Загружается',
                'uploading': 'Скачан',
                'stalledDL': 'В очереди',
                'stalledUP': 'Скачан',
                'pausedDL': 'Пауза',
                'pausedUP': 'Скачан (Пауза)',
                'queuedDL': 'В очереди',
                'queuedUP': 'Скачан (В очереди)',
                'checkingDL': 'Проверка',
                'checkingUP': 'Проверка',
                'error': 'Ошибка'
            }
            return {
                "state": status_map.get(torrent.state, "Неизвестно"),
                "completed": torrent.progress == 1.0 or torrent.state in ["uploading", "stalledUP"]
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса торрента {torrent_hash}: {e}")
            return None