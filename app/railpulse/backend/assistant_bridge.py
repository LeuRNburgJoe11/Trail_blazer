"""Isolate the canonical assistant from the dashboard's duplicate railpulse package.

Opaque, expiring snapshot capabilities keep request-supplied telemetry out of the
evidence trust boundary. Local-demo storage only; never expose without auth/TLS.
"""
from collections import OrderedDict
from copy import deepcopy
from contextvars import ContextVar
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from threading import Lock
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[3]
SCOPE = {"general", "door", "acv", "rail", "shm"}
SNAPSHOTS = OrderedDict()
LOCK = Lock()
TTL = 3600
MAX_BYTES = 24_000_000
router = APIRouter()
SESSION_OWNER = ContextVar("railpulse_session_owner", default=None)
UPLOAD_DIRECTORY = ContextVar("railpulse_upload_directory", default=None)


def local_request(request):
    if request.scope.get("railpulse_cloud_verified"):
        return True
    return request.url.hostname in {"localhost", "127.0.0.1"} and request.headers.get("origin") in {
        None, "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"}


def remember(domain, payload):
    snapshot = {k: deepcopy(v) for k, v in payload.items() if k != "submission_csv"}
    size = len(json.dumps(snapshot, allow_nan=False).encode())
    if size > MAX_BYTES:
        return {**payload, "assistant_warning": "Result exceeds chat context capacity; documentation chat remains available."}
    token = secrets.token_urlsafe(32)
    with LOCK:
        now = time.monotonic()
        for key in list(SNAPSHOTS):
            if SNAPSHOTS[key][0] < now:
                del SNAPSHOTS[key]
        while SNAPSHOTS and (len(SNAPSHOTS) >= 16 or sum(v[3] for v in SNAPSHOTS.values()) + size > MAX_BYTES):
            SNAPSHOTS.popitem(last=False)
        SNAPSHOTS[token] = (now + TTL, domain, snapshot, size, SESSION_OWNER.get())
    return {**payload, "assistant_snapshot": token}


def snapshot_for(token, domain):
    if token is None:
        return None
    if not isinstance(token, str) or len(token) > 100:
        raise ValueError("Invalid snapshot")
    with LOCK:
        saved = SNAPSHOTS.get(token)
        if not saved or saved[0] < time.monotonic() or saved[1] != domain or saved[4] != SESSION_OWNER.get():
            raise ValueError("Expired or mismatched snapshot. Run the analysis again.")
        return deepcopy(saved[2])


def invoke(payload):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    # JSON travels through stdin, never process arguments or temporary key files.
    result = subprocess.run([sys.executable, "-m", "railpulse.assistant.dashboard"],
                            input=json.dumps(payload, allow_nan=False), text=True,
                            capture_output=True, cwd=ROOT, env=environment, timeout=105)
    if result.returncode:
        raise RuntimeError("Assistant unavailable")  # Never echo stderr / keys.
    return json.loads(result.stdout)


@router.get("/api/assistant/context")
def context(request: Request):
    if not local_request(request):
        return JSONResponse({"detail": "Origin not permitted"}, status_code=403)
    try:
        return invoke({"action": "context"})
    except Exception:
        return JSONResponse({"detail": "Assistant unavailable. Use the repository virtual environment for the dashboard backend."}, status_code=503)


@router.post("/api/assistant/ask")
async def ask(request: Request):
    if not local_request(request):
        return JSONResponse({"detail": "Origin not permitted"}, status_code=403)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 16384:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        allowed = {"question", "subsystem", "snapshot", "file_id", "row_index", "car_id", "previous_question",
                   "provider", "model", "api_key", "consent", "engineer_instructions", "engineer_context", "detail", "audience"}
        if set(value) - allowed or value.get("subsystem") not in SCOPE:
            raise ValueError()
        if not isinstance(value.get("question"), str) or not 1 <= len(value["question"].strip()) <= 2000:
            raise ValueError()
        snapshot = snapshot_for(value.pop("snapshot", None), value["subsystem"])
        value["dashboard_snapshot"] = snapshot
    except (ValueError, TypeError):
        return JSONResponse({"detail": "Invalid or expired evidence scope. Run analysis again if the snapshot expired."}, status_code=400)
    try:
        result = await run_in_threadpool(invoke, value)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except Exception:
        return JSONResponse({"detail": "Assistant unavailable; check the backend environment or try local evidence."}, status_code=503)
