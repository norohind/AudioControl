import queue
from queue import Queue
from threading import Thread
from loguru import logger
import Events
# from typing import TypedDict
from dataclasses import asdict

from TransportABC import TransportABC
from NetworkTransport import NetworkTransport


# class SessionState(TypedDict):
#     pid: int
#     volume: float
#     is_muted: bool
#     is_active: bool
#     name: str


class ServerSideView(Thread):
    """
    The `AudioController` gets called by callbacks, callbacks calls performs from
    threads which we shouldn't block for long time, so it would be wisely to put result of a callback to a
    queue which reads `ServerSideView` from its own thread.
    The common concept:
    `AudioController` put messages from callbacks to queue which reads `ServerSideView` which keep up with
    `ClientSideView` (a client).
    `ClientSideView` sends `Events` over `Transport` to `ServerSideView`. `Transport` calls `ServerSideView` callback
    which put messages to queue which is reading by `AudioController` which performs action specified in messages.
    `AudioController`'s work with queues performs in main thread.
    Callback calls by pycaw performs in pycaw's internal threads.
    `ServerSideView` executing in its own thread.
    """

    daemon = True
    running = True

    def __init__(self, inbound_q: Queue, outbound_q: Queue):
        """
        :param inbound_q: Queue from AudioController to ServerSideView
        :param outbound_q: Queue from ServerSideView to AudioController
        """
        super().__init__()
        self.inbound_q = inbound_q
        self.outbound_q = outbound_q

        self.transport: TransportABC = NetworkTransport(self.rcv_callback)

        self._state: dict[int, dict[str, int | float | str]] = dict()  # Holds current state of sessions received from AudioController
        # PID : SessionState

    def rcv_callback(self, event: Events.ClientToServerEvent):
        if isinstance(event, Events.NewClient):
            self.inbound_q.put(event)

        else:
            self.outbound_q.put(event)

    def run(self) -> None:
        while self.running:
            try:
                msg: Events.Event = self.inbound_q.get(timeout=0.1)

            except queue.Empty:
                pass

            else:
                # logger.debug(msg)
                if isinstance(msg, Events.ServerToClientEvent):
                    self._update_state(msg)
                    self.transport.send(msg)

                elif isinstance(msg, Events.NewClient):
                    self._send_full_state()

                else:
                    logger.warning(f'Unknown event {msg}')

            self.transport.tick()

        self.transport.shutdown()

    def _update_state(self, event: Events.ServerToClientEvent) -> None:
        if isinstance(event, Events.NewSession):
            self._state[event.PID] = dict()

        elif isinstance(event, Events.SessionClosed):
            del self._state[event.PID]

        else:
            dicted = asdict(event)
            del dicted['event']

            self._state[event.PID].update(dicted)

        # logger.trace(f'state: {self._state}')

    def _send_full_state(self):
        """Send full state of sessions to clients"""
        logger.trace(f'Sending full state')
        subclasses = tuple(Events.enumerate_subclasses(Events.ServerToClientEvent))
        for session in self._state.values():
            for cls in subclasses:
                if cls.__name__ == 'SessionClosed':
                    continue

                try:
                    kwargs = dict()
                    for field in cls.__dict__['__dataclass_fields__'].keys():
                        if field != 'event':
                            # args.append(session[field])
                            kwargs[field] = session[field]

                    event: Events.ServerToClientEvent = cls(**kwargs) # Noqa
                    self.transport.send(event)

                except KeyError:  # We don't have appropriate field in state for this kind of events
                    # logger.debug(f'Passing {cls}')
                    pass
