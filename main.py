import sys; sys.coinit_flags = 0  # noqa
from loguru import logger
import logging
import signal


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()])

from pycaw.pycaw import AudioUtilities
import AudioController


mgr = AudioUtilities.GetAudioSessionManager()

audio_controller = AudioController.AudioController()

signal.signal(signal.SIGTERM, audio_controller.shutdown_callback)
signal.signal(signal.SIGINT, audio_controller.shutdown_callback)

callback = AudioController.SessionCreateCallback(audio_controller)

mgr.RegisterSessionNotification(callback)
mgr.GetSessionEnumerator()

try:
    audio_controller.start_blocking()

except KeyboardInterrupt:
    pass

finally:
    mgr.UnregisterSessionNotification(callback)
    audio_controller.pre_shutdown()
