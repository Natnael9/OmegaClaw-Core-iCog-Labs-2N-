from rpc import Rpc, IPCClient, IPCServer, HOST_DEFAULT, PORT_DEFAULT
from contextlib import contextmanager
import threading

class LlmMockAgent:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self.lock = threading.Lock()
        self.answers = {}
        self.rpc = Rpc(IPCClient(address))
        self.rpc.on_request('set_answer', lambda args: self.on_set_answer(args))
        self.rpc.start()

    def stop(self, timeout=None):
        self.rpc.stop(timeout)

    def chat(self, content):
        user = content.rsplit(":-:-:-:", 1)
        if len(user) < 2:
            return ""

        try:
            body = eval(user[1])[1]
        except SyntaxError:
            return ""

        # IRC may deliver multiple PRIVMSGs in one agent iteration; the
        # agent concatenates them with " | " between speakers. Split
        # and look up each fragment individually so a registered answer
        # is not missed when several messages arrive together.
        fragments = body.split(" | ")
        answer = None
        matched = None
        for fragment in fragments:
            if ": " not in fragment:
                continue
            prompt = fragment.split(": ", 1)[1]
            with self.lock:
                a = self.answers.get(prompt)
            if a:
                answer = a
                matched = prompt

        if answer:
            print(f"[LlmMockAgent] Mock answers: {answer}")
            return answer
        else:
            print(f"[LlmMockAgent] Mock doesn't have answer for: {body}")
            return ""

    def on_set_answer(self, args):
        with self.lock:
            request = args['request']
            response = args['response']
            print(f'[LlmMockAgent] Mock request: "{request}" with response "{response}"')
            self.answers[request] = response

class LlmMockController:

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT)):
        self.rpc = Rpc(IPCServer(address))
        self.rpc.start()

    def stop(self, timeout=None):
        self.rpc.stop(timeout)

    def set_answer(self, request, response, timeout=10):
        result = self.rpc.request('set_answer', { 'request': request, 'response': response })
        if result.get(timeout) != True:
            print(f"[LlmMockController] Cannot set answer to the mock, error: {result.error()}")
            return False
        return True

@contextmanager
def llm_mock_controller(*args, **kwargs) -> LlmMockController:
    controller = LlmMockController(*args, **kwargs)
    try:
        yield controller
    finally:
        controller.stop(5)
