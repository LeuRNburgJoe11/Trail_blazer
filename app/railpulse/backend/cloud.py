"""Bounded public hackathon demo, not a persistent multi-user production service."""
import asyncio
from collections import deque
import os
from pathlib import Path
import secrets
import tempfile
import time
from urllib.parse import urlsplit

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from .assistant_bridge import SESSION_OWNER, UPLOAD_DIRECTORY

COOKIE = "__Host-railpulse"
MAX_UPLOAD = 24 * 1024 * 1024


class DemoBoundary:
    """Same-origin session binding, bounded buffering/rate/parallelism and cleanup.

    Cookies identify anonymous browsers, NOT verified people. Stored snapshots
    remain private to that browser and expire on restart or after one hour.
    Limits are per process; run one worker and initially one Cloud Run instance.
    """
    def __init__(self, app, origin, max_requests=60, per_session=20):
        self.app, self.origin = app, origin.rstrip("/")
        parsed = urlsplit(self.origin)
        if self.origin and (parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username):
            raise ValueError("RAILPULSE_PUBLIC_ORIGIN must be an exact HTTPS origin")
        self.host = parsed.netloc
        self.sessions, self.requests = {}, deque()
        self.max_requests, self.per_session, self.active = max_requests, per_session, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        request = Request(scope)

        async def reject(code, message):
            await JSONResponse({"detail": message}, status_code=code, headers={"Cache-Control": "no-store"})(scope, receive, send)

        if path == "/healthz" and method == "GET":
            return await JSONResponse({"status": "ok", "configured": bool(self.origin)})(scope, receive, send)
        if not self.origin:
            return await reject(503, "Deployment is being configured. Please try again shortly.")
        if request.headers.get("host") != self.host:
            return await reject(403, "Host not permitted")
        origin = request.headers.get("origin")
        if origin not in (None, self.origin) or (method not in {"GET", "HEAD"} and origin != self.origin):
            return await reject(403, "Origin not permitted")
        if request.headers.get("sec-fetch-site") == "cross-site" and path.startswith("/api/"):
            return await reject(403, "Cross-site API access is not permitted")
        if not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        if method not in {"GET", "POST"}:
            return await reject(405, "Method not permitted")

        now = time.monotonic()
        while self.requests and self.requests[0] <= now - 60:
            self.requests.popleft()
        if len(self.requests) >= self.max_requests or self.active >= 2:
            return await reject(429, "Demo is busy. Please wait a minute and retry.")
        for key in list(self.sessions):
            if self.sessions[key][0] < now:
                del self.sessions[key]
        sid = request.cookies.get(COOKIE)
        new_cookie = sid not in self.sessions
        if new_cookie:
            if method == "POST":
                return await reject(403, "Session expired. Refresh the page and run analysis again.")
            if len(self.sessions) >= 256:
                return await reject(503, "Demo session capacity reached. Try again later.")
            sid = secrets.token_urlsafe(32)
            self.sessions[sid] = (now + 3600, deque())
        recent = self.sessions[sid][1]
        for history in (self.requests, recent):
            while history and history[0] <= now - 60:
                history.popleft()
        if len(self.requests) >= self.max_requests or len(recent) >= self.per_session or self.active >= 2:
            return await reject(429, "Demo is busy. Please wait a minute and retry.")
        self.requests.append(now)
        recent.append(now)
        self.active += 1
        owner_token = SESSION_OWNER.set(sid)
        scope["railpulse_cloud_verified"] = True
        started = False

        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = list(message.get("headers", []))
                headers.extend([(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                                (b"referrer-policy", b"no-referrer"), (b"x-frame-options", b"DENY")])
                if new_cookie:
                    headers.append((b"set-cookie", f"{COOKIE}={sid}; Path=/; Max-Age=3600; Secure; HttpOnly; SameSite=Strict".encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            body = bytearray()
            limit = 16384 if path == "/api/assistant/ask" else MAX_UPLOAD
            if method == "POST":
                try:
                    if int(request.headers.get("content-length", "0")) > limit:
                        return await reject(413, "Upload exceeds the public demo limit (24 MiB per batch).")
                except ValueError:
                    return await reject(400, "Invalid content length")
                while True:
                    message = await asyncio.wait_for(receive(), timeout=30)
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > limit:
                        return await reject(413, "Request exceeds the public demo limit")
                    if not message.get("more_body", False):
                        break
            delivered = False

            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            with tempfile.TemporaryDirectory(prefix="railpulse-request-") as directory:
                directory_token = UPLOAD_DIRECTORY.set(directory)
                try:
                    await self.app(scope, buffered_receive, safe_send)
                finally:
                    UPLOAD_DIRECTORY.reset(directory_token)
        except Exception:
            if not started:
                await reject(500, "Analysis unavailable. Check the file format or try a smaller batch.")
            # Do not echo or log payloads, keys, filenames or provider errors.
        finally:
            SESSION_OWNER.reset(owner_token)
            self.active -= 1


def create_app():
    from .main import app as api
    # Production FastAPI errors must not expose child-process stderr or paths.
    from fastapi import HTTPException

    @api.exception_handler(HTTPException)
    async def safe_error(request, exc):
        detail = exc.detail if exc.status_code < 500 else "Model analysis unavailable. Check deployment assets or try a smaller valid file."
        return JSONResponse({"detail": detail}, status_code=exc.status_code)

    static = Path(os.environ.get("RAILPULSE_STATIC_DIR", "/workspace/public"))
    wrapper = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    # Only API routes, never source files or model directories, are exposed.
    for route in api.routes:
        if getattr(route, "path", "").startswith("/api/"):
            wrapper.router.routes.append(route)
    wrapper.exception_handlers[HTTPException] = safe_error
    wrapper.mount("/", StaticFiles(directory=static, html=True), name="dashboard")
    return DemoBoundary(wrapper, os.environ.get("RAILPULSE_PUBLIC_ORIGIN", ""))
