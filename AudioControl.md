# AudioControl
A tool to remotely control audio volume of different things. It includes audio sessions in windows.
Easy extendable via plugin system.

## Architecture
`SessionProvider` provides unified interface to audio sessions.

`Controller` dispatches events from `SessionProvider`s to `TransportProvider`s and backward.

`TransportProvider` allows controller to communicate with clients using common interface

### Providers and Providers manager
A `SessionProvider` represent a source and way to control audio sessions.
There can be, for example, a `SessionProvider` for control over windows default mixer,  
`SessionProvider` for internal audio control of a decent software (i.e. an audio player).

`ProvidersManager` is piece that control both session and transport providers and allow `Controller` control it  
---------
Plugins must subclass and implement abstract methods of class `PluginABC`.
In order to be loadable, file with class must have same name as plugin class inside this file
(i.e. if you have plugin class called `MyPlugin` then you need to call file with plugin `MyPlugin`).
Let's take a look to methods you should define:
- `def __init__(self, plugin_system: 'PluginSystem')` - Constructor of a plugin will be called with one 
argument - instance of a `PluginSystem`.
Plugin should save given instance and use it to pass callbacks to plugin system.
- `def tick(self) -> None` (optional) - If you wish to implement your plugin in single thread style, the `PluginSystem` 
promises to call this method periodically (every 20ms let's say) in main thread, so you can perform some actions there.
- `def handle_new_state(self, new_state: AudioSessionState) -> None` - The `PluginSystem` calls this method with new state
when a client change something in a session. You should apply new state properties to specified session.
- `def stop(self) -> None` (optional) - This method gets called when the application shutting down.

`PluginSystem` Provides next interface for plugins:
- `def handle_session_change`(self, session: AudioSessionState) -> None` - Plugins should call it and pass new state
when they have new state. In order to create session plugins should simply pass new session state here.
- `def remove_session(self, plugin_id: int, session_id: int) -> None` - Plugins should call this method when they
want to remove a session.

Note: When a plugin applies new state through `handle_new_state` call, the plugin must supply updated state to 
`handle_session_change` of `PluginSystem`.

### Controller

### Transport
Transport is a way how to communicate with clients. Transports are loadable plugins