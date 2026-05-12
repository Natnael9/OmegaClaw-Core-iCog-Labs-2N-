import json
import os
import threading
import time
import urllib.parse
import urllib.request

_running = False
_last_message = ""
_msg_lock = threading.Lock()
_state_lock = threading.Lock()

_bot_token = ""
_channel_id = ""
_poll_interval = 20
_last_ts = None
_bot_user_id = ""
_connected = False
_user_cache = {}

_auth_secret = ""
_authenticated_user_id = None


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


def _set_auth_secret(secret=None):
    global _auth_secret, _authenticated_user_id
    if secret is None:
        secret = os.environ.get("OMEGACLAW_AUTH_SECRET", "")
    with _state_lock:
        _auth_secret = (secret or "").strip()
        _authenticated_user_id = None


def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


def _is_allowed_message(user_id, msg):
    global _authenticated_user_id
    candidate = _parse_auth_candidate(msg)
    with _state_lock:
        if not _auth_secret:
            return "allow"
        if candidate == _auth_secret:
            if _authenticated_user_id is None:
                _authenticated_user_id = user_id
                return "auth_bound"
            return "ignore"
        if _authenticated_user_id is None:
            return "ignore"
        return "allow" if user_id == _authenticated_user_id else "ignore"


def _api_call(method, params=None, timeout=30):
    if not _bot_token:
        raise RuntimeError("Slack adapter not initialized")

    params = params or {}
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=body,
        headers={
            "Authorization": f"Bearer {_bot_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))

    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", f"{method} failed"))

    return payload


def _get_display_name(user_id):
    with _state_lock:
        cached = _user_cache.get(user_id)
    if cached:
        return cached

    name = user_id
    try:
        payload = _api_call("users.info", {"user": user_id}, timeout=15)
        user = payload.get("user") or {}
        profile = user.get("profile") or {}

        display_name = str(profile.get("display_name", "")).strip()
        real_name = str(profile.get("real_name", "")).strip()
        username = str(user.get("name", "")).strip()

        if display_name:
            name = display_name
        elif real_name:
            name = real_name
        elif username:
            name = username
    except Exception as exc:
        print(f"[SLACK] Could not resolve user {user_id}: {exc}")

    with _state_lock:
        _user_cache[user_id] = name
    return name


def _initialize_identity():
    global _bot_user_id
    payload = _api_call("auth.test", timeout=15)
    bot_user_id = str(payload.get("user_id", "")).strip()
    with _state_lock:
        _bot_user_id = bot_user_id


def _validate_channel():
    payload = _api_call("conversations.info", {"channel": _channel_id}, timeout=15)
    channel = payload.get("channel") or {}
    channel_name = str(channel.get("name", "")).strip()
    if channel_name:
        print(f"[SLACK] Channel ready: #{channel_name}")
    else:
        print(f"[SLACK] Channel ready: {_channel_id}")


def _initialize_cursor():
    global _last_ts
    try:
        payload = _api_call(
            "conversations.history",
            {"channel": _channel_id, "limit": 1},
            timeout=15,
        )
        messages = payload.get("messages") or []
        if messages:
            ts = str(messages[0].get("ts", "")).strip()
            if ts:
                with _state_lock:
                    _last_ts = ts
    except Exception as exc:
        print(f"[SLACK] Could not initialize cursor: {exc}")


def _poll_loop():
    global _connected, _last_ts
    print("[SLACK] Polling started")

    while _running:
        try:
            params = {"channel": _channel_id, "limit": 15}
            with _state_lock:
                if _last_ts:
                    params["oldest"] = _last_ts
                    params["inclusive"] = "false"

            payload = _api_call("conversations.history", params=params, timeout=30)
            _connected = True

            messages = payload.get("messages") or []
            if messages:
                ordered = sorted(messages, key=lambda m: float(m.get("ts", 0.0)))
                max_ts = None
                for message in ordered:
                    ts = str(message.get("ts", "")).strip()
                    if ts:
                        max_ts = ts

                    # Ignore bot/system messages and process regular user text.
                    if message.get("subtype"):
                        continue

                    text = str(message.get("text", "")).strip()
                    user_id = str(message.get("user", "")).strip()
                    if not text or not user_id:
                        continue

                    with _state_lock:
                        bot_user_id = _bot_user_id
                    if bot_user_id and user_id == bot_user_id:
                        continue

                    state = _is_allowed_message(user_id, text)
                    display_name = _get_display_name(user_id)
                    if state == "allow":
                        _set_last(f"{display_name}: {text}")
                    elif state == "auth_bound":
                        send_message(f"Authentication successful for {display_name}.")

                if max_ts:
                    with _state_lock:
                        _last_ts = max_ts
        except Exception as exc:
            _connected = False
            print(f"[SLACK] Poll error: {exc}")

        time.sleep(max(1, int(_poll_interval)))

    _connected = False
    print("[SLACK] Polling stopped")


def start_slack(bot_token, channel_id, poll_interval=20, auth_secret=None):
    global _running, _bot_token, _channel_id, _poll_interval, _last_ts, _connected

    _bot_token = str(bot_token).strip()
    if not _bot_token:
        raise ValueError("SL_BOT_TOKEN is required")

    _channel_id = str(channel_id).strip()
    if not _channel_id:
        raise ValueError("SL_CHANNEL_ID is required")

    try:
        _poll_interval = max(1, int(poll_interval))
    except Exception:
        _poll_interval = 20

    with _state_lock:
        _user_cache.clear()
    _last_ts = None
    _connected = False
    _set_auth_secret(auth_secret)
    _initialize_identity()
    _validate_channel()
    _initialize_cursor()

    _running = True
    print(f"[SLACK] Starting adapter for channel: {_channel_id}")
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    return t


def stop_slack():
    global _running
    _running = False


def send_message(text):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return
    if not _connected or not _channel_id:
        return

    max_len = 3900
    for i in range(0, len(text), max_len):
        chunk = text[i:i + max_len]
        if not chunk:
            continue
        try:
            _api_call("chat.postMessage", {"channel": _channel_id, "text": chunk}, timeout=15)
        except Exception as exc:
            print(f"[SLACK] Send failed: {exc}")
            return
