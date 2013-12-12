import soundcloud

from media_entry import MediaEntry
from service_interface import ServiceInterface

import youtube_dl
from FileDownloader import FileDownloader

class SoundCloudService(ServiceInterface):
    def __init__(self):
        ServiceInterface.__init__(self)
        self._client = soundcloud.Client(client_id="a0f302b73e746e103ea4be14fac09677")
        self.downloader = None
        self._current_feed = None
        self._name = "soundcloud"

    def search(self, words):
        self._current_feed = self._client.get('/tracks', q=words)
        return self._createMediaEntries()

    def _createMediaEntries(self):
        _entries = []
        for entry in self._current_feed:
            artwork_url = entry.obj["artwork_url"]
            if artwork_url is None:
                artwork_url = "soundcloud_default.png"
            _mediaEntry = MediaEntry(entry.obj["permalink_url"],
                                     [artwork_url],
                                     entry.obj["title"],
                                     str(entry.obj["duration"] / 1000),  # Duration is in milliseconds
                                     entry.obj["description"],
                                     self,
                                     audio_only=True)
            _entries.append(_mediaEntry)
        return _entries

    def _get_url_from_infos(self, infos):
        return infos["formats"][0]
