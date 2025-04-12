import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from urllib.parse import urlparse
from datetime import datetime
from qbittorrent_manager import QBittorrentManager  # Добавляем импорт

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def find_series_data(series_url, config):
    parsed_url = urlparse(series_url)
    series_domain = parsed_url.netloc
    series_path = parsed_url.path
    for url, data in config.get("series", {}).items():
        if series_domain in url and series_path in url:
            return data
    return None

async def scan_series(series_url, socketio, auth_manager, config):
    series_data = find_series_data(series_url, config)
    if not series_data:
        logger.error(f"Сериал {series_url} не найден в конфигурации")
        socketio.emit('status_update', {'series_url': series_url, 'status': 'Ошибка: сериал не найден', 'progress': 0, 'total': 0})
        return
    logger.info(f"Начинаем сканирование для {series_url} с данными: {series_data}")
    socketio.emit('status_update', {'series_url': series_url, 'status': 'Сканирование', 'progress': 0, 'total': 0})
    scraper = auth_manager.get_scraper(series_url)
    if not scraper:
        logger.error(f"Парсер не найден для {series_url}")
        socketio.emit('status_update', {'series_url': series_url, 'status': 'Ошибка: парсер не найден', 'progress': 0, 'total': 0})
        return
    try:
        episodes = await scraper.get_episodes(series_url, quality=series_data.get("quality"))
        logger.info(f"Получено {len(episodes)} эпизодов для {series_url}")
    except Exception as e:
        logger.error(f"Ошибка при получении эпизодов для {series_url}: {str(e)}")
        socketio.emit('status_update', {'series_url': series_url, 'status': f'Ошибка: {str(e)}', 'progress': 0, 'total': 0})
        return
    total_steps = len(episodes) * 2
    if not episodes:
        logger.info(f"Завершено: эпизодов нет для {series_url}")
        socketio.emit('status_update', {'series_url': series_url, 'status': 'Завершено: эпизодов нет', 'progress': 0, 'total': 0})
        return
    qb_client = auth_manager.get_qb_client()
    qb_manager = QBittorrentManager(qb_client) if qb_client else None  # Создаём qb_manager
    if not qb_manager:
        logger.error(f"Не удалось подключиться к qBittorrent для {series_url}")
        socketio.emit('status_update', {'series_url': series_url, 'status': 'Ошибка: нет подключения к qBittorrent', 'progress': 0, 'total': 0})
        return
    qb_torrents = qb_client.torrents_info() if qb_client else []
    progress = 0
    for episode in episodes:
        torrent = next((t for t in qb_torrents if episode["torrent_id"] in t.tags), None)
        last_updated = datetime.fromisoformat(episode["last_updated"]) if episode["last_updated"] else None
        saved_updated = datetime.fromisoformat(series_data.get("last_updated")) if series_data.get("last_updated") else None
        
        should_download = not torrent or (last_updated and saved_updated and last_updated > saved_updated)
        if should_download:
            progress += 1
            logger.info(f"Добавление: {episode['name']} для {series_url}")
            socketio.emit('status_update', {'series_url': series_url, 'status': f"Добавление: {episode['name']}", 'progress': progress, 'total': total_steps})
            content = episode.get("magnet_link") or await scraper.get_torrent_content(episode["torrent_url"])
            if content:
                success, msg = await qb_manager.add_torrent(
                    content, series_data["save_path"], episode["torrent_id"],
                    series_data["rename_enabled"], series_data["series_name"], series_data["season"],
                    socketio=socketio
                )
                if success:
                    config.config["series"][series_url]["last_updated"] = episode["last_updated"]
                    config.save_config()
                socketio.emit('notification', {'message': msg, 'type': 'info'})
                progress += 1
            else:
                logger.error(f"Не удалось получить содержимое торрента для {episode['torrent_url']}")
        elif series_data.get("rename_enabled", False) and torrent:
            status = qb_manager.get_torrent_status(torrent.hash)
            if status and status["completed"]:
                await qb_manager.rename_torrent_files(torrent.hash, series_data["save_path"], series_data["series_name"], series_data["season"], episode["torrent_id"], socketio)
                socketio.emit('status_update', {'series_url': series_url, 'status': 'Переименование завершено', 'progress': progress, 'total': total_steps})
    logger.info(f"Завершено сканирование для {series_url}")
    socketio.emit('status_update', {'series_url': series_url, 'status': 'Завершено', 'progress': total_steps, 'total': total_steps})

def run_scan_series(series_url, socketio, auth_manager, config):
    try:
        logger.info(f"Запуск сканирования в потоке для {series_url}")
        asyncio.run(scan_series(series_url, socketio, auth_manager, config))
    except Exception as e:
        logger.error(f"Ошибка в потоке сканирования для {series_url}: {str(e)}", exc_info=True)

async def monitor_task(socketio, auth_manager, config):
    try:
        series = config.get("series", {})
        logger.info(f"Запуск мониторинга для {len(series)} сериалов")
        for series_url in series:
            scraper = auth_manager.get_scraper(series_url)
            if scraper:
                await scan_series(series_url, socketio, auth_manager, config)
            else:
                logger.error(f"Парсер не найден для {series_url}")
        logger.info("Мониторинг завершён")
    except Exception as e:
        logger.error(f"Ошибка в monitor_task: {str(e)}", exc_info=True)

def setup_scheduler(socketio, auth_manager, config):
    scheduler.add_job(
        lambda: asyncio.run(monitor_task(socketio, auth_manager, config)),
        'interval',
        minutes=config.get("scan_interval", 30),
        id='monitor_task'
    )
    logger.info("Задача мониторинга добавлена в планировщик")