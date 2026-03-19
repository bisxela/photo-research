#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import sys
import time

host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
timeout = int(os.environ.get("STARTUP_WAIT_TIMEOUT", "90"))
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        socket.gethostbyname(host)
        with socket.create_connection((host, port), timeout=2):
            print(f"Postgres reachable at {host}:{port}", flush=True)
            sys.exit(0)
    except OSError as exc:
        last_error = exc
        print(f"Waiting for Postgres {host}:{port}: {exc}", flush=True)
        time.sleep(2)

print(
    f"Timed out waiting for Postgres {host}:{port}: {last_error}",
    file=sys.stderr,
    flush=True,
)
sys.exit(1)
PY

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
