# PiTiVi , Non-linear video editor
#
#       ui/viewer.py
#
# Copyright (c) 2005, Edward Hervey <bilboed@bilboed.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

import platform
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Gst
from gi.repository import GdkX11
from gi.repository import GObject
from gi.repository import GES
GdkX11  # pyflakes
from gi.repository import GstVideo
GstVideo    # pyflakes
import cairo

from gettext import gettext as _
from time import time
from math import pi

from pipeline import Seeker, SimplePipeline
from ui import SPACING, hex_to_rgb
from widgets import TimeWidget
from loggable import Loggable
from misc import print_ns

class PitiviViewer(Gtk.VBox, Loggable):
    """
    A Widget to control and visualize a Pipeline

    @ivar pipeline: The current pipeline
    @type pipeline: L{Pipeline}
    @ivar action: The action controlled by this Pipeline
    @type action: L{ViewAction}
    """
    __gtype_name__ = 'PitiviViewer'
    __gsignals__ = {
        "activate-playback-controls": (GObject.SignalFlags.RUN_LAST,
            None, (GObject.TYPE_BOOLEAN,)),
    }

    INHIBIT_REASON = _("Currently playing")

    def __init__(self, app, undock_action=None):
        Gtk.VBox.__init__(self)
        self.set_border_width(SPACING)
        self.app = app

        Loggable.__init__(self)
        self.log("New PitiviViewer")

        self.pipeline = None
        self._tmp_pipeline = None  # Used for displaying a preview when trimming

        self.sink = None
        self.docked = True

        # Only used for restoring the pipeline position after a live clip trim preview:
        self._oldTimelinePos = None

        self._haveUI = False

        self._createUi()
        self.target = self.internal
        self.undock_action = undock_action
        if undock_action:
            self.undock_action.connect("activate", self._toggleDocked)

    def setPipeline(self, pipeline, position=None):
        """
        Set the Viewer to the given Pipeline.

        Properly switches the currently set action to that new Pipeline.

        @param pipeline: The Pipeline to switch to.
        @type pipeline: L{Pipeline}.
        @param position: Optional position to seek to initially.
        """
        self.debug("self.pipeline:%r", self.pipeline)

        self.seeker = Seeker()
        self._disconnectFromPipeline()
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        self.pipeline = pipeline
        if self.pipeline:
            self.pipeline.pause()
            self.seeker.seek(position)

            self.pipeline.connect("state-change", self._pipelineStateChangedCb)
            self.pipeline.connect("position", self._positionCb)
            self.pipeline.connect("duration-changed", self._durationChangedCb)

        self.sink = pipeline.video_overlay
        self._switch_output_window()
        self._setUiActive()

    def _disconnectFromPipeline(self):
        self.debug("pipeline:%r", self.pipeline)
        if self.pipeline is None:
            # silently return, there's nothing to disconnect from
            return

        self.pipeline.disconnect_by_func(self._pipelineStateChangedCb)
        self.pipeline.disconnect_by_func(self._positionCb)
        self.pipeline.disconnect_by_func(self._durationChangedCb)

        self.pipeline = None

    def _setUiActive(self, active=True):
        self.debug("active %r", active)
        self.set_sensitive(active)
        if self._haveUI:
            for item in [self.goToStart_button, self.back_button,
                         self.playpause_button, self.forward_button,
                         self.goToEnd_button, self.timecode_entry]:
                item.set_sensitive(active)
        if active:
            self.emit("activate-playback-controls", True)

    def _externalWindowDeleteCb(self, window, event):
        self.dock()
        return True

    def _externalWindowConfigureCb(self, window, event):
        self.settings.viewerWidth = event.width
        self.settings.viewerHeight = event.height
        self.settings.viewerX = event.x
        self.settings.viewerY = event.y

    def _createUi(self):
        """ Creates the Viewer GUI """
        # Drawing area
        # The aspect ratio gets overridden on startup by setDisplayAspectRatio
        self.aframe = Gtk.AspectFrame(xalign=0.5, yalign=1.0, ratio=4.0 / 3.0,
                                      obey_child=False)

        self.internal = ViewerWidget()
        self.internal.init_transformation_events()
        self.internal.show()
        self.aframe.add(self.internal)
        self.pack_start(self.aframe, True, True, 0)

        self.external_window = Gtk.Window()
        vbox = Gtk.VBox()
        vbox.set_spacing(SPACING)
        self.external_window.add(vbox)
        self.external = ViewerWidget()
        vbox.pack_start(self.external, True, True, 0)
        self.external_window.connect("delete-event", self._externalWindowDeleteCb)
        self.external_window.connect("configure-event", self._externalWindowConfigureCb)
        self.external_vbox = vbox
        self.external_vbox.show_all()

        # Buttons/Controls
        bbox = Gtk.HBox()
        boxalign = Gtk.Alignment(xalign=0.5, yalign=0.5, xscale=0.0, yscale=0.0)
        boxalign.add(bbox)
        self.pack_start(boxalign, False, True, 0)

        self.goToStart_button = Gtk.ToolButton(Gtk.STOCK_MEDIA_PREVIOUS)
        self.goToStart_button.connect("clicked", self._goToStartCb)
        self.goToStart_button.set_tooltip_text(_("Not implemented"))
        self.goToStart_button.set_sensitive(False)
        bbox.pack_start(self.goToStart_button, False, True, 0)

        self.back_button = Gtk.ToolButton(Gtk.STOCK_MEDIA_REWIND)
        self.back_button.connect("clicked", self._backCb)
        self.back_button.set_tooltip_text(_("Not implemented"))
        self.back_button.set_sensitive(False)
        bbox.pack_start(self.back_button, False, True, 0)

        self.playpause_button = PlayPauseButton()
        self.playpause_button.connect("play", self._playButtonCb)
        bbox.pack_start(self.playpause_button, False, True, 0)
        self.playpause_button.set_sensitive(False)

        self.forward_button = Gtk.ToolButton(Gtk.STOCK_MEDIA_FORWARD)
        self.forward_button.connect("clicked", self._forwardCb)
        self.forward_button.set_tooltip_text(_("Not implemented"))
        self.forward_button.set_sensitive(False)
        bbox.pack_start(self.forward_button, False, True, 0)

        self.goToEnd_button = Gtk.ToolButton(Gtk.STOCK_REFRESH)
        self.goToEnd_button.connect("clicked", self._goToEndCb)
        self.goToEnd_button.set_tooltip_text(_("Go back to live"))
        self.goToEnd_button.set_sensitive(False)
        bbox.pack_start(self.goToEnd_button, False, True, 0)

        # current time
        self.timecode_entry = TimeWidget()
        self.timecode_entry.setWidgetValue(0)
        self.timecode_entry.set_tooltip_text(_('Enter a timecode or frame number\nand press "Enter" to go to that position'))
        self.timecode_entry.connectActivateEvent(self._entryActivateCb)
        bbox.pack_start(self.timecode_entry, False, 10, 0)
        self._haveUI = True

        # Identify widgets for AT-SPI, making our test suite easier to develop
        # These will show up in sniff, accerciser, etc.
        self.goToStart_button.get_accessible().set_name("goToStart_button")
        self.back_button.get_accessible().set_name("back_button")
        self.playpause_button.get_accessible().set_name("playpause_button")
        self.forward_button.get_accessible().set_name("forward_button")
        self.goToEnd_button.get_accessible().set_name("goToEnd_button")
        self.timecode_entry.get_accessible().set_name("timecode_entry")

        screen = Gdk.Screen.get_default()
        height = screen.get_height()
        if height >= 800:
            # show the controls and force the aspect frame to have at least the same
            # width (+110, which is a magic number to minimize dead padding).
            bbox.show_all()
            req = bbox.size_request()
            width = req.width
            height = req.height
            width += 110
            height = int(width / self.aframe.props.ratio)
            self.aframe.set_size_request(width, height)
        self.show_all()
        self.buttons = bbox
        self.buttons_container = boxalign

    def setDisplayAspectRatio(self, ratio):
        """
        Sets the DAR of the Viewer to the given ratio.

        @arg ratio: The aspect ratio to set on the viewer
        @type ratio: L{float}
        """
        self.debug("Setting ratio of %f [%r]", float(ratio), ratio)
        try:
            self.aframe.set_property("ratio", float(ratio))
        except:
            self.warning("could not set ratio !")

    def _entryActivateCb(self, entry):
        self._seekFromTimecodeWidget()

    def _seekFromTimecodeWidget(self):
        nanoseconds = self.timecode_entry.getWidgetValue()
        self.seeker.seek(nanoseconds)

    ## active Timeline calllbacks
    def _durationChangedCb(self, unused_pipeline, duration):
        if duration == 0:
            self._setUiActive(False)
        else:
            self._setUiActive(True)

    ## Control Gtk.Button callbacks

    def setZoom(self, zoom):
        """
        Zoom in or out of the transformation box canvas.
        This is called by clipproperties.
        """
        if self.target.box:
            maxSize = self.target.area
            width = int(float(maxSize.width) * zoom)
            height = int(float(maxSize.height) * zoom)
            area = ((maxSize.width - width) / 2,
                    (maxSize.height - height) / 2,
                    width, height)
            self.sink.set_render_rectangle(*area)
            self.target.box.update_size(area)
            self.target.zoom = zoom
            self.target.sink = self.sink
            self.target.renderbox()

    def _playButtonCb(self, unused_button, playing):
        self.app.togglePlayback()

    def _goToStartCb(self, unused_button):
        raise NotImplementedError

    def _backCb(self, unused_button):
        # Seek backwards one second
        raise NotImplementedError

    def _forwardCb(self, unused_button):
        # Seek forward one second
        raise NotImplementedError

    def _goToEndCb(self, unused_button):
        self.app.goToEnd()
    ## public methods for controlling playback

    def undock(self):
        if not self.undock_action:
            self.error("Cannot undock because undock_action is missing.")
            return
        if not self.docked:
            return

        self.docked = False
        self.settings.viewerDocked = False
        self.undock_action.set_label(_("Dock Viewer"))
        self.target = self.external

        self.remove(self.buttons_container)
        self.external_vbox.pack_end(self.buttons_container, False, False, 0)
        self.external_window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.external_window.show()

        self.fullscreen_button = Gtk.ToggleToolButton(Gtk.STOCK_FULLSCREEN)
        self.fullscreen_button.set_tooltip_text(_("Show this window in fullscreen"))
        self.buttons.pack_end(self.fullscreen_button, expand=False, fill=False, padding=6)
        self.fullscreen_button.show()
        self.fullscreen_button.connect("toggled", self._toggleFullscreen)

        # if we are playing, switch output immediately
        if self.sink:
            self._switch_output_window()
        self.hide()
        self.external_window.move(self.settings.viewerX, self.settings.viewerY)
        self.external_window.resize(self.settings.viewerWidth, self.settings.viewerHeight)

    def dock(self):
        if not self.undock_action:
            self.error("Cannot dock because undock_action is missing.")
            return
        if self.docked:
            return
        self.docked = True
        self.settings.viewerDocked = True
        self.undock_action.set_label(_("Undock Viewer"))
        self.target = self.internal

        self.fullscreen_button.destroy()
        self.external_vbox.remove(self.buttons_container)
        self.pack_end(self.buttons_container, False, False, 0)
        self.show()
        # if we are playing, switch output immediately
        if self.sink:
            self._switch_output_window()
        self.external_window.hide()

    def _toggleDocked(self, action):
        if self.docked:
            self.undock()
        else:
            self.dock()

    def _toggleFullscreen(self, widget):
        if widget.get_active():
            self.external_window.hide()
            # GTK doesn't let us fullscreen utility windows
            self.external_window.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            self.external_window.show()
            self.external_window.fullscreen()
            widget.set_tooltip_text(_("Exit fullscreen mode"))
        else:
            self.external_window.unfullscreen()
            widget.set_tooltip_text(_("Show this window in fullscreen"))
            self.external_window.hide()
            self.external_window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
            self.external_window.show()

    def _positionCb(self, unused_pipeline, position):
        """
        If the timeline position changed, update the viewer UI widgets.

        This is meant to be called either by the gobject timer when playing,
        or by mainwindow's _timelineSeekCb when the timer is disabled.
        """
        self.timecode_entry.setWidgetValue(position, False)

    def clipTrimPreview(self, tl_obj, position):
        """
        While a clip is being trimmed, show a live preview of it.
        """
        if isinstance(tl_obj, GES.TitleClip) or tl_obj.props.is_image or not hasattr(tl_obj, "get_uri"):
            self.log("%s is an image or has no URI, so not previewing trim" % tl_obj)
            return False

        clip_uri = tl_obj.props.uri
        cur_time = time()
        if not self._tmp_pipeline:
            self.debug("Creating temporary pipeline for clip %s, position %s",
                clip_uri, print_ns(position))

            self._oldTimelinePos = self.pipeline.getPosition()
            self._tmp_pipeline = Gst.ElementFactory.make("playbin", None)
            self._tmp_pipeline.set_property("uri", clip_uri)
            self.setPipeline(SimplePipeline(self._tmp_pipeline, self._tmp_pipeline))
            self._lastClipTrimTime = cur_time
        if (cur_time - self._lastClipTrimTime) > 0.2:
            # Do not seek more than once every 200 ms (for performance)
            self._tmp_pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, position)
            self._lastClipTrimTime = cur_time

    def clipTrimPreviewFinished(self):
        """
        After trimming a clip, reset the project pipeline into the viewer.
        """
        if self._tmp_pipeline is not None:
            self._tmp_pipeline.set_state(Gst.State.NULL)
            self._tmp_pipeline = None  # Free the memory
            self.setPipeline(self.app.current.pipeline, self._oldTimelinePos)
            self.debug("Back to old pipeline")

    def _pipelineStateChangedCb(self, pipeline, state):
        """
        When playback starts/stops, update the viewer widget,
        play/pause button and (un)inhibit the screensaver.

        This is meant to be called by mainwindow.
        """
        self.info("current state changed : %s", state)
        if int(state) == int(Gst.State.PLAYING):
            self.playpause_button.setPause()
        elif int(state) == int(Gst.State.PAUSED):
            self.playpause_button.setPlay()
        else:
            self.sink = None
        self.internal._currentStateCb(self.pipeline, state)

    def _switch_output_window(self):
        Gdk.threads_enter()
        # Prevent cases where target has no "window_xid" (yes, it happens!):
        self.target.show()
        self.sink.set_window_handle(self.target.window_xid)
        self.sink.expose()
        Gdk.threads_leave()

class ViewerWidget(Gtk.DrawingArea, Loggable):
    """
    Widget for displaying properly GStreamer video sink

    @ivar settings: The settings of the application.
    @type settings: L{GlobalSettings}
    """

    __gsignals__ = {}

    def __init__(self, settings=None):
        Gtk.DrawingArea.__init__(self)
        Loggable.__init__(self)
        self.seeker = Seeker()
        self.settings = settings
        self.box = None
        self.stored = False
        self.area = None
        self.zoom = 1.0
        self.sink = None
        self.pixbuf = None
        self.pipeline = None
        self.transformation_properties = None
        # FIXME PyGi Styling with Gtk3
        #for state in range(Gtk.StateType.INSENSITIVE + 1):
            #self.modify_bg(state, self.style.black)

    def init_transformation_events(self):
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK
                        | Gdk.EventMask.POINTER_MOTION_HINT_MASK)

    def show_box(self):
        if not self.box:
            self.box = TransformationBox(self.settings)
            self.box.init_size(self.area)
            self._update_gradient()
            self.connect("button-press-event", self.button_press_event)
            self.connect("button-release-event", self.button_release_event)
            self.connect("motion-notify-event", self.motion_notify_event)
            self.connect("size-allocate", self._sizeCb)
            self.box.set_transformation_properties(self.transformation_properties)
            self.renderbox()

    def _sizeCb(self, widget, area):
        # The transformation box is cleared when using regular rendering
        # so we need to flush the pipeline
        self.seeker.flush()

    def hide_box(self):
        if self.box:
            self.box = None
            self.disconnect_by_func(self.button_press_event)
            self.disconnect_by_func(self.button_release_event)
            self.disconnect_by_func(self.motion_notify_event)
            self.seeker.flush()
            self.zoom = 1.0
            if self.sink:
                self.sink.set_render_rectangle(*self.area)

    def set_transformation_properties(self, transformation_properties):
            self.transformation_properties = transformation_properties

    def _store_pixbuf(self):
        """
        When not playing, store a pixbuf of the current viewer image.
        This will allow it to be restored for the transformation box.
        """

        if self.box and self.zoom != 1.0:
            # The transformation box is active and dezoomed
            # crop away 1 pixel border to avoid artefacts on the pixbuf

            self.pixbuf = Gdk.pixbuf_get_from_window(self.get_window(),
                self.box.area.x + 1, self.box.area.y + 1,
                self.box.area.width - 2, self.box.area.height - 2)
        else:
            self.pixbuf = Gdk.pixbuf_get_from_window(self.get_window(),
                0, 0,
                self.get_window().get_width(),
                self.get_window().get_height())

        self.stored = True

    def do_realize(self):
        """
        Redefine gtk DrawingArea's do_realize method to handle multiple OSes.
        This is called when creating the widget to get the window ID.
        """
        Gtk.DrawingArea.do_realize(self)
        if platform.system() == 'Windows':
            self.window_xid = self.props.window.handle
        else:
            self.window_xid = self.get_property('window').get_xid()

    def button_release_event(self, widget, event):
        if event.button == 1:
            self.box.update_effect_properties()
            self.box.release_point()
            self.seeker.flush()
            self.stored = False
        return True

    def button_press_event(self, widget, event):
        if event.button == 1:
            self.box.select_point(event)
        return True

    def _currentStateCb(self, pipeline, state):
        self.pipeline = pipeline
        if state == Gst.State.PAUSED:
            self._store_pixbuf()
        self.renderbox()

    def motion_notify_event(self, widget, event):
        if event.get_state() & Gdk.ModifierType.BUTTON1_MASK:
            if self.box.transform(event):
                if self.stored:
                    self.renderbox()
        return True

    def do_expose_event(self, event):
        self.area = event.area
        if self.box:
            self._update_gradient()
            if self.zoom != 1.0:
                width = int(float(self.area.width) * self.zoom)
                height = int(float(self.area.height) * self.zoom)
                area = ((self.area.width - width) / 2,
                        (self.area.height - height) / 2,
                        width, height)
                self.sink.set_render_rectangle(*area)
            else:
                area = self.area
            self.box.update_size(area)
            self.renderbox()

    def _update_gradient(self):
        self.gradient_background = cairo.LinearGradient(0, 0, 0, self.area.height)
        self.gradient_background.add_color_stop_rgb(0.00, .1, .1, .1)
        self.gradient_background.add_color_stop_rgb(0.50, .2, .2, .2)
        self.gradient_background.add_color_stop_rgb(1.00, .5, .5, .5)

    def renderbox(self):
        if self.box:
            cr = self.window.cairo_create()
            cr.push_group()

            if self.zoom != 1.0:
                # draw some nice background for zoom out
                cr.set_source(self.gradient_background)
                cr.rectangle(0, 0, self.area.width, self.area.height)
                cr.fill()

                # translate the drawing of the zoomed out box
                cr.translate(self.box.area.x, self.box.area.y)

            # clear the drawingarea with the last known clean video frame
            # translate when zoomed out
            if self.pixbuf:
                if self.box.area.width != self.pixbuf.get_width():
                    scale = float(self.box.area.width) / float(self.pixbuf.get_width())
                    cr.save()
                    cr.scale(scale, scale)
                cr.set_source_pixbuf(self.pixbuf, 0, 0)
                cr.paint()
                if self.box.area.width != self.pixbuf.get_width():
                    cr.restore()

            if self.pipeline and self.pipeline.get_state()[1] == Gst.State.PAUSED:
                self.box.draw(cr)
            cr.pop_group_to_source()
            cr.paint()


class PlayPauseButton(Gtk.Button, Loggable):
    """
    Double state Gtk.Button which displays play/pause
    """
    __gsignals__ = {
        "play": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_BOOLEAN,))
    }

    def __init__(self):
        Gtk.Button.__init__(self)
        Loggable.__init__(self)
        self.image = Gtk.Image()
        self.add(self.image)
        self.playing = False
        self.setPlay()
        self.connect('clicked', self._clickedCb)

    def set_sensitive(self, value):
        Gtk.Button.set_sensitive(self, value)

    def _clickedCb(self, unused):
        self.playing = not self.playing
        self.emit("play", self.playing)

    def setPlay(self):
        """ display the play image """
        self.log("setPlay")
        self.playing = True
        self.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_MEDIA_PLAY, Gtk.IconSize.BUTTON))
        self.set_tooltip_text(_("Play"))
        self.playing = False

    def setPause(self):
        self.log("setPause")
        """ display the pause image """
        self.playing = False
        self.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_MEDIA_PAUSE, Gtk.IconSize.BUTTON))
        self.set_tooltip_text(_("Pause"))
        self.playing = True
