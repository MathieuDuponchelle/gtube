import gdata.youtube
import gdata.youtube.service
import os

from media_entry import MediaEntry

from service_interface import ServiceInterface
from config import DEBUG

class YouTubeService(ServiceInterface):
    def __init__(self):
        ServiceInterface.__init__(self)
        yt_service = gdata.youtube.service.YouTubeService()
        yt_service.ssl = True  # Why not ?
        yt_service.developer_key = "AIzaSyAHriJg_4_SMBy11eq7N-8-QkAR66LtlxE"
        yt_service.client_id = "158353063395-4cdq0ij6j2daalhagbcfnqrgoftauvht.apps.googleusercontent.com"
        self._yt_service = yt_service
        self._name = "youtube"

        self._current_feed = None

    def search(self, words):
        query = gdata.youtube.service.YouTubeVideoQuery()
        query.vq = words
        query.orderby = 'viewCount'
        query.racy = 'include'
        self._current_feed = self._yt_service.YouTubeQuery(query)

        if DEBUG:
            self._printVideoFeed(self._current_feed)
        return self._createMediaEntries()

    def authenticate(self):
        pass

    def _createMediaEntries(self):
        _entries = []
        for _entry in self._current_feed.entry:
            _mediaEntry = MediaEntry(_entry.media.player.url,
                                     [thumb.url for thumb in _entry.media.thumbnail],
                                     _entry.media.title.text,
                                     _entry.media.duration.seconds,
                                     _entry.media.description.text,
                                     self)
            _entries.append(_mediaEntry)
        return _entries

    # Debugging utils
    def _printEntryDetails(self, entry):
        print ("=================== One Entry ==================")
        print ('Video title: %s' % entry.media.title.text)
        print ('Video published on: %s ' % entry.published.text)
        print ('Video description: %s' % entry.media.description.text)
        print ('Video tags: %s' % entry.media.keywords.text)
        print ('Video watch page: %s' % entry.media.player.url)
        print ('Video flash player URL: %s' % entry.GetSwfUrl())
        print ('Video duration: %s' % entry.media.duration.seconds)

        # non entry.media attributes
        print ('Video view count: %s' % entry.statistics.view_count)

        # show alternate formats
        for alternate_format in entry.media.content:
            if 'isDefault' not in alternate_format.extension_attributes:
                print ('Alternate format: %s | url: %s ' % (alternate_format.type,
                                                           alternate_format.url))

        # show thumbnails
        for thumbnail in entry.media.thumbnail:
            print ('Thumbnail url: %s' % thumbnail.url)
        print ("=================== End Entry ==================")

    def _printVideoFeed(self, feed):
        for entry in feed.entry:
            self._printEntryDetails(entry)

    def _get_url_from_infos(self, infos):
        return infos["entries"][0]

#Basic unit tests, will need some assertions :)

if __name__=="__main__":
    service = YouTubeService()
    entries = service.search("Dense Pika Colt")
