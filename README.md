# Torrent-Monitor

Torrent-Monitor — это веб-приложение для автоматического мониторинга и управления загрузкой торрентов сериалов с сайтов Anilibria (anilibria.top) и AstarBz (v6.astar.bz). Оно позволяет добавлять сериалы, отслеживать новые эпизоды, загружать их через qBittorrent и автоматически переименовывать файлы в удобный формат. Проект разработан с использованием Python (Flask, SocketIO) для серверной части и JavaScript (Bootstrap) для интерфейса. Подходит для автоматизации загрузки аниме-сериалов с поддержкой выбора качества и гибкой настройки.

### Основные возможности

- Добавление сериалов: укажите URL сериала, путь сохранения и настройки (название, сезон, качество).  
- Мониторинг: автоматическая проверка новых эпизодов с заданным интервалом.  
- Загрузка: интеграция с qBittorrent для скачивания торрентов.  
- Переименование: автоматическое или ручное переименование файлов в формат <Название> <Сезон>e<Номер> <Качество>.  
- Интерфейс: удобная веб-таблица с состоянием сериалов, действиями (сканирование, статус, удаление) и уведомлениями.  
- Статусы: визуальная индикация процесса с зелёным пульсирующим спиннером для активных состояний.

### Требования

- Операционная система: Linux (тестировалось на Ubuntu), Windows или macOS.  
- Python: 3.8+.  
- qBittorrent: установленный и настроенный экземпляр с доступом через WebUI.  
- ChromeDriver: для парсинга Anilibria (требуется Selenium).  
- Git: для клонирования репозитория.

### Установка

#### 1. Клонирование репозитория  
Склонируйте проект с GitHub и перейдите в директорию:
```bash
git clone https://github.com/wolfam0108/Torrent-Monitor.git
cd Torrent-Monitor
```

- Приложение будет доступно по адресу `http://localhost:5000`.

#### 2. Установка зависимостей  
Создайте виртуальное окружение и установите необходимые Python-пакеты:
```bash
python3 -m venv Torrent-Monitor
source Torrent-Monitor/bin/activate  # Для Linux/macOS
```
или Torrent-Monitor\Scripts\activate для Windows
```bash
pip install -r requirements.txt
```
Если файл `requirements.txt` отсутствует, установите зависимости вручную:
```bash
pip install flask flask-socketio qbittorrent-api apscheduler cloudscraper beautifulsoup4 selenium
```

#### 3. Установка ChromeDriver  
Для парсинга Anilibria требуется ChromeDriver:  
- Установите Google Chrome.  
- Скачайте ChromeDriver, соответствующий версии Chrome, с [официального сайта](https://chromedriver.chromium.org/downloads).  
- Поместите `chromedriver` в `/usr/local/bin/` (Linux) или добавьте путь к нему в переменную PATH:  
```bash
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```

#### 4. Настройка qBittorrent  
- Убедитесь, что qBittorrent запущен и WebUI включён (по умолчанию: `http://localhost:8080`).  
- Настройте имя пользователя и пароль в qBittorrent (по умолчанию пустые).  
- Укажите эти данные в `torrent_monitor_config.json` (см. ниже).

#### 5. Конфигурация  
Создайте или отредактируйте файл `torrent_monitor_config.json` в корневой директории проекта. Пример:  
```bash
{
    "qbittorrent": {
        "host": "http://localhost:8080",
        "username": "admin",
        "password": "your_password"
    },
    "scan_interval": 10,
    "series": {},
    "last_scan": null,
    "auto_start": false
}
```
- `host`: Адрес WebUI qBittorrent.  
- `username` и `password`: Учётные данные qBittorrent.  
- `scan_interval`: Интервал мониторинга в минутах (например, 10).  
- `auto_start`: Автоматический запуск мониторинга при старте (`true` или `false`).

### Использование

#### 1. Запуск приложения  
Запустите сервер:

```bash
source Torrent-Monitor/bin/activate  # Для Linux/macOS
python3 app.py
```
- Приложение будет доступно по адресу `http://localhost:5000`.

#### 2. Интерфейс  
Открой браузер и перейди на `http://localhost:5000`.

##### Основные элементы  
- **Таблица сериалов**:  
  - **URL**: Ссылка на страницу сериала.  
  - **Путь**: Директория сохранения.  
  - **Название**: Имя сериала.  
  - **Сезон**: Номер сезона (например, "s01").  
  - **Авто**: Галочка для включения авто-переименования.  
  - **Состояние**: Текущий статус ("Ожидание", "Готов", "Сканирование" и т.д.).  
  - **Действия**: Кнопки "Удалить", "Статус", "Сканировать".  
- **Кнопки управления**:  
  - "Добавить сериал": Открывает форму для добавления.  
  - "Запустить" / "Остановить": Управление периодическим мониторингом.  
  - "Сканировать все": Запуск сканирования всех сериалов.

##### Добавление сериала  
1. Нажми "Добавить сериал".  
2. Введи URL (например, `https://anilibria.top/anime/releases/release/kusuriya-no-hitorigoto-2nd-season/torrents`).  
3. Укажи путь сохранения, название и сезон.  
4. Выбери качество (для Anilibria, например, "WEBRip+1080p").  
5. Нажми "Добавить".

##### Сканирование и статус  
- **Сканировать**: Запускает проверку новых эпизодов для конкретного сериала.  
- **Статус**: Открывает модальное окно с деталями (всего эпизодов, скачано, новых) и опцией переименования для завершённых торрентов.

##### Авто-переименование  
- Включи галочку "Авто" в таблице.  
- При периодическом мониторинге завершённые торренты будут автоматически переименованы.

### Статусы в таблице
- **Ожидание**: Начальное состояние, ничего не происходит.  
- **Готов**: Сканирование завершено успешно.  
- **Ошибка: <текст>**: Ошибка при сканировании или загрузке.  
- **<спиннер> В процессе**: Временное состояние при клике.  
- **<спиннер> Сканирование**: Проверка новых эпизодов.  
- **<спиннер> <progress>/<total>**: Прогресс добавления (например, "1/2").  
- **<спиннер> Добавление: <имя>**: Добавление торрента.  
- **Переименование завершено**: Переименование выполнено.  

Спиннер — зелёный пульсирующий круг (`spinner-grow text-success`), отображается для активных процессов.

### Разработка и вклад
- **Требования для разработки**: Установите зависимости и ChromeDriver, как описано выше.  
- **Запуск**: Используйте `python3 app.py` для тестирования.  
- **Вклад**: Создавайте Pull Requests с улучшениями или исправлениями.

### Лицензия
Этот проект распространяется под лицензией MIT. Подробности в файле `LICENSE` (если его нет, добавьте самостоятельно).

### Контакты
Если у вас есть вопросы или предложения, создайте Issue на GitHub или свяжитесь с автором: [wolfam0108](https://github.com/wolfam0108).
