#!/usr/bin/env python

import signal

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gst

import urllib
import os
import thread
import shutil

from youtube_service import YouTubeService
from converter_queue import ConverterQueue
from viewer import PitiviViewer
from pipeline import SimplePipeline
from config import RESULT_COLUMNS, MINIMUM_DOWNLOADED_SIZE, MUSIC_DIRECTORY, VIDEO_DIRECTORY
from check import check_hard_dependencies

class Crawler(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self)
        self.builder = None
        self._yt_service = None
        self._alreadyPlaying = False
        self._gridLock = thread.allocate_lock()
        self._current_state = Gst.State.PAUSED
        self._converter_queue = ConverterQueue()

        self.connect("activate", self._activatedCb)
        self.connect("startup", self._startupCb)

        if not os.path.exists(MUSIC_DIRECTORY):
            os.mkdir(MUSIC_DIRECTORY)

        if not os.path.exists(VIDEO_DIRECTORY):
            os.mkdir(VIDEO_DIRECTORY)

        if not os.path.exists(os.path.join(os.getcwd(), "data")):
            os.mkdir(os.path.join(os.getcwd(), "data"))

    def _startupCb(self, _):
        self.builder = Gtk.Builder()
        self.builder.add_from_file("crawler.ui")
        self.builder.connect_signals(self)

        _window = self.builder.get_object("applicationwindow1")
        box = self.builder.get_object("box4")
        _window.props.application = self
        _window.show_all()
        _window.maximize()

        self.viewer = PitiviViewer(self)
        box.pack_start(self.viewer, False, False, 0)

        self._resultGrid = self.builder.get_object("grid2")
        self._yt_service = YouTubeService()

        self._title_label = self.builder.get_object("titlelabel")
        self._duration_label = self.builder.get_object("durationlabel")
        self._description_label = self.builder.get_object("descriptionlabel")
        self._downloaded_label = self.builder.get_object("downloadedlabel")
        self._total_label = self.builder.get_object("totallabel")
        self._keep_button = self.builder.get_object("button1")
        self._convert_button = self.builder.get_object("button2")
        self._keep_button.set_sensitive(False)
        self._convert_button.set_sensitive(False)
        self._description_label.set_line_wrap(True)

    def _activatedCb(self, _):
        pass

    def _updateStateBox(self, entry):
        self._title_label.set_text(entry.title)
        self._duration_label.set_text(entry.duration + " seconds")
        self._description_label.set_text(entry.description)

    def _clearGrid(self):
        for label in self._resultGrid.get_children():
            label.hide()
            self._resultGrid.remove(label)

    def _retrieveImageFromUrl(self, url):
        name = os.getcwd()
        split = url.split('/')
        name = os.path.join(name, "data", split[-2] + "_" + split[-1])
        urllib.urlretrieve(url, name)
        return name

    def _getImage(self, entry, _row, _col):
        name = self._retrieveImageFromUrl(entry.thumbnail_urls[0])
        im = Gtk.Image.new_from_file(name)
        box = Gtk.EventBox()

        box.add(im)

        box.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
        box.connect("button-press-event", self._imageClickedCb, entry)

        GLib.idle_add(self._packBox, box, im, _row, _col, entry)

    def _packBox(self, box, image, _row, _col, entry):
        self._gridLock.acquire()
        hbox = Gtk.HBox()
        vbox = Gtk.VBox()
        label = Gtk.Label(label=entry.title)
        label.set_line_wrap(True)
        vbox.pack_start(box, False, False, 0)
        vbox.pack_start(label, False, False, 0)
        hbox.pack_start(vbox, expand=True, fill=False, padding=0)
        hbox.show_all()
        self._resultGrid.attach(hbox, _row, _col, 1, 1)
        self._gridLock.release()
        image.props.window.set_cursor (Gdk.Cursor (Gdk.CursorType.HAND1))

    def _cleanup(self):
        if self._alreadyPlaying:
            self._yt_service.stop_download()
            self.pipeline.setState(Gst.State.NULL)

        shutil.rmtree(os.path.join(os.getcwd(), "data"))

    def _searchActivatedCb(self, entry):
        self._clearGrid()
        _entries = self._yt_service.search(entry.get_text())
        _col = 0
        _row = 0

        for _entry in _entries:
            thread.start_new_thread(self._getImage, (_entry, _row, _col))
            _row += 1
            if (_row >= RESULT_COLUMNS):
                _row = 0
                _col += 1

    def _onDeleteCb(self, _, dummy):
        self._cleanup()
        self.quit()

    def _startPlaying(self):
        self._alreadyPlaying = True
        name = self._current_url.split("/")[-1]
        uri = GLib.filename_to_uri(os.path.join(os.getcwd(), "data", name + ".part"), None)
        pipe = Gst.parse_launch("uridecodebin uri=" + uri +" name=d ! xvimagesink name=my_video_sink d. ! autoaudiosink")
        pipeline = SimplePipeline(pipe, pipe.get_by_name("my_video_sink"))
        self.pipeline = pipeline
        self.viewer.setPipeline(pipeline)
        self.viewer._playButtonCb(None, None)

    def _progress_hook(self, status):
        if status["status"] == "finished":
            self._convert_button.set_sensitive(True)
            self._keep_button.set_sensitive(True)
            self._current_uri = os.path.join(os.getcwd(), "data", status["filename"])
            return

        try:
            _bytes = status["downloaded_bytes"]
            _total = status["total_bytes"]
        except KeyError:
            return

        if _bytes > MINIMUM_DOWNLOADED_SIZE and not self._alreadyPlaying:
            GLib.idle_add(self._startPlaying)

        GLib.idle_add(self._update_bytes_labels, _bytes, _total)

    def _update_bytes_labels(self, _bytes, _total):
        self._downloaded_label.set_text(str(_bytes) + " downloaded")
        self._total_label.set_text(str(_total) + " total")

    def togglePlayback(self):
        self.pipeline.togglePlayback()

    def _download_url(self, entry):
        self._current_url = entry.media_url
        self._current_entry = entry
        self._yt_service.downloadUrl(entry.media_url, self._progress_hook)

    def _imageClickedCb(self, widget, event, entry):
        if self._alreadyPlaying:
            self.viewer._playButtonCb(None, None)
            self._yt_service.stop_download()

        self._convert_button.set_sensitive(False)
        self._keep_button.set_sensitive(False)
        self._alreadyPlaying = False
        thread.start_new_thread(self._download_url, (entry,))
        self._updateStateBox(entry)

    def _convertMediaCb(self, _):
        self._converter_queue.enqueue(self._current_uri, self._current_entry.title)

    def _keepMediaCb(self, _):
        shutil.copy(self._current_uri, os.path.join(VIDEO_DIRECTORY, self._current_entry.title))

if __name__=="__main__":
    Gtk.init([])
    Gst.init([])

    deps = check_hard_dependencies()

    if (deps):
        print deps
        exit(0)

    crawler = Crawler()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    crawler.run([])
