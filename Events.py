from dataclasses import dataclass, field

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

Cases:
1. New Session:
    Send `New Session` event
    Send `Name Changed` event
    Send `Volume Changed` event
    Send `Mute State Changed` event
    Send `State changed` event
    # Let's call this set of events a full view since it fully describes current information about a session

2. Session closed
    Send `Session closed` event
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
    new_volume: float


@dataclass
class MuteStateChanged(ServerToClientEvent):
    is_muted: bool


@dataclass
class SetName(ServerToClientEvent):
    name: str


# Client to Server Events

@dataclass
class VolumeIncrement(ClientToServerEvent):
    increment: float


@dataclass
class MuteToggle(ClientToServerEvent):
    ...


def lookup_event(event_name: str) -> Event:
    subclasses = dict()
    to_handle = [Event]
    while len(to_handle) > 0:
        current_item = to_handle.pop()
        for subclass in current_item.__subclasses__():
            subclasses[subclass.__name__] = subclass
            to_handle.append(subclass)

    return subclasses[event_name]
