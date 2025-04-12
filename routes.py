import asyncio
from flask import render_template, redirect, url_for, request, jsonify
import logging
from monitor import scheduler, run_scan_series, find_series_data, monitor_task
from utils import load_logs
import threading
from urllib.parse import urlparse
import hashlib
from qbittorrent_manager import QBittorrentManager

logger = logging.getLogger(__name__)

def setup_routes(app, socketio, auth_manager, config):
    def get_scraper(series_url):
        return auth_manager.get_scraper(series_url)

    @app.route('/')
    def index():
        return render_template(
            'index.html',
            series=config.get("series", {}),
            monitoring_status=app.config.get('scheduler_running', False),
            logs=load_logs(),
            qb_config=config.get("qbittorrent", {}),
            kinozal_auth=config.get("kinozal_auth", {}),
            rutracker_auth=config.get("rutracker_auth", {}),
            scan_interval=config.get("scan_interval", 30)
        )

    @app.route('/add', methods=['POST'])
    def add_series():
        series_url = request.form['series_url'].strip()
        save_path = request.form['save_path'].strip()
        series_name = request.form['series_name'].strip()
        season = request.form['season'].strip()
        quality = request.form.get('quality', None)
        torrent_ids = request.form.get('torrent_ids', '').split(',')
        is_seasonal_torrent = 'anilibria.top' in series_url or 'kinozal.tv' in series_url or 'kinozal.me' in series_url or 'rutracker.org' in series_url or 'nnmclub.to' in series_url
        
        scraper = get_scraper(series_url)
        if not scraper:
            socketio.emit('notification', {'message': 'Парсер не найден для этого URL', 'type': 'danger'})
            return "Парсер не найден!", 400
        
        if ('kinozal.tv' in series_url or 'kinozal.me' in series_url) and (not config.get("kinozal_auth")["username"] or not config.get("kinozal_auth")["password"]):
            socketio.emit('notification', {'message': 'Требуется авторизация для kinozal. Укажите логин и пароль в настройках.', 'type': 'danger'})
            return "Требуется авторизация!", 400
        
        if 'rutracker.org' in series_url and (not config.get("rutracker_auth")["username"] or not config.get("rutracker_auth")["password"]):
            socketio.emit('notification', {'message': 'Требуется авторизация для rutracker.org. Укажите логин и пароль в настройках.', 'type': 'danger'})
            return "Требуется авторизация!", 400
        
        if config.add_series(series_url, save_path, series_name, season, quality, is_seasonal_torrent):
            config.config["series"][series_url]["torrent_ids"] = torrent_ids
            config.save_config()
            socketio.emit('notification', {'message': f'Сериал {series_name} добавлен', 'type': 'success'})
            return redirect(url_for('index'))
        socketio.emit('notification', {'message': 'Сериал уже добавлен', 'type': 'danger'})
        return "Сериал уже добавлен!", 400

    @app.route('/delete/<path:series_url>')
    def delete_series(series_url):
        if config.remove_series(series_url):
            config.config = config.load_or_create_config()
            socketio.emit('notification', {'message': f'Сериал {series_url} удален', 'type': 'success'})
        return redirect(url_for('index'))

    @app.route('/start')
    def start_monitoring():
        if not app.config.get('scheduler_running', False):
            app.config['scheduler_running'] = True
            if not scheduler.running:
                scheduler.start()
                logger.info("Планировщик запущен через маршрут /start")
            socketio.emit('notification', {'message': 'Мониторинг запущен', 'type': 'success'})
        return redirect(url_for('index'))

    @app.route('/stop')
    def stop_monitoring():
        if app.config.get('scheduler_running', False):
            app.config['scheduler_running'] = False
            if scheduler.running:
                scheduler.shutdown(wait=False)
                logger.info("Планировщик остановлен через маршрут /stop")
            socketio.emit('notification', {'message': 'Мониторинг остановлен', 'type': 'info'})
        return redirect(url_for('index'))

    @app.route('/scan')
    def force_scan():
        series = config.get("series", {})
        for series_url in series:
            scraper = get_scraper(series_url)
            if scraper:
                threading.Thread(target=run_scan_series, args=(series_url, socketio, auth_manager, config), daemon=True).start()
        socketio.emit('notification', {'message': 'Сканирование всех сериалов запущено', 'type': 'info'})
        return redirect(url_for('index'))

    @app.route('/scan_series/<path:series_url>')
    def scan_series_route(series_url):
        scraper = get_scraper(series_url)
        series_data = find_series_data(series_url, config)
        if series_data and scraper:
            threading.Thread(target=run_scan_series, args=(series_url, socketio, auth_manager, config), daemon=True).start()
            socketio.emit('notification', {'message': f'Сканирование запущено для {series_url}', 'type': 'info'})
            return jsonify({"status": "started"})
        socketio.emit('notification', {'message': 'Сериал не найден', 'type': 'danger'})
        logger.error(f"Сериал {series_url} не найден в конфигурации при сканировании")
        return jsonify({"status": "error", "message": "Сериал не найден"}), 404

    @app.route('/api/status/<path:series_url>', methods=['GET', 'POST'])
    def api_status(series_url):
        series_data = find_series_data(series_url, config)
        if not series_data:
            socketio.emit('notification', {'message': 'Сериал не найден', 'type': 'danger'})
            return jsonify({"error": "Сериал не найден"}), 404
        scraper = get_scraper(series_url)
        if not scraper:
            from urllib.parse import urlparse
            domain = urlparse(series_url).netloc
            if domain == "nnmclub.to":
                socketio.emit('notification', {'message': 'Парсер для nnmclub.to отключён в настройках приложения', 'type': 'warning'})
                return jsonify({"error": "Парсер для nnmclub.to отключён"}), 400
            socketio.emit('notification', {'message': 'Парсер не найден для этого URL', 'type': 'danger'})
            return jsonify({"error": "Парсер не найден"}), 400
        
        try:
            episodes = asyncio.run(scraper.get_episodes(series_url, quality=series_data.get("quality")))
            logger.info(f"Получено {len(episodes)} эпизодов для {series_url} через парсер")
            if not episodes:
                socketio.emit('notification', {'message': 'Эпизоды не найдены для этого сериала', 'type': 'warning'})
        except Exception as e:
            logger.error(f"Ошибка при получении эпизодов для {series_url}: {str(e)}")
            socketio.emit('notification', {'message': f'Ошибка при сканировании сайта: {str(e)}', 'type': 'danger'})
            return jsonify({"error": f"Ошибка при сканировании сайта: {str(e)}"}), 500
        
        qb_client = auth_manager.get_qb_client()
        qb_torrents = qb_client.torrents_info() if qb_client else []
        torrent_ids = series_data.get("torrent_ids", [ep["torrent_id"] for ep in episodes])

        if request.method == 'POST':
            series_data["series_name"] = request.form['series_name'].strip()
            series_data["season"] = request.form['season'].strip()
            config.save_config()
            torrent_hashes = [t.hash for t in qb_torrents if any(t_id in t.tags for t_id in torrent_ids)]
            try:
                qb_manager = QBittorrentManager(qb_client)
                for torrent_hash in torrent_hashes:
                    logger.info(f"Обработка торрента с хэшем {torrent_hash}")
                    torrent = next((torrent for torrent in qb_torrents if torrent.hash == torrent_hash), None)
                    if not torrent:
                        logger.warning(f"Торрент с хэшем {torrent_hash} не найден")
                        continue
                    torrent_id = next((t_id for t_id in torrent_ids if t_id in torrent.tags), None)
                    if not torrent_id:
                        logger.warning(f"ID торрента не найден для хэша {torrent_hash}")
                        continue
                    asyncio.run(qb_manager.rename_torrent_files(
                        torrent_hash, series_data["save_path"], series_data["series_name"], 
                        series_data["season"], torrent_id, socketio
                    ))
                socketio.emit('notification', {'message': f'Переименование для {series_url} применено', 'type': 'success'})
                return jsonify({"message": "Переименование выполнено"})
            except Exception as e:
                logger.error(f"Ошибка при переименовании: {e}")
                socketio.emit('notification', {'message': f'Ошибка при переименовании: {str(e)}', 'type': 'danger'})
                return jsonify({"error": str(e)}), 500

        status_data = {
            "episodes": [
                {
                    "name": ep["name"],
                    "date": ep.get("last_updated", "Неизвестно"),
                    "torrent_id": ep["torrent_id"],
                    "status": "Есть на сайте"
                } for ep in episodes
            ],
            "total": len(episodes),
            "downloaded": 0,
            "new": len(episodes)
        }
        rename_preview = []
        has_completed = False
        for ep in status_data["episodes"]:
            torrent = next((torrent for torrent in qb_torrents if ep["torrent_id"] in torrent.tags), None)
            if torrent:
                qb_manager = QBittorrentManager(qb_client)
                status = qb_manager.get_torrent_status(torrent.hash)
                if status:
                    ep["status"] = status["state"]
                    if status["completed"]:
                        has_completed = True
                        status_data["downloaded"] += 1
                        status_data["new"] -= 1
                        files = qb_client.torrents_files(torrent_hash=torrent.hash)
                        for file in files:
                            new_name = qb_manager.get_new_filename(file.name, series_data["series_name"], series_data["season"])
                            rename_preview.append({
                                "current_name": file.name,
                                "new_name": new_name or "Паттерн не найден",
                                "torrent_hash": torrent.hash,
                                "torrent_id": ep["torrent_id"]
                            })
        return jsonify({
            "status_data": status_data,
            "rename_preview": rename_preview if has_completed else [],
            "series_data": series_data,
            "can_rename": has_completed
        })

    @app.route('/api/toggle_rename/<path:series_url>', methods=['POST'])
    def toggle_rename(series_url):
        data = request.get_json()
        series = config.get("series").get(series_url)
        if not series:
            logger.error(f"Сериал {series_url} не найден для переключения авто-переименования")
            return jsonify({"error": "Сериал не найден"}), 404
        series["rename_enabled"] = data["enabled"]
        config.save_config()
        logger.info(f"Авто-переименование для {series_url} установлено в {data['enabled']}")
        return jsonify({"status": "ok"})

    @app.route('/api/scan_url', methods=['POST'])
    def scan_url():
        series_url = request.json.get('series_url', '').strip()
        scraper = get_scraper(series_url)
        if not scraper:
            from urllib.parse import urlparse
            domain = urlparse(series_url).netloc
            if domain == "nnmclub.to":
                socketio.emit('notification', {'message': 'Парсер для nnmclub.to отключён в настройках приложения', 'type': 'warning'})
                return jsonify({"error": "Парсер для nnmclub.to отключён"}), 400
            socketio.emit('notification', {'message': 'Парсер не найден для этого URL', 'type': 'danger'})
            return jsonify({"error": "Парсер не найден для этого URL"}), 400
        try:
            result = asyncio.run(scraper.get_episodes(series_url))
            if not result:
                socketio.emit('notification', {'message': 'Эпизоды не найдены', 'type': 'warning'})
                return jsonify({"error": "Эпизоды не найдены"}), 404
            
            torrent_ids = [ep["torrent_id"] for ep in result]
            quality_options = [{"quality": ep.get("quality", "N/A")} for ep in result] if any("quality" in ep and ep["quality"] != "N/A" for ep in result) else []
            qb_client = auth_manager.get_qb_client()
            qb_torrents = qb_client.torrents_info() if qb_client else []
            names = result[0].get("names", [result[0]["name"]]) if "names" in result[0] else [result[0]["name"]]
            status_data = {
                "episodes": [
                    {
                        "name": ep["name"],
                        "episode_name": ep.get("episode_name", ep["name"]),
                        "torrent_id": ep["torrent_id"],
                        "quality": ep.get("quality", "N/A"),
                        "last_updated": ep.get("last_updated", ""),
                        "status": "Есть на сайте" if not any(ep["torrent_id"] in t.tags for t in qb_torrents) else 
                                  QBittorrentManager(qb_client).get_torrent_status(next(t.hash for t in qb_torrents if ep["torrent_id"] in t.tags))["state"]
                    } for ep in result
                ]
            }
            response = {
                "name": result[0]["name"],
                "names": names,
                "torrent_ids": torrent_ids,
                "status_data": status_data
            }
            if quality_options:
                response["quality_options"] = quality_options
            return jsonify(response)
        except Exception as e:
            logger.error(f"Ошибка при сканировании URL: {e}")
            socketio.emit('notification', {'message': f'Ошибка при сканировании: {str(e)}', 'type': 'danger'})
            return jsonify({"error": str(e)}), 500

    @app.route('/update_settings', methods=['POST'])
    def update_settings():
        config.set("qbittorrent", {
            "host": request.form['qb_host'].strip(),
            "username": request.form['qb_username'].strip(),
            "password": request.form['qb_password'].strip()
        })
        config.set("kinozal_auth", {
            "username": request.form['kinozal_username'].strip(),
            "password": request.form['kinozal_password'].strip()
        })
        config.set("rutracker_auth", {
            "username": request.form['rutracker_username'].strip(),
            "password": request.form['rutracker_password'].strip()
        })
        new_interval = int(request.form['scan_interval'])
        config.set("scan_interval", new_interval)
        auto_start = 'auto_start' in request.form
        config.set("auto_start", auto_start)
        
        # Перезапуск авторизации с новыми настройками
        auth_manager.statuses = {
            "qbittorrent": {"status": "Проверка...", "spinner": True},
            "kinozal": {"status": "Проверка...", "spinner": True},
            "rutracker": {"status": "Проверка...", "spinner": True}
        }
        socketio.start_background_task(auth_manager.initialize)
        
        if scheduler.running:
            scheduler.remove_all_jobs()
            scheduler.add_job(
                lambda: asyncio.run(monitor_task(socketio, auth_manager, config)),
                'interval',
                minutes=new_interval,
                id='monitor_task'
            )
            logger.info(f"Интервал мониторинга обновлён на {new_interval} минут")
        socketio.emit('notification', {'message': 'Настройки обновлены', 'type': 'success'})
        return redirect(url_for('index'))

    @socketio.on('connect')
    def handle_connect():
        pass