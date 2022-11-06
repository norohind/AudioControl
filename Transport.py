from loguru import logger
from dataclasses import asdict
import socket
import selectors
from queue import Queue
import Events
import json


class Transport:
    def __init__(self):
        self._selector = selectors.DefaultSelector()
        self._from_net_q = Queue()

        self._sock = socket.socket()
        self._sock.bind(('localhost', 54683))
        self._sock.listen(100)
        self._sock.setblocking(False)
        self._selector.register(self._sock, selectors.EVENT_READ, self._accept)

        self._connections: list[socket.socket] = list()
        # self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # self.sock.bind(("127.0.0.1", 54683))
        ...

    def send(self, msg: Events.ServerToClientEvent):
        logger.debug(f'Sending {asdict(msg)}')
        msg = json.dumps(asdict(msg)).encode()
        for conn in self._connections:
            conn.sendall(msg)

    def receive(self) -> Events.ClientToServerEvent:
        return self._from_net_q.get_nowait()

    def _accept(self, sock: socket.socket, mask: int):
        conn, addr = sock.accept()  # Should be ready
        print('accepted', conn, 'from', addr)
        conn.setblocking(False)
        self._selector.register(conn, selectors.EVENT_READ, self._read)
        self._connections.append(conn)

    def _read(self, conn: socket.socket, mask: int):
        data = conn.recv(1000)
        if not data:
            logger.debug(f'Closing connection to {conn.getpeername()}')
            self._selector.unregister(conn)
            self._connections.remove(conn)
            conn.close()
            return

        try:
            event_dict = json.loads(data)
            event_name = event_dict['event']
            event_cls = Events.lookup_event(event_name)
            del event_dict['event']
            logger.trace(f'Passing msg {event_dict} from client {conn.getpeername()}')
            self._from_net_q.put(event_cls(**event_dict))

        except Exception:
            logger.opt(exception=True).warning(f"Couldn't parse message from client: {data}")

    def tick(self):
        events = self._selector.select(timeout=0)
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)
