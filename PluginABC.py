import typing
from abc import ABC, abstractmethod

from AudioSessionState import AudioSessionState

if typing.TYPE_CHECKING:
    from PluginSystem import PluginSystem


class PluginABC(ABC):
    @abstractmethod
    def __init__(self, plugin_system: 'PluginSystem', plugin_id: int):
        raise NotImplementedError

    @abstractmethod
    def handle_new_state(self, new_state: AudioSessionState) -> None:
        raise NotImplementedError

    def tick(self) -> None:
        return

    def stop(self) -> None:
        return
