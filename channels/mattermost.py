import json
import os
import threading
import time

import requests
import websocket
import auth

_running = False
_ws = None
_ws_lock = threading.Lock()
_last_message = ""
_msg_lock = threading.Lock()
_connected = False
_auth_lock = threading.Lock()
_authenticated_user_id = None

# ---- Mattermost config (dummy token ok) ----
MM_URL = "https://chat.singularitynet.io"
CHANNEL_ID = "8fjrmabjx7gupy7e5kjznpt5qh" #NOT AN ID JUST NAME: "omegaclaw"x
BOT_TOKEN = ""

def _get_bot_user_id():
    global headers
    r = requests.get(
        f"{MM_URL}/api/v4/users/me",
        headers=_headers
    )
    return r.json()["id"]

def _set_last(msg):
    global _last_message
    with _msg_lock:
        if _last_message == "":
            _last_message = msg
        else:
            _last_message = _last_message + " | " + msg

def getLastMessage():
    global _last_message
    with _msg_lock:
        tmp = _last_message
        _last_message = ""
        return tmp

def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text

def _is_auth_command(msg):
    lower = msg.strip().lower()
    return lower.startswith("auth ") or lower.startswith("/auth ")

def _is_allowed_message(user_id, msg):
    global _authenticated_user_id
    with _auth_lock:
        if not auth.is_auth_enabled():
            return "allow"
        if _authenticated_user_id is not None:
            return "allow" if user_id == _authenticated_user_id else "ignore"
        if not _is_auth_command(msg):
            return "ignore"
        candidate = _parse_auth_candidate(msg)
        if auth.verify_token(candidate):
            _authenticated_user_id = user_id
            return "auth_bound"
        return "ignore"

def _get_display_name(user_id):
    r = requests.get(
        f"{MM_URL}/api/v4/users/{user_id}",
        headers=_headers
    )
    u = r.json()

    # Mimic common Mattermost display setting
    if u.get("first_name") or u.get("last_name"):
        return f"{u.get('first_name','')} {u.get('last_name','')}".strip()

    return u["username"]

def _ws_loop():
    global _ws, _connected, BOT_USER_ID

    ws_url = MM_URL.replace("https", "wss") + "/api/v4/websocket"
    ws = websocket.WebSocket()
    ws.connect(ws_url, header=[f"Authorization: Bearer {BOT_TOKEN}"])

    BOT_USER_ID = _get_bot_user_id()
    _ws = ws
    _connected = True

    last_ping = time.time()

    while _running:
        try:
            # send ping every 25s
            if time.time() - last_ping > 25:
                ws.ping()
                last_ping = time.time()

            ws.settimeout(1)
            event = json.loads(ws.recv())

            if event.get("event") == "posted":
                post = json.loads(event["data"]["post"])
                if post["channel_id"] == CHANNEL_ID and post["user_id"] != BOT_USER_ID:
                    user_id = post["user_id"]
                    message = post.get("message", "")
                    state = _is_allowed_message(user_id, message)
                    if state == "allow":
                        name = _get_display_name(user_id)
                        _set_last(f"{name}: {message}")
                    elif state == "auth_bound":
                        name = _get_display_name(user_id)
                        send_message(f"Authentication successful for {name}.")

        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            break

    ws.close()
    _connected = False

def start_mattermost(MM_URL_, CHANNEL_ID_, BOT_TOKEN_):
    global _running, MM_URL, CHANNEL_ID, BOT_TOKEN, _headers, _connected
    MM_URL = MM_URL_
    CHANNEL_ID = CHANNEL_ID_
    BOT_TOKEN = BOT_TOKEN_
    _headers = {"Authorization": f"Bearer {BOT_TOKEN}"}
    _running = True
    _connected = False
    t = threading.Thread(target=_ws_loop, daemon=True)
    t.start()
    return t

def stop_mattermost():
    global _running
    _running = False

def send_message(text):
    text = text.replace("\\n", "\n")
    if not _connected:
        return
    requests.post(
        f"{MM_URL}/api/v4/posts",
        headers=_headers,
        json={"channel_id": CHANNEL_ID, "message": text}
    )
