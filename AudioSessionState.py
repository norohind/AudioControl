from dataclasses import dataclass, field

Unchanged = type('Unchanged', tuple(), dict())
unchanged = Unchanged()


@dataclass
class AudioSessionState:
    """Represent audio session """
    plugin_id: int  # Unique identifier of a plugin
    id: int  # Unique identifier of a session within plugin
    is_active: bool = unchanged
    is_muted: bool = unchanged
    name: str = unchanged  # Name of a session (i.e. name of a process)
    volume: int = unchanged  # Volume in range(0, 101)
