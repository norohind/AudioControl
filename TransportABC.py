from abc import ABC, abstractmethod
from typing import Callable

import Events


class TransportABC(ABC):
    @abstractmethod
    def __init__(self, rcv_callback: Callable[[Events.ClientToServerEvent], None]):
        """Should call rcv_callback in order to pass received from client event"""

    @abstractmethod
    def send(self, msg: Events.ServerToClientEvent):
        """This method gets called by `ServerSideView` when it has an event to send to client"""

    @abstractmethod
    def tick(self):
        """This method get called by `ServerSideView` every little piece of time in order to allow
        `Transport` to handle inbound messages (or other stuff `Transport` should do continuously"""

    @abstractmethod
    def shutdown(self):
        """Gets called by `ServerSideView` on program shutdown, the class should clean up all connections
         and such staff"""
