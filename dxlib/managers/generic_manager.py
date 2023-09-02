import logging

from dxlib.api import HttpServer, WebSocketServer
from dxlib.core.logger import no_logger


class GenericManager:
    def __init__(self,
                 use_server: bool = False,
                 use_websocket: bool = False,
                 server_port: int = None,
                 websocket_port: int = None,
                 logger: logging.Logger = None
                 ):
        self.logger = logger if logger else no_logger(__name__)
        self.server = HttpServer(self, server_port, logger=self.logger) if use_server else None
        self.websocket = WebSocketServer(self, websocket_port, logger=self.logger) if use_websocket else None

        self.message_handler = None
        self.connection_handler = None

    def start(self):
        if self.server is not None:
            self.server.start()
        if self.websocket is not None:
            self.websocket.start()

    def stop(self):
        if self.server is not None:
            self.server.stop()
        if self.websocket is not None:
            self.websocket.stop()

    def is_alive(self):
        return (self.server.is_alive() or not self.server) and (self.websocket.is_alive() or not self.websocket)