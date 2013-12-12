import os
import youtube_dl
from FileDownloader import FileDownloader

class ServiceInterface:
    def __init__(self):
        self.downloader = None
        self._ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s%(ext)s'})
        self._ydl.add_default_info_extractors()
        self._name = None

    def search (self, words):
        raise NotImplementedError

    def authenticate(self):
        raise NotImplementedError

    def downloadUrl(self, url, progress_hook):
        infos = self._ydl.extract_info(url, download=False)
        params = {}
        params["quiet"] = True
        downloader = FileDownloader(self, params)
        downloader.add_progress_hook(progress_hook)
        self.downloader = downloader
        target = os.path.join(os.getcwd(), "data", url.split("/")[-1])
        real_url = self._get_url_from_infos(infos)
        print "real url is : ", real_url
        downloader._do_download(unicode(target), real_url)

    def stop_download(self):
        self.downloader.stop_download()

    def to_screen(self, *args, **kargs):
        pass

    def to_stderr(self, message):
        pass

    def to_console_title(self, message):
        pass

    def trouble(self, *args, **kargs):
        pass

    def report_warning(self, *args, **kargs):
        pass

    def report_error(self, *args, **kargs):
        pass

    def getName(self):
        return self._name

    def _get_url_from_infos(self, infos):
        raise NotImplementedError
