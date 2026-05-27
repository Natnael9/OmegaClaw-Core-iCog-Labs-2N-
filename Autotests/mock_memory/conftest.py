"""Pytest fixtures for the memory mock test suite.

Mirrors Autotests/mock/conftest.py: session-scoped LlmMockController and
CommMockServer that the agent's IPCClient and channels/mock.py connect
to once for the whole run. The controllers themselves live in
Autotests/mock/{llm,comm,rpc}.py — those modules are imported at runtime
by the agent inside the container too, so we do not duplicate them
here, only extend sys.path so this directory's conftest can reach them.
"""
import os
import sys

import pytest

_MOCK_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "mock"))
if _MOCK_DIR not in sys.path:
    sys.path.insert(0, _MOCK_DIR)

from llm import LlmMockController, LLM_MOCK_PORT  # noqa: E402
from comm import CommMockServer, COMM_MOCK_PORT  # noqa: E402


@pytest.fixture(scope="session")
def llm():
    controller = LlmMockController(("0.0.0.0", LLM_MOCK_PORT))
    try:
        yield controller
    finally:
        controller.stop(5)


@pytest.fixture(scope="session")
def comm():
    server = CommMockServer(("0.0.0.0", COMM_MOCK_PORT))
    try:
        yield server
    finally:
        server.stop(5)
