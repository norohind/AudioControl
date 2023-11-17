import sys; sys.coinit_flags = 0  # noqa
import signal
from pycaw.pycaw import AudioUtilities
from pycaw.callbacks import AudioSessionEvents, AudioSessionNotification
from loguru import logger
from time import sleep


class Globals:
    shutting_down = False


def shutdown_callback(*args):
    logger.info(f'Shutting down')
    Globals.shutting_down = True


class SessionCreateCallback(AudioSessionNotification):
    references = list()

    def on_session_created(self, new_session):
        logger.info(f'Session created: {new_session}')
        new_session.register_notification(SessionCallback(new_session.Process, 'by on_session_created'))
        self.references.append(new_session)


class SessionCallback(AudioSessionEvents):
    def __init__(self, process, obtained_via):
        self.process = getattr(process, '_name', None)
        self.ov = obtained_via

    def on_simple_volume_changed(self, new_volume, new_mute, event_context):
        logger.info(f'{self.process} - {new_volume} - {self.ov}')

    def on_state_changed(self, new_state, new_state_id):
        logger.info(f'{self.process} - {new_state} - {self.ov}')

    def on_session_disconnected(self, disconnect_reason, disconnect_reason_id):
        logger.info(f'{self.process} - {disconnect_reason} - {self.ov}')


def main():
    signal.signal(signal.SIGTERM, shutdown_callback)
    signal.signal(signal.SIGINT, shutdown_callback)

    mgr = AudioUtilities.GetAudioSessionManager()
    callback = SessionCreateCallback()
    mgr.RegisterSessionNotification(callback)
    mgr.GetSessionEnumerator()

    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        logger.info(f'Registering callback for {session}')
        session.register_notification(SessionCallback(session.Process, 'by initial discover'))

    while not Globals.shutting_down:
        sleep(0.1)

    mgr.UnregisterSessionNotification(callback)

    for session in sessions:
        logger.info(f'Unregistering callback for {session}')
        session.unregister_notification()


if __name__ == '__main__':
    main()
