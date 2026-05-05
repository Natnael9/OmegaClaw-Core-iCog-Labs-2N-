import rpc

class LlmMockAgent:

    def __init__(self):
        self.rpc = rpc.Rpc(rpc.IPCServer())
        self.rpc.on_request('set_answer', lambda args: self.on_set_answer(args))
        self.rpc.start()
        self.answers = {}

    def stop(self):
        self.rpc.stop()

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

class LlmMockHarness:

    def __init__(self):
        self.rpc = rpc.Rpc(rpc.IPCClient())
        self.rpc.start()

    def stop(self):
        self.rpc.stop()

    def set_answer(self, request, response):
        result = self.rpc.request('set_answer', { 'request': request, 'response': response })
        if result.get(10) != True:
            print(f"Cannot set answer to the mock, error: {result.error()}")
            return False
        return True


class TestMock:

    import pytest

    def setup_class(cls):
        import logging
        import threading

        def thread_id_filter(record):
            record.thread_id = threading.get_native_id()
            return record

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(levelname)s] [%(thread_id)d]: %(message)s'))
        handler.addFilter(thread_id_filter)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)

    @pytest.fixture
    def agent(self):
        agent = LlmMockAgent()
        yield agent
        agent.stop()

    @pytest.fixture
    def harness(self):
        harness = LlmMockHarness()
        yield harness
        harness.stop()

    def test_response(self, agent, harness):
        assert harness.set_answer("hello", "world")
        assert agent.chat("hello") == "world"

    def test_test_restart(self, agent):
        harness = LlmMockHarness()
        assert harness.set_answer("hello", "world")
        assert agent.chat("hello") == "world"
        harness.stop()
        harness = LlmMockHarness()
        assert harness.set_answer("hello", "earth")
        assert agent.chat("hello") == "earth"
