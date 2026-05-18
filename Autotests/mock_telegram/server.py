"""Mock Telegram Bot API server for OmegaClaw autotests.

Emulates the two endpoints `channels/telegram.py` actually calls:

- `GET  /bot<token>/getUpdates?offset=N&timeout=T` — long-poll inbound queue
- `POST /bot<token>/sendMessage` (chat_id, text)   — outbound captured here

Test-side API (Python only, not exposed over HTTP):

- `inject_user_message(text, user_id=999, chat_id=999, username="qatestuser")`
- `pop_agent_reply(timeout=30)` — block until the agent sends a message, return its text
- `clear()` — drain both queues between tests

The server binds 0.0.0.0:9766 by default so that a Docker container on the
default bridge network can reach it through the host gateway 172.17.0.1.

The agent's Telegram adapter is pointed at this server via env
`TG_API_BASE=http://172.17.0.1:9766` plus a dummy `TG_BOT_TOKEN=DUMMYTESTTOKEN`.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import threading
import time
import urllib.parse


HOST_DEFAULT = "0.0.0.0"
PORT_DEFAULT = 9766


class _Handler(BaseHTTPRequestHandler):
    server_version = "MockTelegramBotAPI/0.1"

    def log_message(self, format, *args):
        # Reduce per-request noise; uncomment for HTTP tracing.
        # print(f"[MockTG HTTP] {format % args}", flush=True)
        pass

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, result):
        self._send_json(200, {"ok": True, "result": result})

    def _bad(self, code, description):
        self._send_json(code, {"ok": False, "error_code": code, "description": description})

    # GET handler ---------------------------------------------------------
    def do_GET(self):
        srv = self.server  # type: MockTelegramServer
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if not path.startswith("/bot"):
            return self._bad(404, "Not Found")
        try:
            _, token, method = path.split("/", 2)
        except ValueError:
            return self._bad(404, "Not Found")
        token = token[3:]  # strip 'bot' prefix
        if token != srv.expected_token:
            return self._bad(401, "Unauthorized")

        if method == "getMe":
            return self._ok({
                "id": 7777777,
                "is_bot": True,
                "first_name": "OmegaClawMock",
                "username": "omegaclaw_mock_bot",
                "can_join_groups": True,
                "can_read_all_group_messages": True,
                "supports_inline_queries": False,
            })

        if method == "getUpdates":
            try:
                offset = int((params.get("offset") or ["0"])[0])
            except ValueError:
                offset = 0
            try:
                timeout = int((params.get("timeout") or ["0"])[0])
            except ValueError:
                timeout = 0
            # Long-poll: wait up to `timeout` seconds for new updates.
            updates = srv._drain_pending_updates(min_offset=offset, timeout=timeout)
            return self._ok(updates)

        return self._bad(404, f"Unknown method: {method}")

    # POST handler --------------------------------------------------------
    def do_POST(self):
        srv = self.server  # type: MockTelegramServer
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not path.startswith("/bot"):
            return self._bad(404, "Not Found")
        try:
            _, token, method = path.split("/", 2)
        except ValueError:
            return self._bad(404, "Not Found")
        token = token[3:]
        if token != srv.expected_token:
            return self._bad(401, "Unauthorized")

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", errors="ignore") if length else ""
        # OmegaClaw uses application/x-www-form-urlencoded on POSTs.
        body = urllib.parse.parse_qs(raw, keep_blank_values=True)
        flat = {k: (v[0] if v else "") for k, v in body.items()}

        if method == "sendMessage":
            chat_id = str(flat.get("chat_id", ""))
            text = flat.get("text", "")
            ts = int(time.time())
            srv._record_outbound(chat_id, text, ts)
            return self._ok({
                "message_id": srv._next_message_id(),
                "from": {"id": 7777777, "is_bot": True, "username": "omegaclaw_mock_bot"},
                "chat": {"id": int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id,
                         "type": "private"},
                "date": ts,
                "text": text,
            })

        return self._bad(404, f"Unknown method: {method}")


class MockTelegramServer(ThreadingHTTPServer):
    """Thread-pool HTTP server with test-side queues for inbound updates and
    captured outbound messages."""

    def __init__(self, address=(HOST_DEFAULT, PORT_DEFAULT),
                 expected_token="DUMMYTESTTOKEN"):
        super().__init__(address, _Handler)
        self.expected_token = expected_token
        self._inbound_lock = threading.Lock()
        self._inbound_updates = []   # list[dict] - pending Telegram Update objects
        # Wall-clock seed so update_ids stay above any offset the agent kept from a prior session.
        self._update_seq = int(time.time())
        self._message_id = 1000
        self._inbound_event = threading.Event()
        self._outbound = queue.Queue()  # tuples (chat_id, text, ts)
        self._thread = None

    # ---- lifecycle ------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        print(f"[MockTG] listening on {self.server_address[0]}:{self.server_address[1]} "
              f"(token={self.expected_token!r})", flush=True)

    def stop(self, timeout=5):
        try:
            self.shutdown()
        except Exception:
            pass
        try:
            self.server_close()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # ---- test-side API --------------------------------------------------
    def inject_user_message(self, text, user_id=999, chat_id=999, username="qatestuser"):
        """Append an inbound user message; the agent will see it on next poll."""
        with self._inbound_lock:
            self._update_seq += 1
            update = {
                "update_id": self._update_seq,
                "message": {
                    "message_id": self._update_seq,
                    "date": int(time.time()),
                    "from": {
                        "id": int(user_id),
                        "is_bot": False,
                        "first_name": username,
                        "username": username,
                        "language_code": "en",
                    },
                    "chat": {
                        "id": int(chat_id),
                        "type": "private",
                        "first_name": username,
                        "username": username,
                    },
                    "text": str(text),
                },
            }
            self._inbound_updates.append(update)
            self._inbound_event.set()
        print(f"[MockTG] injected user msg from {username} (chat {chat_id}): {text!r}",
              flush=True)

    def pop_agent_reply(self, timeout=30):
        """Block until the agent sends a message, return (chat_id, text). Returns
        (None, None) on timeout."""
        try:
            chat_id, text, _ts = self._outbound.get(timeout=timeout)
            return chat_id, text
        except queue.Empty:
            return None, None

    def drain_agent_replies(self, max_wait=2):
        """Drain everything the agent has sent so far. Returns a list of (chat_id, text)."""
        out = []
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                chat_id, text, _ts = self._outbound.get(timeout=0.2)
                out.append((chat_id, text))
            except queue.Empty:
                break
        return out

    def clear(self):
        """Drop both queues. Use between tests if you want a clean slate."""
        with self._inbound_lock:
            self._inbound_updates.clear()
            self._inbound_event.clear()
        while True:
            try:
                self._outbound.get_nowait()
            except queue.Empty:
                break

    # ---- HTTP handler helpers (called from _Handler) --------------------
    def _drain_pending_updates(self, min_offset, timeout):
        """Block up to `timeout` seconds for updates with id >= min_offset.
        Returns the matching list (possibly empty if timeout fires).
        """
        deadline = time.time() + max(0, timeout)
        while True:
            with self._inbound_lock:
                matching = [u for u in self._inbound_updates
                            if u.get("update_id", 0) >= min_offset]
                if matching:
                    # Telegram's getUpdates contract: once the client passes a
                    # higher offset, server forgets older updates. We drop
                    # everything strictly below min_offset.
                    self._inbound_updates = matching
                    self._inbound_event.clear()
                    return list(matching)
            # No matching updates — wait for the next inject or timeout.
            remaining = deadline - time.time()
            if remaining <= 0:
                return []
            self._inbound_event.wait(timeout=min(remaining, 1.0))

    def _record_outbound(self, chat_id, text, ts):
        self._outbound.put((chat_id, text, ts))
        print(f"[MockTG] agent sendMessage chat={chat_id} text={text!r}", flush=True)

    def _next_message_id(self):
        self._message_id += 1
        return self._message_id


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Run Mock Telegram Bot API server")
    p.add_argument("--host", default=HOST_DEFAULT)
    p.add_argument("--port", default=PORT_DEFAULT, type=int)
    p.add_argument("--token", default="DUMMYTESTTOKEN")
    args = p.parse_args()
    s = MockTelegramServer((args.host, args.port), expected_token=args.token)
    s.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        s.stop()
