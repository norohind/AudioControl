import queue

import comtypes
import psutil
from pycaw.utils import AudioSession
from pycaw.callbacks import AudioSessionEvents, AudioSessionNotification
from pycaw.pycaw import AudioUtilities

import Events
from ServerSideView import ServerSideView
from queue import Queue, Empty

from loguru import logger
from get_app_name import get_app_name


class PerSessionCallbacks(AudioSessionEvents):
    """Passing callbacks calls to AudioController and includes pid to calls"""

    def __init__(self, pid: int, audio_controller: 'AudioController'):
        self.pid = pid
        self.audio_controller = audio_controller
        self._is_muted: bool | None = None
        self._volume: int | None = None

    def on_simple_volume_changed(self, new_volume, new_mute, event_context):
        new_mute = bool(new_mute)
        new_volume = int(new_volume * 100)

        if new_mute != self._is_muted:
            self._is_muted = new_mute
            self.audio_controller.on_mute_changed(self.pid, self._is_muted)

        if new_volume != self._volume:
            self._volume = new_volume
            self.audio_controller.on_volume_changed(self.pid, self._volume, event_context)

    def on_state_changed(self, new_state, new_state_id):
        self.audio_controller.on_state_changed(self.pid, new_state, new_state_id)

    def on_session_disconnected(self, disconnect_reason, disconnect_reason_id):
        self.audio_controller.on_session_disconnected(self.pid, disconnect_reason, disconnect_reason_id)


class SessionCreateCallback(AudioSessionNotification):
    def __init__(self, audio_controller: 'AudioController'):
        self.audio_controller = audio_controller

    def on_session_created(self, new_session):
        self.audio_controller.on_session_created(new_session)


class AudioController:
    """
    Class aimed to keep current state of situation, handle callbacks from sessions, and do communication with clients
    vie ServerSideView
    """

    def __init__(self):
        self.running = True
        self.per_session_callbacks_class = PerSessionCallbacks
        self._sessions: dict[int, AudioSession] = dict()  # Mapping pid to session

        self.outbound_q = Queue()  # from AudioController to ServerSideView
        self.inbound_q = Queue()  # from ServerSideView to AudioController

        self._state_change_q = Queue()  # A queue for handling state changes as it seems to
        # work bad with all this logic in callback handler

        self.view = ServerSideView(self.outbound_q, self.inbound_q)

    def shutdown_callback(self, sig, frame):
        """Gets called by signal module as handler"""
        logger.info(f'Shutting down by signal {sig}')
        self.running = False

    def get_process(self, pid: int) -> psutil.Process:
        return self._sessions[pid].Process

    def perform_discover(self):
        logger.trace('Performing discovering')
        for session in AudioUtilities.GetAllSessions():
            logger.trace(f'Checking session {session.Process}')
            if session.Process is not None:
                # if session.ProcessId not in self._sessions:
                logger.debug(f'Discovered session {session.Process}')
                self.on_session_created(session)

                # else:
                #     logger.trace(f'Already have session {session.Process} in _sessions')

    def on_session_created(self, new_session: AudioSession):
        if new_session.Process is not None:
            logger.debug(f'New session {new_session.Process}')

            if new_session.ProcessId in self._sessions:
                logger.warning(f'Already have session {new_session.Process}, removing it first')
                self._remove_session_by_pid(new_session.ProcessId)

            self._sessions[new_session.ProcessId] = new_session
            new_session.register_notification(self.per_session_callbacks_class(new_session.ProcessId, self))

            # Notifying
            pid = new_session.ProcessId
            self.outbound_q.put(Events.NewSession(pid))
            self.outbound_q.put(Events.VolumeChanged(pid, self.get_volume(pid)))
            self.outbound_q.put(Events.SetName(pid, get_app_name(new_session.Process)))
            self.outbound_q.put(Events.MuteStateChanged(pid, self.is_muted(pid)))
            self.outbound_q.put(Events.StateChanged(pid, bool(self._sessions[pid].State)))

        else:
            logger.debug("None's process session", new_session, new_session.ProcessId)

    def on_volume_changed(self, pid: int, new_volume: int, event_context: 'comtypes.LP_GUID'):
        logger.debug(f'Volume changed {self.get_process(pid)}: new value: {new_volume}')
        self.outbound_q.put(Events.VolumeChanged(pid, new_volume))

    def on_mute_changed(self, pid, new_mute: bool):
        logger.debug(f'Mute changed {self.get_process(pid)}: new value: {new_mute}')
        self.outbound_q.put(Events.MuteStateChanged(pid, new_mute))

    def on_state_changed(self, pid: int, new_state: str, new_state_id: int):
        """
        There have been some problems with executing some amount of code on callbacks so took it out to main thread and
        in callbacks it only put messages to queue
        """

        logger.debug(f'State changed {self.get_process(pid).name()} {pid} new state: {new_state} {new_state_id}')
        self._state_change_q.put((pid, new_state_id))

    def _state_change_tick(self):
        try:
            msg = self._state_change_q.get_nowait()
            logger.trace(f'New state message {msg}')

        except Empty:
            return

        else:
            pid, new_state_id = msg
            if new_state_id == 2:
                self._generic_disconnect(pid)
                logger.trace(f'_generic_disconnect call done for {pid}')

            else:
                # Notifying
                self.outbound_q.put(Events.StateChanged(pid, bool(new_state_id)))

    def on_session_disconnected(self, pid: int, disconnect_reason, disconnect_reason_id):
        """
        Is fired, when the audio session disconnected "hard".
        Mostly on_state_changed == "Expired" is what you are looking for.
        see self.AudioSessionDisconnectReason for disconnect_reason
        The use is similar to on_state_changed (ref: pycaw.callbacks.AudioSessionEvents)
        NB: expired state id = 2
        """

        logger.info(f'Session disconnected {self.get_process(pid).name()} {pid} {disconnect_reason} {disconnect_reason_id}')
        self._generic_disconnect(pid)

    def _generic_disconnect(self, pid: int):
        """
        Session can be disconnected by on_session_disconnected event and by state = expired, this method gets called
        by both of them.

        :param pid:
        :return:
        """

        process = self.get_process(pid)
        if process.is_running():
            logger.warning(f'Process disconnected but still running {process}')

        # Notifying
        self.outbound_q.put(Events.SessionClosed(pid))
        logger.debug(f'Generic disconnect done')

        self._remove_session_by_pid(pid)
        logger.debug(f'Removing call done')

    def _remove_session_by_pid(self, pid: int):
        session = self._sessions[pid]
        session.unregister_notification()
        logger.trace(f'Successfully unregistered notification for {session._process}')
        del self._sessions[pid]
        logger.trace(f'Removing {pid} done')
        # print_stack()
        # return

    def pre_shutdown(self):
        """Unregister callbacks"""
        logger.trace(f'Entering pre_shutdown')
        for pid in tuple(self._sessions.keys()):
            try:
                self._remove_session_by_pid(pid)

            except Exception:
                logger.opt(exception=True).warning(f'Failed to unregister_notification() for pid {pid}')

        # Notify ServerSideView to stop
        self.view.running = False
        self.view.join(1)
        logger.trace(f'pre_shutdown completed')

    def set_mute(self, pid: int, is_muted: bool):
        logger.trace(f'Set mute for {pid} {is_muted=}')
        self._sessions[pid].SimpleAudioVolume.SetMute(int(is_muted), None)

    def is_muted(self, pid: int) -> bool:
        return bool(self._sessions[pid].SimpleAudioVolume.GetMute())

    def toggle_mute(self, pid: int):
        logger.trace(f'Toggle mute for {pid}')
        is_muted = self.is_muted(pid)
        self.set_mute(pid, not is_muted)

    def get_volume(self, pid: int) -> int:
        logger.trace(f'Get volume for {pid}')
        return int(self._sessions[pid].SimpleAudioVolume.GetMasterVolume() * 100)

    def set_volume(self, pid: int, volume: int):
        # only set volume in the range 0 to 100
        volume = min(100, max(0, volume))
        volume = float(volume) / 100
        self._sessions[pid].SimpleAudioVolume.SetMasterVolume(volume, None)

    def increment_volume(self, pid: int, increment: int):
        logger.trace(f'Increment volume for {pid}, {increment=}')
        volume = increment + self.get_volume(pid)
        self.set_volume(pid, volume)

    def _inbound_q_tick(self):
        try:
            event: Events.ClientToServerEvent = self.inbound_q.get(timeout=0.1)

        except queue.Empty:
            return

        else:
            try:
                self.get_process(event.PID)

            except KeyError:
                logger.warning(f'Event for unknown process {event}')
                return

            if isinstance(event, Events.VolumeIncrement):
                self.increment_volume(event.PID, event.increment)

            elif isinstance(event, Events.MuteToggle):
                self.toggle_mute(event.PID)

            elif isinstance(event, Events.SetVolume):
                self.set_volume(event.PID, event.volume)

    def start_blocking(self):
        # self.perform_discover()
        logger.debug(f'Starting blocking')
        self.view.start()
        while self.running:
            # time.sleep(1)
            self._state_change_tick()
            self._inbound_q_tick()
