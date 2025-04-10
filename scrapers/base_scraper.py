from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def get_episodes(self, series_url: str):
        """Возвращает список эпизодов для сериала."""
        pass

    @abstractmethod
    def get_torrent_content(self, torrent_url: str):
        """Возвращает содержимое торрент-файла или magnet-ссылку."""
        pass

    @abstractmethod
    def scan_series(self, series_url: str):
        """Возвращает метаданные сериала (название, варианты качества и т.д.)."""
        pass