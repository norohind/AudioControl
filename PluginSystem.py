import os
import importlib
import typing
from time import sleep

from loguru import logger

from PluginABC import PluginABC
from AudioSessionState import AudioSessionState

PLUGINS_DIR: typing.Final = 'plugins'


class PluginSystem:
    """Class performs communication with plugins"""

    def __init__(self):
        self._id_counter = 0
        self._plugins: dict[int, PluginABC] = dict()
        self.keep_ticking = True

    def shutdown(self, *args):
        self.keep_ticking = False

    def _plugin_load(self, plugin_path: typing.AnyStr, plugin_name: str):
        try:
            module = importlib.machinery.SourceFileLoader(plugin_name, plugin_path).load_module()
            cls: type[PluginABC] = getattr(module, plugin_name, None)
            constructor = getattr(cls, '__init__', None)
            if not callable(constructor):
                raise AttributeError(f'No __init__ method in {plugin_name} plugin')

            instance = cls(self, self._id_counter)
            if not isinstance(instance, PluginABC):
                raise ValueError('Plugin class must be instance of PluginABC')

            self._plugins[self._id_counter] = instance
            self._id_counter += 1

        except Exception:
            logger.opt(exception=True).warning(f'Failed to load plugin {plugin_path!r} - {plugin_name!r}')

    def plugins_load(self):
        if len(self._plugins) > 0:
            logger.warning(f"Can't load plugins twice")
            return

        for file_name in sorted(os.listdir(PLUGINS_DIR)):
            if file_name.endswith('.py') and not file_name[0] in ['.', '_']:
                path = os.path.join(PLUGINS_DIR, file_name)
                plugin_name = file_name[:-3]
                self._plugin_load(path, plugin_name)

    def _plugins_stop(self):
        for plugin in self._plugins.values():
            plugin.stop()

    def handle_session_change(self, session: AudioSessionState) -> None:
        logger.debug(session)

    def remove_session(self, plugin_id: int, session_id: int) -> None:
        logger.debug(f'{plugin_id} - {session_id}')

    def ticking(self) -> None:
        while self.keep_ticking:
            sleep(0.1)
            for plugin in self._plugins.values():
                plugin.tick()

        self._plugins_stop()


if __name__ == '__main__':
    ps = PluginSystem()
    import signal
    signal.signal(signal.SIGINT, ps.shutdown)
    signal.signal(signal.SIGTERM, ps.shutdown)

    ps.plugins_load()
    ps.ticking()
