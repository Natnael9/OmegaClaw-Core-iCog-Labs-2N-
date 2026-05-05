import pytest

from llm import *
from rpc import HOST_DEFAULT

TEST_ADDRESS = (HOST_DEFAULT, 9767)

class TestLlmMock:

    def setup_class(cls):
        import logging
        import threading

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
    def agent(self):
        agent = LlmMockAgent(TEST_ADDRESS)
        yield agent
        agent.stop(5)

    @pytest.fixture
    def harness(self):
        harness = LlmMockController(TEST_ADDRESS)
        yield harness
        harness.stop(5)

    def test_response(self, agent, harness):
        assert harness.set_answer("hello", "world")
        assert agent.chat("hello") == "world"

    def test_test_restart(self, agent):
        harness = LlmMockController(TEST_ADDRESS)
        assert harness.set_answer("hello", "world")
        assert agent.chat("hello") == "world"
        harness.stop(5)
        harness = LlmMockController(TEST_ADDRESS)
        assert harness.set_answer("hello", "earth")
        assert agent.chat("hello") == "earth"
        harness.stop(5)
