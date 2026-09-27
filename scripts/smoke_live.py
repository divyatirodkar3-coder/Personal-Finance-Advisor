"""
scripts/smoke_live.py - Boot the real app, hit it over HTTP, then stop it.

This runs the DEVELOPMENT server on a real port and checks the pages a
visitor would actually load, so we know the app works outside pytest.

Usage:  python scripts/smoke_live.py [port]
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5099
BASE = "http://127.0.0.1:{0}".format(PORT)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wait_for_port(seconds=25):
    """Poll until the server accepts connections."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", PORT)) == 0:
                return True
        time.sleep(0.4)
    return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Return the 302 itself instead of following it to the login page.

    Without this, a protected page answers 302 -> /auth/login -> 200 and
    we would wrongly conclude that anonymous users can read the data.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(path, expect):
    """Return (path, status, ok, note)."""
    url = BASE + path
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(url, timeout=10) as response:
            status = response.status
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", "replace")
    except Exception as exc:                        # noqa: BLE001
        return path, "ERR", False, type(exc).__name__

    leaked = any(word in body for word in
                 ("Traceback", "werkzeug.debug", "jinja2.exceptions"))
    ok = status == expect and not leaked
    note = "expected {0}".format(expect)
    if leaked:
        note = "LEAKED A TRACEBACK"
    elif status != expect:
        note = "expected {0}, got {1}".format(expect, status)
    return path, status, ok, note


def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["HOST"] = "127.0.0.1"
    env["FLASK_DEBUG"] = "0"          # public-facing: never the debugger

    process = subprocess.Popen(
        [sys.executable, "app.py"], cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    try:
        if not wait_for_port():
            print("FAILED: server never came up on port {0}".format(PORT))
            return 1

        # (path, expected status). Protected pages redirect to login (302).
        checks = [
            ("/health", 200),
            ("/auth/login", 200),
            ("/auth/register", 200),
            ("/", 302),
            ("/dashboard", 302),
            ("/expenses", 302),
            ("/budgets", 302),
            ("/reports", 302),
            ("/api/summary", 302),
            ("/no-such-page", 404),
        ]

        failed = 0
        print("Live smoke test on {0}".format(BASE))
        print("-" * 58)
        for path, expect in checks:
            path, status, ok, note = probe(path, expect)
            print("{0:<20} {1:<6} {2:<4} {3}".format(
                path, status, "OK" if ok else "FAIL", note))
            if not ok:
                failed += 1
        print("-" * 58)
        print("{0} checks, {1} failed".format(len(checks), failed))
        return 1 if failed else 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    sys.exit(main())
