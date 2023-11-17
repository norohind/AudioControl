import typing
from time import time
from loguru import logger
import pyaimp

from PluginABC import PluginABC
if typing.TYPE_CHECKING:
    from PluginSystem import PluginSystem

from AudioSessionState import AudioSessionState


class AIMPPlugin(PluginABC):
    def __init__(self, plugin_system: 'PluginSystem', plugin_id: int):
        self.id = plugin_id
        self.ps = plugin_system
        self._prev_tick = time()
        self.tick_interval_secs = 1
        self._client: None | pyaimp.Client = None
        self._latest_state: None | AudioSessionState = None

    def _init_client(self) -> bool:
        if self._is_client_alive():
            return True

        try:
            self._client = pyaimp.Client()
            return True

        except RuntimeError:  # Unable to find AIMP window probably
            logger.opt(exception=True).trace(f'Failed to init AIMP client')
            return False

    def _is_client_alive(self) -> bool:
        if self._client is not None:
            is_alive = self._client.get_version() is not None
            if not is_alive:
                self._client = None

            return is_alive

        return False

    def _scheduled_tick(self):
        if self._init_client():
            state = AudioSessionState(
                plugin_id=self.id, id=0,
                is_active=self._client.get_playback_state() == pyaimp.PlayBackState.Playing, name='AIMP',
                volume=self._client.get_volume(), is_muted=self._client.is_muted()
            )
            if state != self._latest_state:
                self.ps.handle_session_change(state)
                self._latest_state = state

        else:  # If init failed we have to consider two situations
            if self._latest_state is not None:  # It is not long ago became like that (i.e. AIMP shutdown)
                self.ps.remove_session(self._latest_state.plugin_id, self._latest_state.id)
                self._latest_state = None

        # else: # If it is like that for a while then we have nothing to do

    def handle_new_state(self, new_state: AudioSessionState) -> None:
        if self._latest_state is None:
            logger.warning(f'Got new_state while _latest_state is None {new_state=}, {self._client=}')
            return

        if new_state.volume != self._latest_state.volume:
            self._client.set_volume(new_state.volume)

        if new_state.is_muted != self._latest_state.is_muted:
            self._client.set_muted(new_state.is_muted)

        # Note: We do not set new state to _latest_state to let _scheduled_tick detect state change and send it

    def tick(self) -> None:
        time_now = time()
        if (time_now - self._prev_tick) > self.tick_interval_secs:
            self._prev_tick = time_now
            self._scheduled_tick()

