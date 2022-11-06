import queue
from queue import Queue
from threading import Thread
from loguru import logger
import Events
from typing import TypedDict
from dataclasses import asdict
from Transport import Transport


class SessionState(TypedDict):
    pid: int
    volume: float
    is_muted: bool
    is_active: bool
    name: str


class ServerSideView(Thread):
    """
    The `AudioController` gets called by callbacks, callbacks calls performs from
    threads which we shouldn't block for long time, so it would be wisely to put result of a callback to a
    queue which reads `ServerSideView` from its own thread.
    The common concept:
    `AudioController` put messages from callbacks to queue which reads `ServerSideView` which keep up with
    `ClientSideView` (a client).
    `ClientSideView` sends `Events` over `Transport` to `ServerSideView` which put messages to another queue
    which reads `AudioController` which performs action specified in messages.
    `AudioController`'s work with queues performs in main thread.
    Callback calls by pycaw performs in pycaw's internal threads.
    `ServerSideView` executing in its own thread.
    """

    daemon = True

    def __init__(self, inbound_q: Queue, outbound_q: Queue, transport: Transport = Transport()):
        """
        :param inbound_q: Queue from AudioController to ServerSideView
        :param outbound_q: Queue from ServerSideView to AudioController
        """
        super().__init__()
        self.inbound_q = inbound_q
        self.outbound_q = outbound_q

        self.transport = transport

        self._state: dict[int, SessionState] = dict()  # Holds current state of sessions received from AudioController
        # PID : SessionState

    def run(self) -> None:
        while True:
            try:
                msg: Events.ServerToClientEvent = self.inbound_q.get_nowait()

            except queue.Empty:
                pass

            else:
                logger.debug(msg)
                self._update_state(msg)
                self.transport.send(msg)

            self.transport.tick()

            try:
                new_msg = self.transport.receive()
                self.outbound_q.put(new_msg)

            except queue.Empty:
                pass

    def _update_state(self, event: Events.ServerToClientEvent) -> None:
        if isinstance(event, Events.NewSession):
            self._state[event.PID] = dict()

        elif isinstance(event, Events.SessionClosed):
            del self._state[event.PID]

        else:
            dicted = asdict(event)
            del dicted['event']

            self._state[event.PID].update(dicted)

        logger.debug(f'state: {self._state}')
