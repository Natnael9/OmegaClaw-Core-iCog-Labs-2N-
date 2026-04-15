import socket

HOST_DEFAULT = "localhost"
PORT_DEFAULT = 9765
TIMEOUT_DEFAULT = 5

_singletonClient = None
_singletonServer = None

class LlmMockStream:

    def __init__(self, sock):
        self.sock = sock
        self.buffer = ""

    def send(self, content):
        line = content + "\r\n"
        self.sock.sendall(line.encode(errors="ignore"))

    def read(self):
        while True:
            while "\r\n" in self.buffer:
                line, self.buffer = self.buffer.split("\r\n", 1)
                if not line:
                    continue
                return line
            data = self.sock.recv(4096).decode(errors="ignore")
            if not data:
                return None
            self.buffer += data


class LlmMockClient:

    def __init__(self, timeout=TIMEOUT_DEFAULT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)

    def __del__(self):
        if self.sock:
            self.sock.close()

    @staticmethod
    def singleton():
        global _singletonClient
        if _singletonClient is None:
            _singletonClient = LlmMockClient()
            _singletonClient.connect()
        return _singletonClient

    def connect(self, host=HOST_DEFAULT,
                port=PORT_DEFAULT):
        self.sock.connect((host, port))
        self.stream = LlmMockStream(self.sock)

    def chat(self, content):
        try:
            self.stream.send(content)
            return self.stream.read()
        except OSError:
            return ""


class LlmMockServer:

    def __init__(self, host=HOST_DEFAULT,
                 port=PORT_DEFAULT,
                 timeout=TIMEOUT_DEFAULT,
                 acceptTimeout=60):
        self.conn = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(acceptTimeout)
        self.sock.bind((host, port))
        self.sock.listen(1)
        self.timeout = timeout

    def __del__(self):
        if self.conn:
            self.conn.close()
        if self.sock:
            self.sock.close()

    @staticmethod
    def singleton():
        global _singletonServer
        if _singletonServer is None:
            _singletonServer = LlmMockServer()
            _singletonServer.accept()
        return _singletonServer

    def accept(self):
        self.conn, _addr = self.sock.accept()
        self.conn.settimeout(self.timeout)
        self.stream = LlmMockStream(self.conn)

    def send(self, content):
        self.stream.send(content)

    def read_line(self):
        return self.stream.read()
