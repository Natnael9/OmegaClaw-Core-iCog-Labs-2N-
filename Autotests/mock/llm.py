from .rpc import Rpc, IPCClient, IPCServer, HOST_DEFAULT, PORT_DEFAULT
from contextlib import contextmanager

class LlmMockAgent:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self.rpc = Rpc(IPCServer(address))
        self.rpc.on_request('set_answer', lambda args: self.on_set_answer(args))
        self.rpc.start()
        self.answers = {}

    def stop(self, timeout=None):
        self.rpc.stop(timeout)

    def chat(self, content):
        answer = self.answers.get(content)
        if answer:
            return answer
        else:
            print(f"Mock doesn't have answer for: {content}")
            return ""

    def on_set_answer(self, args):
        self.answers[args['request']] = args['response']
        return True

class LlmMockController:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self.rpc = Rpc(IPCClient(address))
        self.rpc.start()

    def stop(self, timeout=None):
        self.rpc.stop(timeout)

    def set_answer(self, request, response, timeout=10):
        result = self.rpc.request('set_answer', { 'request': request, 'response': response })
        if result.get(timeout) != True:
            print(f"Cannot set answer to the mock, error: {result.error()}")
            return False
        return True

def llm_mock_controller(*args, **kwargs) -> LlmMockController:
    controller = LlmMockController(*args, **kwargs)
    try:
        yield controller
    finally:
        controller.stop(5)
