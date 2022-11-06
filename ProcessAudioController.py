from pycaw.pycaw import AudioUtilities
import pycaw.utils
from get_app_name import get_app_name


def get_process_session(pid: int) -> pycaw.utils.AudioSession | None:
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.pid == pid:
            return session


class ProcessAudioController:
    def __init__(self, *, pid: int = None, audio_session: pycaw.utils.AudioSession = None):
        if pid is not None:
            self._process_session = get_process_session(pid)

        if audio_session is not None:
            self._process_session = audio_session

        self.process = self._process_session.Process
        self.process_description = get_app_name(self.process)

    def mute(self):
        self._process_session.SimpleAudioVolume.SetMute(1, None)
        print(self.process.name(), "has been muted.")  # debug

    def unmute(self):
        self._process_session.SimpleAudioVolume.SetMute(0, None)
        print(self.process.name(), "has been unmuted.")  # debug

    def get_process_volume(self):
        return self._process_session.SimpleAudioVolume.GetMasterVolume()

    @property
    def volume(self):
        return self.get_process_volume()

    def set_volume(self, decibels: float):
        new_volume = min(1.0, max(0.0, decibels))
        self._process_session.SimpleAudioVolume.SetMasterVolume(new_volume, None)
        print("Volume set to", new_volume)  # debug

    def decrease_volume(self, decibels: float):
        volume = max(0.0, self.volume - decibels)
        self._process_session.SimpleAudioVolume.SetMasterVolume(volume, None)
        print("Volume reduced to", volume)  # debug

    def increase_volume(self, decibels: float):
        # 1.0 is the max value, raise by decibels
        new_volume = min(1.0, self.volume + decibels)
        self._process_session.SimpleAudioVolume.SetMasterVolume(new_volume, None)
        print("Volume raised to", new_volume)  # debug


class AudioController:
    processes: dict[int, ProcessAudioController] = dict()  # PIDs as keys
    _selected_process: Optional[ProcessAudioController] = None

    def __init__(self, view: ViewABC):
        self.view = view
        for session in AudioUtilities.GetAllSessions():
            if session.ProcessId != 0:
                audio_process_controller = ProcessAudioController(audio_session=session)
                self.processes[audio_process_controller.process_description] = audio_process_controller

        if len(self.processes) > 0:
            self.selected_process = next(iter(self.processes))

    @property
    def selected_process(self) -> Optional[ProcessAudioController]:
        return self._selected_process

    @selected_process.setter
    def selected_process(self, pid_to_select: int):
        self._selected_process = self.processes[pid_to_select]
        self.view.select_process_callback(self.selected_process)

