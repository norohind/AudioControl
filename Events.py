from typing import TypeVar, Generator
from dataclasses import dataclass, field
from functools import lru_cache

"""
Processes unique identifies by their PIDs.
From server to client events:
1. New session
    PID

2. Session closed
    PID

3. State changed
    PID
    is_active

4. Volume changed
    PID
    New volume

5. Mute state changed
    PID
    is_muted

6. Set name
    PID
    Name

From client to server:
1. Volume increment
    PID
    increment (for decrement use -increment value)

2. Mute toggle
    PID

3. New client
    *Literally nothing*
    # Set PID to any value
    # On this event `ServerSideView` should send full state to clients
    # Note: This event should be sent by Transport, not client itself

Cases:
1. New Session:
    Send `New Session` event
    Send `Name Changed` event
    Send `Volume Changed` event
    Send `Mute State Changed` event
    Send `State changed` event; Still TODO:
    # This set of events fully describes state of a session

2. Session closed:
    Send `Session closed` event

3. New client:
    Send events as in `New Session` case

Volume and volume increment as int in range 0 to 100
"""


@dataclass
class Event:
    PID: int
    event: str = field(init=False)

    def __post_init__(self):
        self.event = self.__class__.__name__


@dataclass
class ServerToClientEvent(Event):
    ...


@dataclass
class ClientToServerEvent(Event):
    ...


# Server to Client Events

@dataclass
class NewSession(ServerToClientEvent):
    ...


@dataclass
class SessionClosed(ServerToClientEvent):
    ...


@dataclass
class StateChanged(ServerToClientEvent):
    is_active: bool


@dataclass
class VolumeChanged(ServerToClientEvent):
    new_volume: int


@dataclass
class MuteStateChanged(ServerToClientEvent):
    is_muted: bool


@dataclass
class SetName(ServerToClientEvent):
    name: str


# Client to Server Events

@dataclass
class VolumeIncrement(ClientToServerEvent):
    increment: int


@dataclass
class MuteToggle(ClientToServerEvent):
    ...


@dataclass
class NewClient(ClientToServerEvent):
    ...


T = TypeVar('T')


@lru_cache
def lookup_event(event_name: str) -> Event:
    for cls in enumerate_subclasses(Event):
        if cls.__name__ == event_name:
            return cls

    raise ValueError(f'Lookup {event_name} failed')


def enumerate_subclasses(base: type[T]) -> Generator[T, None, None]:
    to_handle = [base]
    while len(to_handle) > 0:
        current_item = to_handle.pop()
        for subclass in current_item.__subclasses__():
            yield subclass
            to_handle.append(subclass)
