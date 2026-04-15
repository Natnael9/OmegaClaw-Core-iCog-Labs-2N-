import llm_mock

if __name__ == "__main__":
    client = llm_mock.LlmMockClient.singleton()
    client.connect()
    msg = client.chat("Hello Max!")
    assert msg.strip() == "Hello Dan!", f"Unexpected message from server: {msg}"
