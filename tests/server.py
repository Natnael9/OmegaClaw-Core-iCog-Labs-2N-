import llm_mock
import time

if __name__ == "__main__":
    server = llm_mock.LlmMockServer.singleton()
    msg = server.read_line()
    assert msg == "Hello Max!", f"Unexpected message from client: {msg}"
    time.sleep(10)
    server.send("Hello Dan!")
