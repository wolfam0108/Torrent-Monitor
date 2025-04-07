import asyncio
from flask import render_template, redirect, url_for, request, jsonify
import logging
from config import Config
from scraper import AstarBzScraper
from qbittorrent_manager import QBittorrentManager
from monitor import scheduler, monitor_task  # Добавляем импорт monitor_task
from utils import load_logs
import threading

# Инициализация логгера
logger = logging.getLogger(__name__)

config = Config()
scraper = AstarBzScraper()

def setup_routes(app, socketio, qb_manager):
    @app.route('/')
    def index():
        qb_status, qb_message = asyncio.run(qb_manager.connect()) if not qb_manager.client else (True, "Подключено")
        logs = load_logs()
        return render_template(
            'index.html',
            series=config.get("series", {}),
            monitoring_status=app.config.get('scheduler_running', False),
            qb_status=qb_status,
            qb_message=qb_message,
            qb_config=config.get("qbittorrent"),
            scan_interval=config.get("scan_interval"),
            logs=logs
        )

    @app.route('/add', methods=['POST'])
    def add_series():
        series_url = request.form['series_url'].strip()
        save_path = request.form['save_path'].strip()
        series_name = request.form['series_name'].strip()
        season = request.form['season'].strip()
        if config.add_series(series_url, save_path, series_name, season):
            socketio.emit('notification', {'message': f'Сериал {series_name} добавлен', 'type': 'success'})
            return redirect(url_for('index'))
        socketio.emit('notification', {'message': 'Сериал уже добавлен', 'type': 'danger'})
        return "Сериал уже добавлен!", 400

    @app.route('/delete/<path:series_url>')
    def delete_series(series_url):
        if config.remove_series(series_url):
            socketio.emit('notification', {'message': f'Сериал {series_url} удален', 'type': 'success'})
        return redirect(url_for('index'))

    @app.route('/start')
    def start_monitoring():
        if not app.config.get('scheduler_running', False):
            app.config['scheduler_running'] = True
            if not scheduler.running:
                scheduler.start()
                logger.info("Планировщик перезапущен")
            socketio.emit('notification', {'message': 'Мониторинг запущен', 'type': 'success'})
        return redirect(url_for('index'))

    @app.route('/stop')
    def stop_monitoring():
        if app.config.get('scheduler_running', False):
            app.config['scheduler_running'] = False
            if scheduler.running:
                scheduler.shutdown(wait=False)  # Останавливаем планировщик
                logger.info("Планировщик остановлен")
            socketio.emit('notification', {'message': 'Мониторинг остановлен', 'type': 'info'})
        return redirect(url_for('index'))

    @app.route('/scan')
    def force_scan():
        from monitor import run_scan_series
        series = config.get("series", {})
        for series_url in series:
            threading.Thread(target=run_scan_series, args=(series_url, socketio, qb_manager), daemon=True).start()
        socketio.emit('notification', {'message': 'Сканирование всех сериалов запущено', 'type': 'info'})
        return redirect(url_for('index'))

    @app.route('/scan_series/<path:series_url>')
    def scan_series_route(series_url):
        from monitor import run_scan_series
        if series_url in config.get("series", {}):
            threading.Thread(target=run_scan_series, args=(series_url, socketio, qb_manager), daemon=True).start()
            socketio.emit('notification', {'message': f'Сканирование запущено для {series_url}', 'type': 'info'})
        else:
            socketio.emit('notification', {'message': 'Сериал не найден', 'type': 'danger'})
        return redirect(url_for('index'))

    @app.route('/api/status/<path:series_url>')
    def api_status(series_url):
        series_data = config.get("series").get(series_url)
        if not series_data:
            return jsonify({"error": "Сериал не найден"}), 404
        episodes = asyncio.run(scraper.get_episodes(series_url))
        qb_torrents = qb_manager.client.torrents_info() if qb_manager.client else []
        status_data = {
            "episodes": [
                {
                    "name": ep["name"],
                    "date": ep["date"],
                    "torrent_id": ep["torrent_id"],
                    "status": "Скачан/В загрузках" if any(ep["torrent_id"] in t.tags for t in qb_torrents) else "Есть на сайте"
                } for ep in episodes
            ],
            "total": len(episodes),
            "downloaded": sum(1 for ep in episodes if any(ep["torrent_id"] in t.tags for t in qb_torrents)),
            "new": sum(1 for ep in episodes if not any(ep["torrent_id"] in t.tags for t in qb_torrents))
        }
        return jsonify(status_data)

    @app.route('/api/rename/<path:series_url>', methods=['GET', 'POST'])
    def api_rename(series_url):
        series_data = config.get("series").get(series_url)
        if not series_data:
            return jsonify({"error": "Сериал не найден"}), 404

        if request.method == 'POST':
            try:
                series_data["series_name"] = request.form['series_name'].strip()
                series_data["season"] = request.form['season'].strip()
                config.save_config()
                asyncio.run(qb_manager.rename_torrent_files(None, series_data["save_path"], series_data["series_name"], series_data["season"], socketio))
                logger.info(f"Успешно применены настройки переименования для {series_url}")
                return jsonify({"message": f"Переименование для {series_url} применено"})
            except Exception as e:
                logger.error(f"Ошибка при переименовании для {series_url}: {str(e)}")
                return jsonify({"error": str(e)}), 500

        files = asyncio.run(qb_manager.get_torrent_files(series_data["save_path"]))
        rename_preview = [
            {
                "current_name": f["current_name"],
                "new_name": qb_manager.get_new_filename(f["current_name"], series_data["series_name"], series_data["season"]) or "Паттерн не найден"
            } for f in files
        ]
        return jsonify({"series_data": series_data, "rename_preview": rename_preview})

    @app.route('/api/toggle_rename/<path:series_url>', methods=['POST'])
    def toggle_rename(series_url):
        data = request.get_json()
        series = config.get("series").get(series_url)
        if series:
            series["rename_enabled"] = data["enabled"]
            config.save_config()
        return jsonify({"status": "ok"})

    @app.route('/update_settings', methods=['POST'])
    def update_settings():
        config.set("qbittorrent", {
            "host": request.form['qb_host'].strip(),
            "username": request.form['qb_username'].strip(),
            "password": request.form['qb_password'].strip()
        })
        new_interval = int(request.form['scan_interval'])
        config.set("scan_interval", new_interval)
        auto_start = 'auto_start' in request.form  # Проверяем, включена ли галочка
        config.set("auto_start", auto_start)
        global qb_manager
        qb_manager = QBittorrentManager(
            config.get("qbittorrent")["host"],
            config.get("qbittorrent")["username"],
            config.get("qbittorrent")["password"]
        )
        asyncio.run(qb_manager.connect())
    
        # Обновляем интервал планировщика
        if scheduler.running:
            scheduler.remove_all_jobs()  # Удаляем старую задачу
            scheduler.add_job(
                lambda: asyncio.run(monitor_task(socketio, qb_manager)),
                'interval',
                minutes=new_interval,
                id='monitor_task'
            )
            logger.info(f"Интервал мониторинга обновлён на {new_interval} минут")
        socketio.emit('notification', {'message': 'Настройки обновлены', 'type': 'success'})
        return redirect(url_for('index'))

    @app.route('/status/<path:series_url>')
    def status(series_url):
        return redirect(url_for('index'))  # Устаревший маршрут, перенаправляем

    @app.route('/rename/<path:series_url>', methods=['GET', 'POST'])
    def rename_settings(series_url):
        return redirect(url_for('index'))  # Устаревший маршрут, перенаправляем

    @socketio.on('connect')
    def handle_connect():
        pass