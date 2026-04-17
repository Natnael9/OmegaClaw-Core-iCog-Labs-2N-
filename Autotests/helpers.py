"""Shared test infrastructure for OmegaClaw smoke tests."""
import inspect
import re
import socket
import subprocess
import time

import pytest

CHANNEL = "#metaclaw777"
CONTAINER = "omegaclaw"
IRC_SERVER = "irc.quakenet.org"
IRC_PORT = 6667
WAIT = 120
POLL = 3

HISTORY_FILE = "/PeTTa/repos/omegaclaw/memory/history.metta"
CHROMA_SQLITE = "/PeTTa/chroma_db/chroma.sqlite3"


def dexec(*args):
    cmd = ["docker", "exec", CONTAINER, *args]
    print(f"       $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True)


def dexec_root(*args):
    cmd = ["docker", "exec", "-u", "root", CONTAINER, *args]
    print(f"       $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True)


IRC_RETRIES = 3
IRC_RETRY_DELAY = 30


def _try_send(prompt):
    nick = f"Toss{int(time.time()) % 10000}"
    sock = socket.create_connection((IRC_SERVER, IRC_PORT), timeout=30)
    sock.settimeout(30)
    sock.sendall(f"NICK {nick}\r\nUSER {nick} 0 * :{nick}\r\n".encode())

    sent = False
    buf = ""
    deadline = time.time() + 60
    while time.time() < deadline and not sent:
        buf += sock.recv(4096).decode(errors="ignore")
        while "\r\n" in buf:
            line, buf = buf.split("\r\n", 1)
            if line.startswith("PING"):
                sock.sendall(f"PONG {line.split()[1]}\r\n".encode())
            if " 001 " in line:
                sock.sendall(f"JOIN {CHANNEL}\r\n".encode())
            if " 366 " in line:
                sock.sendall(f"PRIVMSG {CHANNEL} :auth 0000\r\n".encode())
                sock.sendall(f"PRIVMSG {CHANNEL} :{prompt}\r\n".encode())
                time.sleep(2)
                sock.sendall(b"QUIT :bye\r\n")
                sock.close()
                sent = True
                break
    return sent


def send_prompt(prompt):
    for attempt in range(IRC_RETRIES):
        try:
            if _try_send(prompt):
                return True
        except (ConnectionResetError, ConnectionRefusedError, socket.timeout, OSError) as e:
            print(f"       IRC attempt {attempt + 1}/{IRC_RETRIES} failed: {e}", flush=True)
        if attempt < IRC_RETRIES - 1:
            print(f"       retrying in {IRC_RETRY_DELAY}s...", flush=True)
            time.sleep(IRC_RETRY_DELAY)
    return False


def wait_for_file(path, after_ts, timeout=WAIT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = dexec("stat", "-c", "%Y", path)
        if res.returncode == 0:
            mtime = int(res.stdout.strip())
            if mtime >= after_ts:
                return mtime
        time.sleep(POLL)
    return None


def cleanup_dir(path):
    subprocess.run(
        ["docker", "exec", "-u", "root", CONTAINER, "rm", "-rf", path],
        capture_output=True, text=True,
    )


def history_cleanup_by_markers(markers):
    """Remove HUMAN_MESSAGE blocks from history.metta whose text contains any
    of the given markers. Idempotent. Runs python3 inside the container as root.
    """
    if not markers:
        return 0
    py = (
        "import sys\n"
        f"path = {HISTORY_FILE!r}\n"
        f"markers = {list(markers)!r}\n"
        "try:\n"
        "    with open(path) as f: content = f.read()\n"
        "except FileNotFoundError:\n"
        "    print('0'); sys.exit(0)\n"
        "out = []\n"
        "i = 0\n"
        "n = len(content)\n"
        "removed = 0\n"
        "markers_lc = [m.lower() for m in markers]\n"
        "while i < n:\n"
        "    hm = content.find('HUMAN_MESSAGE:', i)\n"
        "    if hm == -1:\n"
        "        out.append(content[i:]); break\n"
        "    out.append(content[i:hm])\n"
        "    nxt = content.find('HUMAN_MESSAGE:', hm + 14)\n"
        "    end = nxt if nxt != -1 else n\n"
        "    block = content[hm:end]\n"
        "    block_lc = block.lower()\n"
        "    if any(m in block_lc for m in markers_lc):\n"
        "        removed += 1\n"
        "    else:\n"
        "        out.append(block)\n"
        "    i = end\n"
        "new_content = ''.join(out)\n"
        "if new_content != content:\n"
        "    with open(path, 'w') as f: f.write(new_content)\n"
        "print(removed)\n"
    )
    res = dexec_root("python3", "-c", py)
    try:
        return int(res.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0


def chromadb_cleanup_by_markers(markers):
    """Delete chromadb entries whose document contains any of the given markers.
    Uses ChromaDB Python API inside the container. Returns total deleted count.
    """
    if not markers:
        return 0
    py = (
        "import chromadb\n"
        "client = chromadb.PersistentClient(path='/PeTTa/chroma_db')\n"
        f"markers = {list(markers)!r}\n"
        "markers_lc = [m.lower() for m in markers]\n"
        "total = 0\n"
        "for coll in client.list_collections():\n"
        "    c = client.get_collection(coll.name)\n"
        "    data = c.get()\n"
        "    ids = data.get('ids') or []\n"
        "    docs = data.get('documents') or []\n"
        "    to_del = [ids[i] for i, d in enumerate(docs)\n"
        "              if d and any(m in d.lower() for m in markers_lc)]\n"
        "    if to_del:\n"
        "        c.delete(ids=to_del)\n"
        "        total += len(to_del)\n"
        "print(total)\n"
    )
    res = dexec("python3", "-c", py)
    try:
        return int(res.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0


def read_history():
    return dexec("cat", HISTORY_FILE).stdout


def get_mtime(path):
    res = dexec("stat", "-c", "%Y", path)
    if res.returncode != 0:
        return None
    try:
        return int(res.stdout.strip())
    except ValueError:
        return None


def get_size(path):
    res = dexec("stat", "-c", "%s", path)
    if res.returncode != 0:
        return None
    try:
        return int(res.stdout.strip())
    except ValueError:
        return None


def _history_block_for_run_id(content, run_id):
    marker = f"run-id {run_id}"
    idx = content.find(marker)
    if idx == -1:
        return None
    line_start = content.rfind("HUMAN_MESSAGE:", 0, idx)
    if line_start == -1:
        line_start = idx
    return content[line_start:]


def wait_for_history_keyword(run_id, keywords, timeout=WAIT, require_all=False):
    """Wait until at least one keyword (case-insensitive) appears in history
    after the HUMAN_MESSAGE line containing the given run_id.
    If require_all=True, waits until ALL keywords are present.
    Returns list of matched keywords, or None on timeout.
    """
    deadline = time.time() + timeout
    kws_lower = [k.lower() for k in keywords]
    while time.time() < deadline:
        block = _history_block_for_run_id(read_history(), run_id)
        if block:
            blk_lower = block.lower()
            matched = [k for k, kl in zip(keywords, kws_lower) if kl in blk_lower]
            if require_all and len(matched) == len(keywords):
                return matched
            if not require_all and matched:
                return matched
        time.sleep(POLL)
    return None


def wait_for_history_block(run_id, timeout=WAIT):
    """Wait until any response block appears in history after the run_id marker.
    Returns the block text, or None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        block = _history_block_for_run_id(read_history(), run_id)
        if block:
            next_human = block.find("HUMAN_MESSAGE:", 20)
            if next_human != -1:
                return block[:next_human]
            time.sleep(POLL)
            block2 = _history_block_for_run_id(read_history(), run_id)
            if block2 and len(block2) > len(block) * 0.9:
                return block2
            return block
        time.sleep(POLL)
    return None


def wait_for_file_mtime_change(path, initial_mtime, timeout=WAIT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = get_mtime(path)
        if m is not None and (initial_mtime is None or m > initial_mtime):
            return m
        time.sleep(POLL)
    return None


def _response_window(content, run_id):
    """Return the slice of history from our HUMAN_MESSAGE block up to the next
    HUMAN_MESSAGE (or EOF). This is where the agent's skill invocations for
    our run_id live.
    """
    marker = f"run-id {run_id}"
    idx = content.find(marker)
    if idx == -1:
        return None
    line_start = content.rfind("HUMAN_MESSAGE:", 0, idx)
    if line_start == -1:
        line_start = idx
    # find next HUMAN_MESSAGE after our prompt line
    next_hm = content.find("HUMAN_MESSAGE:", idx + len(marker))
    if next_hm == -1:
        return content[line_start:]
    return content[line_start:next_hm]


_SKILL_ARG_RE = {}


def _skill_regex(skill):
    if skill not in _SKILL_ARG_RE:
        _SKILL_ARG_RE[skill] = re.compile(
            r"\(" + re.escape(skill) + r"\s+\"((?:[^\"\\]|\\.)*)\"",
            re.DOTALL,
        )
    return _SKILL_ARG_RE[skill]


def find_skill_calls(run_id, skill_name):
    """Return list of argument strings for every (<skill_name> "...") call
    the agent made in its response window for this run_id. Empty list if none.
    None if no response block exists yet.
    """
    window = _response_window(read_history(), run_id)
    if window is None:
        return None
    return _skill_regex(skill_name).findall(window)


def wait_for_skill_call(run_id, skill_name, timeout=WAIT, arg_substr=None):
    """Wait until the agent invokes (<skill_name> "...") in its response to run_id.
    If arg_substr is given, require that substring (case-insensitive) in the
    skill argument. Returns the matching argument on success, None on timeout.
    """
    deadline = time.time() + timeout
    needle = arg_substr.lower() if arg_substr else None
    while time.time() < deadline:
        calls = find_skill_calls(run_id, skill_name)
        if calls:
            if needle is None:
                return calls[0]
            for a in calls:
                if needle in a.lower():
                    return a
        time.sleep(POLL)
    return None


def wait_for_any_skill_call(run_id, skill_names, timeout=WAIT, arg_substr=None):
    """Wait for a call to any of the given skills. Returns (skill_name, arg) tuple
    on success, (None, None) on timeout.
    """
    deadline = time.time() + timeout
    needle = arg_substr.lower() if arg_substr else None
    while time.time() < deadline:
        for skill in skill_names:
            calls = find_skill_calls(run_id, skill)
            if calls:
                if needle is None:
                    return skill, calls[0]
                for a in calls:
                    if needle in a.lower():
                        return skill, a
        time.sleep(POLL)
    return None, None


def make_prompt(run_id, task):
    return (
        f"CI smoke test run-id {run_id}, never executed before - "
        "this is a NEW request, do not consult memory. "
        f"{task} "
        "Confirm with one short line."
    )


class Checker:
    def __init__(self, name, cleanup_dirs=None):
        self.name = name
        self.total = 0
        self.passed = 0
        self.run_id = int(time.time())
        self._cleanup_dirs = cleanup_dirs or []
        self._cleanup_markers = [f"run-id {self.run_id}", str(self.run_id)]

    def add_cleanup_marker(self, marker):
        """Register an extra string to match in chromadb docs / history blocks
        during teardown. The default marker 'run-id {run_id}' is always added.
        """
        if marker and marker not in self._cleanup_markers:
            self._cleanup_markers.append(marker)

    def __enter__(self):
        frame = inspect.currentframe().f_back
        try:
            source = inspect.getsource(frame.f_code)
            self.total = source.count(".step(") + source.count(".verify_clean(")
        except OSError:
            self.total = 0
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.step("teardown: cleanup test artifacts")
        for path in self._cleanup_dirs:
            cleanup_dir(path)
            if dexec("test", "-e", path).returncode == 0:
                print(f"       [WARN] {path} still exists after teardown", flush=True)
            else:
                print(f"       removed {path}", flush=True)
        h_removed = history_cleanup_by_markers(self._cleanup_markers)
        print(f"       history: {h_removed} blocks removed "
              f"(markers={self._cleanup_markers})", flush=True)
        c_removed = chromadb_cleanup_by_markers(self._cleanup_markers)
        print(f"       chromadb: {c_removed} vectors removed", flush=True)
        return False

    def verify_clean(self):
        self.step("verify target dirs are clean")
        for path in self._cleanup_dirs:
            if dexec("test", "-e", path).returncode == 0:
                print(f"       {path} exists, cleaning up leftover", flush=True)
                cleanup_dir(path)
                if dexec("test", "-e", path).returncode == 0:
                    self.fail("verify clean", f"cannot remove leftover {path}")
        self.ok("verify clean")

    def step(self, name):
        print(f"\n>> {name}", flush=True)

    def ok(self, name, detail=""):
        self.passed += 1
        extra = f" -- {detail}" if detail else ""
        print(f"[ OK ] {name}{extra}", flush=True)

    def fail(self, name, detail):
        print(f"[FAIL] {name} -- {detail}", flush=True)
        print(f"\n[FAIL] {self.passed}/{self.total} checks passed\n", flush=True)
        pytest.fail(f"{name}: {detail}", pytrace=False)

    def done(self):
        print(f"\n[PASS] {self.passed}/{self.total} checks passed\n", flush=True)
