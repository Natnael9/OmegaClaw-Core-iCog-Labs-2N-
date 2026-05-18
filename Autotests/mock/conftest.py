"""Pytest fixtures for the mock test suite.

The session-scoped llm fixture keeps a single LlmMockController alive
for the whole pytest run. The agent's IPCClient connects to it once
and holds the connection until the session ends, so per-test
set_answer() calls land before the corresponding HUMAN-MSG arrives,
without the reconnect race that hits the per-test controller pattern.

Answer keys are the full prompt strings, which include a unique
REQ-{run_id} tag, so answers do not collide across tests sharing the
same controller.
"""
import pytest

from llm import LlmMockController
from rpc import PORT_DEFAULT


@pytest.fixture(scope="session")
def llm():
    controller = LlmMockController(("0.0.0.0", PORT_DEFAULT))
    try:
        yield controller
    finally:
        controller.stop(5)
