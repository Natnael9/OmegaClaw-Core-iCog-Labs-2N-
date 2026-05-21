import os
import Autotests.mock.comm as comm

_client = None

def getLastMessage():
    global _client
    return _client.getLastMessage()

def start_mock():
    global _client
    server_ip = os.environ.get("TEST_SERVER_IP")
    _client = comm.CommMockClient((server_ip, comm.COMM_MOCK_PORT))

def send_message(text):
    global _client
    return _client.send_message(text)
