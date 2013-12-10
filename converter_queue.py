from gi.repository import Gst
from gi.repository import GLib

import thread
import urllib
import os
from pipeline import SimplePipeline
from config import MUSIC_DIRECTORY, AUDIO_ENCODER

class ConverterQueue:
    def __init__(self):
        self._queued = []
        self._lock = thread.allocate_lock()
        self.pipeline = None

    def enqueue(self, uri, target):
        self._lock.acquire()
        self._queued.append((GLib.filename_to_uri(uri, None), target))
        self._lock.release()
        self._dequeue()

    def _dequeue(self):
        self._lock.acquire()
        if not self._queued:
            self._lock.release()
            return
        uri, target = self._queued.pop()
        # Really crappy way to figure out an extension
        extension = "." + AUDIO_ENCODER.split('enc')[0][-3:]

        target = os.path.join(MUSIC_DIRECTORY, GLib.uri_escape_string(target, None, False) + extension)
        self._lock.release()
        pipeline = Gst.parse_launch("uridecodebin uri=" + uri + " ! " + AUDIO_ENCODER + " ! filesink location=" + target)

        if self.pipeline:
            self.pipeline.disconnect_by_func(self._eosCb)
            self.pipeline.setState(Gst.State.NULL)

        self.pipeline = SimplePipeline(pipeline, None)
        self.pipeline.connect("eos", self._eosCb)
        self.pipeline.setState(Gst.State.PLAYING)

    def _eosCb(self, pipeline):
        pipeline.setState(Gst.State.NULL)
        self._dequeue()
