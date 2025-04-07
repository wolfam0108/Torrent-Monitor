import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from scraper import AstarBzScraper
import logging

config = Config()
scraper = AstarBzScraper()
scheduler = BackgroundScheduler()
logger = logging.getLogger(__name__)

async def scan_series(series_url, socketio, qb_manager):
    series_data = config.get("series").get(series_url)
    if not series_data:
        logger.info(f"Отправка статуса: Ошибка для {series_url}")
        socketio.emit('status_update', {'series_url': series_url, 'status': 'Ошибка', 'progress': 0, 'total': 0})
        return

    logger.info(f"Отправка статуса: Сканирование для {series_url}")
    socketio.emit('status_update', {'series_url': series_url, 'status': 'Сканирование', 'progress': 0, 'total': 0})
    episodes = await scraper.get_episodes(series_url)
    total_steps = len(episodes) * 2
    if not episodes:
        logger.info(f"Отправка статуса: Завершено: эпизодов нет для {series_url}")
        socketio.emit('status_update', {'series_url': series_url, 'status': 'Завершено: эпизодов нет', 'progress': 0, 'total': 0})
        return

    qb_torrents = qb_manager.client.torrents_info() if qb_manager.client else []
    progress = 0

    for episode in episodes:
        if not any(episode["torrent_id"] in t.tags for t in qb_torrents):
            progress += 1
            logger.info(f"Отправка статуса: Добавление: {episode['name']} для {series_url}")
            socketio.emit('status_update', {'series_url': series_url, 'status': f"Добавление: {episode['name']}", 'progress': progress, 'total': total_steps})
            content = await scraper.get_torrent_content(episode["torrent_url"])
            if content:
                success, msg = await qb_manager.add_torrent(
                    content, series_data["save_path"], episode["torrent_id"],
                    series_data["rename_enabled"], series_data["series_name"], series_data["season"],
                    socketio=socketio  # Передаём socketio для уведомлений
                )
                socketio.emit('notification', {'message': msg, 'type': 'info'})  # Уведомление о добавлении
                progress += 1
                logger.info(f"Отправка статуса: Переименование: {episode['name']} для {series_url}")
                socketio.emit('status_update', {'series_url': series_url, 'status': f"Переименование: {episode['name']}", 'progress': progress, 'total': total_steps})
    
    logger.info(f"Отправка статуса: Завершено для {series_url}")
    socketio.emit('status_update', {'series_url': series_url, 'status': 'Завершено', 'progress': total_steps, 'total': total_steps})

def run_scan_series(series_url, socketio, qb_manager):
    asyncio.run(scan_series(series_url, socketio, qb_manager))

async def monitor_task(socketio, qb_manager):
    try:
        series = config.get("series", {})
        logger.info(f"Запуск мониторинга для {len(series)} сериалов")
        for series_url in series:
            await scan_series(series_url, socketio, qb_manager)
        logger.info("Мониторинг завершён")
    except Exception as e:
        logger.error(f"Ошибка в monitor_task: {str(e)}", exc_info=True)

def setup_scheduler(socketio, qb_manager):
    scheduler.add_job(
        lambda: asyncio.run(monitor_task(socketio, qb_manager)),
        'interval',
        minutes=config.get("scan_interval", 30),
        id='monitor_task'
    )
    scheduler.start()
    logger.info("Планировщик запущен")