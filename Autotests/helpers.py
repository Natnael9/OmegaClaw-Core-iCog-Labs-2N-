"""Shared test infrastructure for OmegaClaw smoke tests."""
import inspect
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

    def __enter__(self):
        frame = inspect.currentframe().f_back
        try:
            source = inspect.getsource(frame.f_code)
            self.total = source.count(".step(") + source.count(".verify_clean(")
        except OSError:
            self.total = 0
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.step("teardown: cleanup test files")
        for path in self._cleanup_dirs:
            cleanup_dir(path)
            if dexec("test", "-e", path).returncode == 0:
                print(f"       [WARN] {path} still exists after teardown", flush=True)
            else:
                print(f"       removed {path}", flush=True)
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
