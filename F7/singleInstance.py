import sys
from abc import ABC, ABCMeta, abstractmethod

from PyQt6.QtCore import QByteArray
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMainWindow

SERVER_NAME = "slick_launcher"  # Ensure this is unique


def send_socket_command(command: str):
    """Sends a command to an existing instance."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(1000):
        socket.write(command.encode())
        socket.waitForBytesWritten()
        socket.disconnectFromServer()
        return True
    return False


# Create a new metaclass that inherits from both
class Meta(type(QMainWindow), ABCMeta):  # type: ignore
    pass


class singleInstance(QMainWindow, metaclass=Meta):
    def __init__(self):

        # Set up the local server
        self.server = QLocalServer()
        self.server.newConnection.connect(self.handle_new_connection)
        self.setup_server()

        super().__init__()

    def setup_server(self):
        """Starts the local server, ensuring single instance."""
        # Remove any existing server (in case of crash), note that QLocalServer.removeServer return true if there was a server like that.
        QLocalServer.removeServer(SERVER_NAME)
        if not self.server.listen(SERVER_NAME):
            print("Failed to start single instance server.", file=sys.stderr)
            sys.exit(1)

    def handle_new_connection(self):
        """Handles incoming connections and processes commands."""
        socket = self.server.nextPendingConnection()
        if socket:
            socket.readyRead.connect(lambda: self._process_command(socket))

    def _process_command(self, socket):
        """Reads data from the socket and acts on it."""
        data = socket.readAll().data().decode()
        self.process_socket_command(data)
        socket.disconnectFromServer()

    @abstractmethod
    def process_socket_command(cls, data: str):
        raise NotImplementedError()
