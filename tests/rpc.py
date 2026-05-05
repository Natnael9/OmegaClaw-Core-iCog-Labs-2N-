import logging
import threading
import select
import pickle
import socket

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

class RingBuffer:

    def __init__(self, size=2 ** 20):
        self._buffer = bytearray(size)
        self._start = 0
        self._count = 0
        self._size = size
        self._lock = threading.RLock()
        self._read = threading.Condition(self._lock)

    def empty(self):
        with self._lock:
            return self._count == 0

    def full(self):
        with self._lock:
            return self._count == self._size

    def data(self):
        with self._lock:
            end = self._start + self._count
            if end > self._size:
                end = self._size
            return memoryview(self._buffer).toreadonly()[self._start : end]

    def mark_read(self, count):
        with self._lock:
            assert self._count >= count
            self._start = (self._start + count) % self._size
            self._count = self._count - count
            self._read.notify_all()

    def space(self):
        with self._lock:
            start = (self._start + self._count) % self._size
            end = self._start if start < self._start else self._size
            return memoryview(self._buffer)[start : end]

    def mark_write(self, count):
        with self._lock:
            assert self._count + count <= self._size
            self._count = self._count + count

    def write_blocking(self, data, timeout=None):
        with self._lock:
            size = len(data)
            assert self._size >= size
            if not self._read.wait_for(lambda: (self._size - self._count) >= size, timeout):
                return False
            end = (self._start + self._count) % self._size
            if end >= self._start:
                head_size = min(self._size - end, size)
                self._buffer[end : end + head_size] = data[0 : head_size]
                self._buffer[0 : size - head_size] = data[head_size : size]
            else:
                self._buffer[end : end + size] = data[0 : size]
            self.mark_write(size)
            return True

    def read_aot(self, size):
        with self._lock:
            assert self._size >= size
            if self._count < size:
                return None
            end = (self._start + self._count) % self._size
            if end >= self._start:
                return bytes(self._buffer[self._start : self._start + size])
            else:
                result = bytes(size)
                head_size = min(self._size - self._start, size)
                result[0 : head_size] = self._buffer[self._start : self._start + head_size]
                result[head_size : size] = self._buffer[0 : size - head_size]
                return result

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
        return f'Request[id={self.id}, method={self.method}, param={self.param}]'

class Response:

    def __init__(self, id, result):
        self.id = id
        self.result = result

    def __repr__(self):
        return f'Response[id={self.id}, result={self.result}]'

class ConnectionTransport:

    def __init__(self, connect):
        self._sock = None
        self._connect = connect
        self._poll = None
        self._output = RingBuffer()
        self._input = RingBuffer()
        self._is_stopped = Shared(False)
        self._handler = Shared(None)
        self._thread = threading.Thread(target=ConnectionTransport._run,
                                       args=[self], daemon=True)

    def set_handler(self, handler):
        self._handler.set(handler)
        assert not self._thread.is_alive()

    def send(self, msg):
        self._write_msg(msg)

    def _write_msg(self, msg):
        logging.debug(f'Writing message: {msg}')
        data = pickle.dumps(msg)
        size = len(data)
        assert self._output.write_blocking(int(size).to_bytes(4) + data)
        logging.debug(f'Message is written')

    def _read_msg(self):
        data = self._input.read_aot(4)
        if not data:
            return None
        size = int.from_bytes(data)
        logging.debug(f'Reading {size} bytes message')
        data = self._input.read_aot(4 + size)
        if not data:
            return None
        msg = pickle.loads(data[4:])
        self._input.mark_read(4 + size)
        logging.debug(f'Message is read: {msg}')
        return msg

    def start(self):
        self._thread.start()

    def stop(self, timeout=None):
        logging.info("Stopping transport")
        self._is_stopped.set(True)
        self._thread.join(timeout)
        if self._thread.is_alive():
            logging.error(f'Could not stop working thread in {timeout} seconds')

    def _close_connection(self):
        logging.info(f'Closing connection')
        try:
            if self._sock:
                self._sock.close()
        except Exception as e:
            logging.error(f'Exception on close: {repr(e)}')
        self._sock = None

    def _send(self):
        if not self._sock:
            return
        try:
            while True:
                data = self._output.data()
                to_be_sent = len(data)
                if to_be_sent == 0:
                    break
                count = self._sock.send(data, socket.MSG_DONTWAIT)
                if count > 0:
                    logging.debug(f'Sent {count} bytes of data')
                    self._output.mark_read(count)
                if count < to_be_sent:
                    break
        except Exception as e:
            logging.error(f'Exception on _send: {repr(e)}')
            self._close_connection()

    def _recv(self):
        if not self._sock:
            return
        try:
            while True:
                buffer = self._input.space()
                bufsize = len(buffer)
                if bufsize == 0:
                    break
                logging.debug(f'Wait for the data')
                count = self._sock.recv_into(buffer, bufsize, socket.MSG_DONTWAIT)
                if count > 0:
                    logging.debug(f'Received {count} bytes of data')
                    self._input.mark_write(count)
                if count < bufsize:
                    break
        except Exception as e:
            logging.error(f'Exception on _recv: {repr(e)}')
            self._close_connection()

    def _run(self):
        while not self._is_stopped.get():

            if not self._sock:
                self._sock = self._connect()
                if self._sock:
                    self._sock.setblocking(False)
                    self._poll = select.poll()
                    self._poll.register(self._sock.fileno())
            else:
                mask = select.POLLRDHUP
                if not self._output.empty():
                    mask = mask | select.POLLOUT
                if not self._input.full():
                    mask = mask | select.POLLIN

                self._poll.modify(self._sock.fileno(), mask)
                events = self._poll.poll(0.1)

                for (_, event) in events:
                    if (event & select.POLLIN) > 0:
                        self._recv()
                    if (event & select.POLLOUT) > 0:
                        self._send()
                    if (event & (select.POLLERR | select.POLLRDHUP |
                                 select.POLLHUP | select.POLLNVAL)) > 0:
                        def check(flag):
                            return f'{flag}' if (event & eval(f'select.{flag}')) > 0 else ''
                        flags = ["POLLERR", "POLLRDHUP", "POLLHUP", "POLLNVAL"]
                        errors = [check(f) for f in flags]
                        logging.error(f'Socket error event: ' + ' '.join(errors))
                        self._close_connection()

            while True:
                msg = self._read_msg()
                if not msg:
                    break
                self._handler.get()(msg)

        if self._sock:
            self._close_connection()

class IPCServer:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self._server = socket.create_server(address)
        self._server.setblocking(False)
        self._address = address
        self._transport = ConnectionTransport(lambda: self._connect())

    def _connect(self):
        try:
            logging.info(f'Listening on: {self._address}')
            c, a = self._server.accept()
            logging.info(f'Connected from {a}')
            return c
        except Exception as e:
            logging.error(f'Exception on accepting the incoming connection: {repr(e)}')
            return None

    def start(self):
        self._transport.start()

    def stop(self, timeout=None):
        self._server.close()
        self._transport.stop(timeout)

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
            c = socket.create_connection(self._address)
            if c:
                logging.info(f'Connected')
            return c
        except Exception as e:
            logging.error(f'Exception on trying to connect to address {self._address}: {repr(e)}')
            return None

    def start(self):
        self._transport.start()

    def stop(self, timeout=None):
        self._transport.stop(timeout)

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

    def stop(self, timeout=None):
        self._ipc.stop(timeout)

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
        logging.getLogger().handlers.clear()
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)

    @pytest.fixture
    def server(self):
        server = Rpc(IPCServer())
        server.start()
        yield server
        server.stop(5)

    @pytest.fixture
    def client(self):
        client = Rpc(IPCClient())
        client.start()
        yield client
        client.stop(5)

    def test_request_from_server_to_client(self, server, client):
        def foo(param):
            assert param == { 'arg': 'abcd' }
            return { 'result': 'dcba' }
        client.on_request('foo', foo)
        response = server.request('foo', { 'arg': 'abcd' })
        assert response.get(5) == { 'result': 'dcba' }


    def test_request_from_client_to_server(self, server, client):
        def foo(param):
            assert param == { 'arg': 'abcd' }
            return { 'result': 'dcba' }
        server.on_request('foo', foo)
        response = client.request('foo', { 'arg': 'abcd' })
        assert response.get(5) == { 'result': 'dcba' }

    def test_request_client_reconnect(self, server):
        def reverse(param):
            assert param.get('arg')
            return { 'result': param['arg'][::-1] }

        client = Rpc(IPCClient())
        client.on_request('reverse', reverse)
        client.start()
        response = server.request('reverse', { 'arg': 'abcd' })
        assert response.get(5) == { 'result': 'dcba' }
        client.stop(5)

        client = Rpc(IPCClient())
        client.on_request('reverse', reverse)
        client.start()
        response = server.request('reverse', { 'arg': 'cdef' })
        assert response.get(5) == { 'result': 'fedc' }
        client.stop(5)
