class MediaEntry(object):
    def __init__(self, media_url, thumbnail_urls, title, duration, description, service, audio_only=False):
        self._media_url = media_url
        self._thumbnail_urls = thumbnail_urls
        self._title = title
        self._duration = duration
        self._description = description
        self._service = service
        self._audio_only = audio_only

    @property
    def thumbnail_urls(self):
        return self._thumbnail_urls

    @thumbnail_urls.setter
    def thumbnail_urls(self, value):
        if not type(value) == list:
            raise TypeError("thumbnail urls must be a list")
        self._thumbnail_urls = value

    @property
    def media_url(self):
        return self._media_url

    @media_url.setter
    def media_url(self, value):
        if not type(value) == str:
            raise TypeError("media url must be a string")
        self._media_url = value

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        self._duration = value

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def service(self):
        return self._service

    @service.setter
    def service(self, value):
        self._service = value

    @property
    def audio_only(self):
        return self._audio_only

    @audio_only.setter
    def audio_only(self, value):
        self._audio_only = value
