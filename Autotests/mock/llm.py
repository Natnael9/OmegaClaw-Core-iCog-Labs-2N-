from .rpc import Rpc, IPCClient, IPCServer, HOST_DEFAULT, PORT_DEFAULT
from contextlib import contextmanager
import threading

class LlmMockAgent:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self._lock = threading.Lock()
        self._answers = {}
        self._rpc = Rpc(IPCClient(address))
        self._rpc.on_request('set_answer', lambda args: self.on_set_answer(args))
        self._rpc.on_request('ping', lambda args: self.on_ping(args))
        self._rpc.start()

    def stop(self, timeout=None):
        self._rpc.stop(timeout)

    def chat(self, content):
        user = content.rsplit(":-:-:-:", 1)
        if len(user) < 2:
            return ""

        try:
            msg = eval(user[1])[1].split(': ', 1)[1]
        except SyntaxError:
            return ""

        with self._lock:
            answer = self._answers.get(msg)
        if answer:
            print(f"[LlmMockAgent] Mock answers: {answer}")
            return answer
        else:
            print(f"[LlmMockAgent] Mock doesn't have answer for: {msg}")
            return ""

    def on_set_answer(self, args):
        with self._lock:
            request = args['request']
            response = args['response']
            print(f'[LlmMockAgent] Mock request: "{request}" with response "{response}"')
            self._answers[request] = response
            return True

    def on_ping(self, args):
        print(f'[LlmMockAgent] Mock ping request processed')
        return True

class LlmMockController:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self._rpc = Rpc(IPCServer(address))
        self._rpc.start()

    def stop(self, timeout=None):
        self._rpc.stop(timeout)

    def set_answer(self, request, response, timeout=10):
        result = self._rpc.request('set_answer', { 'request': request, 'response': response })
        if result.get(timeout) != True:
            print(f'[LlmMockController] Cannot set answer to the mock, error: {result.error()}')
            return False
        return True

    def ping(self, timeout=None):
        print(f'[LlmMockController] Ping agent')
        result = self._rpc.request('ping', {})
        if result.get(timeout) != True:
            print(f'[LlmMockController] Did not get answer on ping in {timeout} seconds')
            return False
        else:
            return True

@contextmanager
def llm_mock_controller(*args, **kwargs) -> LlmMockController:
    timeout = kwargs.pop("timeout", 30)
    controller = LlmMockController(*args, **kwargs)
    if not controller.ping(timeout):
        raise RuntimeError(f"Agent didn't answered in {timeout} seconds")
    try:
        yield controller
    finally:
        controller.stop(5)
