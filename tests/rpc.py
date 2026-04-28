import multiprocessing.connection as conn
import logging
import threading
import time

HOST_DEFAULT = "localhost"
PORT_DEFAULT = 9765
TIMEOUT_DEFAULT = 5

class Shared:

    def __init__(self, value=None):
        self._lock = threading.Lock()
        with self._lock:
            self._value = value

    def get(self, getter=lambda x: x):
        with self._lock:
            return getter(self._value)

    def set(self, value):
        with self._lock:
            self._value = value

    def map(self, f):
        with self._lock:
            self._value = f(self._value)

class Queue:

    def __init__(self):
        self._lock = threading.Lock()
        self._queue = []

    def push_back(self, item):
        with self._lock:
            self._queue.append(item)

    def front(self):
        with self._lock:
            if len(self._queue) == 0:
                return None
            return self._queue[0]

    def pop_front(self):
        with self._lock:
            return self._queue.pop(0)

class Future:

    def __init__(self):
        self._value = None
        self._error = None
        self._lock = threading.Lock()
        self._recieved = threading.Condition(self._lock)

    def is_error(self):
        with self._lock:
            return self._error is not None

    def error(self):
        with self._lock:
            return self._error

    def get(self, timeout=None):
        with self._lock:
            self._recieved.wait_for(lambda: self._value or self._error, timeout)
            if self._error:
                raise self._error
            return self._value

    def _set(self, value):
        with self._lock:
            self._value = value
            self._recieved.notify_all()

    def _set_error(self, error):
        with self._lock:
            self._error = error
            self._recieved.notify_all()

class Request:

    def __init__(self, id, method, param):
        self.id = id
        self.method = method
        self.param = param

    def __repr__(self):
        return f'Request[id={self.id}, method={self.method}, param={self.param}'

class Response:

    def __init__(self, id, result):
        self.id = id
        self.result = result

    def __repr__(self):
        return f'Response[id={self.id}, result={self.result}'

class ConnectionTransport:

    def __init__(self, connect):
        self._conn = None
        self._connect = connect
        self._is_stopped = Shared(False)
        self._output = Queue()
        self._handler = Shared(None)
        self._thread = threading.Thread(target=ConnectionTransport._run,
                                       args=[self], daemon=True)

    def set_handler(self, handler):
        self._handler.set(handler)
        assert not self._thread.is_alive()

    def send(self, msg):
        self._output.push_back(msg)

    def start(self):
        self._thread.start()

    def stop(self):
        self._is_stopped.set(True)
        self._thread.join(TIMEOUT_DEFAULT)
        if self._thread.is_alive():
            logging.error(f'Could not stop working thread')

    def _send(self, msg):
        if not self._conn:
            return False
        try:
            self._conn.send(msg)
            return True
        except Exception as e:
            logging.error(f'Exception on _send: {repr(e)}')
            return False

    def _recv(self):
        if not self._conn:
            return False
        try:
            if self._conn.poll():
                return self._conn.recv()
            else:
                return None
        except EOFError as e:
            logging.warning(f'Closing connection after _recv error: {repr(e)}')
            self._conn = None
            return None
        except OSError as e:
            logging.warning(f'Closing connection after _recv error: {repr(e)}')
            self._conn = None
            return None
        except Exception as e:
            logging.error(f'Exception on _recv: {repr(e)}')
            return None

    def _run(self):
        while not self._is_stopped.get():
            if self._conn:
                # send messages
                while True:
                    msg = self._output.front()
                    if not msg:
                        break
                    logging.info(f'Sending msg: {msg}')
                    if self._send(msg):
                        logging.info(f'Message sent')
                        self._output.pop_front()

                # receive messages
                while True:
                    msg = self._recv()
                    if not msg:
                        break
                    logging.info(f'Recieved msg: {msg}')
                    self._handler.get()(msg)
            else:
                self._conn = self._connect()

            time.sleep(0.1)

class IPCServer:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self._listener = conn.Listener(address)
        self._transport = ConnectionTransport(lambda: self._connect())

    def _connect(self):
        try:
            logging.info(f'Listening on: {self._listener.address}')
            c = self._listener.accept()
            logging.info(f'Connected')
            return c
        except Exception as e:
            logging.error(f'Exception on accepting the incoming connection: {repr(e)}')
            return None

    def start(self):
        self._transport.start()

    def stop(self):
        self._listener.close()
        self._transport.stop()

    def set_handler(self, handler):
        self._transport.set_handler(handler)

    def send(self, msg):
        self._transport.send(msg)

class IPCClient():

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self._address = address
        self._transport = ConnectionTransport(lambda: self._connect())

    def _connect(self):
        try:
            logging.info(f'Connecting to: {self._address}')
            c = conn.Client(self._address)
            logging.info(f'Connected')
            return c
        except Exception as e:
            logging.error(f'Exception on trying to connect to address {self._address}: {repr(e)}')
            return None

    def start(self):
        self._transport.start()

    def stop(self):
        self._transport.stop()

    def set_handler(self, handler):
        self._transport.set_handler(handler)

    def send(self, msg):
        self._transport.send(msg)

class Rpc:

    def __init__(self, ipc):
        self._next_request_id = 0
        self._ipc = ipc
        ipc.set_handler(lambda msg: self._on_incoming(msg))
        self._futures = Shared({})
        self._handlers = Shared({})

    def _get_next_request_id(self):
        next_request_id = self._next_request_id
        self._next_request_id += 1
        return next_request_id

    def _on_incoming(self, msg):
        if isinstance(msg, Response):
            response = msg
            future = self._futures.get(lambda f: f.pop(response.id, None))
            if not future:
                logging.warning(f'Response for non-existing request: {response.id}')
            else:
                future._set(response.result)

        if isinstance(msg, Request):
            request = msg
            handler = self._handlers.get(lambda h: h.get(request.method))
            if handler:
                result = handler(request.param)
                self._ipc.send(Response(request.id, result))
            else:
                logging.error(f'No handler for request: {request}')

    def on_request(self, method, handler):
        self._handlers.map(lambda h: h | { method: handler })

    def request(self, method, param):
        id = self._get_next_request_id()
        self._ipc.send(Request(id, method, param))
        future = Future()
        self._futures.map(lambda f: f | { id: future })
        return future

    def start(self):
        self._ipc.start()

    def stop(self):
        self._ipc.stop()

# Unit tests

class TestClass:

    import pytest

    def setup_class(cls):
        def thread_id_filter(record):
            record.thread_id = threading.get_native_id()
            return record

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(levelname)s] [%(thread_id)d]: %(message)s'))
        handler.addFilter(thread_id_filter)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)

    @pytest.fixture
    def server(self):
        server = Rpc(IPCServer())
        server.start()
        yield server
        server.stop()

    @pytest.fixture
    def client(self):
        client = Rpc(IPCClient())
        client.start()
        yield client
        client.stop()

    def test_request_from_server_to_client(self, server, client):
        def foo(param):
            assert param == { 'arg': 'abcd' }
            return { 'result': 'dcba' }
        client.on_request('foo', foo)
        response = server.request('foo', { 'arg': 'abcd' })
        assert response.get(1) == { 'result': 'dcba' }


    def test_request_from_client_to_server(self, server, client):
        def foo(param):
            assert param == { 'arg': 'abcd' }
            return { 'result': 'dcba' }
        server.on_request('foo', foo)
        response = client.request('foo', { 'arg': 'abcd' })
        assert response.get(1) == { 'result': 'dcba' }

    def test_request_client_reconnect(self, server, client):
        def foo(param):
            assert param == { 'arg': 'abcd' }
            return { 'result': 'dcba' }
        client.on_request('foo', foo)
        response = server.request('foo', { 'arg': 'abcd' })
        assert response.get(1) == { 'result': 'dcba' }

        client._ipc._transport._conn.close()
        response = server.request('foo', { 'arg': 'abcd' })
        assert response.get(1) == { 'result': 'dcba' }

    def test_send(self):
        client = Rpc(IPCClient())
        resp = client.request('foo', 'arg')
        assert resp

