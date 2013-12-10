import os

DEBUG=0  # No real effect, will dump results from youtube gdata search if activated
RESULT_COLUMNS=3  # Display the thumbnails on this amount of columns
MINIMUM_DOWNLOADED_SIZE = 500000  # Wait for this number of bytes downloaded before playing

MUSIC_DIRECTORY=os.path.join(os.path.expanduser("~"), "Music")  # Place where to save converted media
VIDEO_DIRECTORY=os.path.join(os.path.expanduser("~"), "Videos")  # Place where to store downloaded media as is

# Gstreamer encoder to use, wavenc is another example, you can have a look at the available encoders
# with gst-inspect-1.0
AUDIO_ENCODER="lamemp3enc"
