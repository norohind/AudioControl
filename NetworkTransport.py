from typing import Callable
from loguru import logger
from dataclasses import asdict
import socket
import selectors
import Events
import json
from TransportABC import TransportABC


class NetworkTransport(TransportABC):
    def __init__(self, rcv_callback: Callable[[Events.ClientToServerEvent], None]):
        self._selector = selectors.DefaultSelector()
        self.view_rcv_callback = rcv_callback

        self._sock = socket.socket()
        self._sock.bind(('localhost', 54683))
        self._sock.listen(100)
        self._sock.setblocking(False)
        self._selector.register(self._sock, selectors.EVENT_READ, self._accept)
        self._running = True

        self._connections: list[socket.socket] = list()

    def send(self, msg: Events.ServerToClientEvent):
        """This method gets called by `ServerSideView` when it wants to send a message to the client"""

        # logger.debug(f'Sending {asdict(msg)}')
        msg = json.dumps(asdict(msg)).encode() + b'\n'  # TODO: Remove new line probably
        self._send_to_all(msg)

    def _send_to_all(self, msg: bytes):
        for conn in self._connections:
            conn.sendall(msg)

    def _accept(self, sock: socket.socket, mask: int):
        """Callback which get called when accepting new connection"""
        if not self._running:
            logger.debug(f'Net: New connection during shutdown {sock.getpeername()}, not accepting')
            return

        conn, addr = sock.accept()
        logger.debug(f'Net: Accepted {conn.getpeername()}')
        conn.setblocking(False)
        self._selector.register(conn, selectors.EVENT_READ, self._on_socket_receive)
        self._connections.append(conn)
        self.view_rcv_callback(Events.NewClient(-1))

    def _close_conn(self, conn: socket.socket):
        logger.debug(f'Net: Closing connection to {conn.getpeername()}')
        self._selector.unregister(conn)
        self._connections.remove(conn)
        conn.close()

    def _on_socket_receive(self, conn: socket.socket, mask: int):
        data = conn.recv(1000)
        if not data:
            self._close_conn(conn)
            return

        for data_part in data.split(b'\n'):
            if len(data_part) != 0:
                self._handle_received_event(data_part, conn)

    def _handle_received_event(self, data: bytes, conn: socket.socket):
        try:
            event_dict = json.loads(data)
            event_name = event_dict['event']
            event_cls = Events.lookup_event(event_name)
            del event_dict['event']
            logger.trace(f'Passing msg {event_dict} from client {conn.getpeername()}')
            event = event_cls(**event_dict)  # noqa
            self.view_rcv_callback(event)

        except Exception:
            logger.opt(colors=False, exception=True).warning(f"Couldn't parse message from client: {data}")

    def tick(self):
        events = self._selector.select(timeout=0)
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

    def shutdown(self):
        logger.debug(f'Net: Shutting down')
        self._running = False
        while len(self._connections) > 0:
            self._close_conn(self._connections[0])

        logger.trace(f'Net: Shutdown completed, clients disconnected')
