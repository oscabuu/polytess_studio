# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Phone mirror of the Viewer board (PLAN_MOBILE.md).

A small aiohttp server inside the Viewer's asyncio loop serves the
mobile web page and a JSON/WebSocket API, all behind a per-session
token in the URL (the QR code). Everything is read-only unless
*allow_control* is on; then the phone may start/stop cards.

    GET  /m/<token>                      mobile page
    GET  /m/<token>/static/<file>        app.js, style.css
    GET  /m/<token>/api/board            full state (flow, cards, summary)
    GET  /m/<token>/api/events           WebSocket: deltas
    GET  /m/<token>/api/log/<guid>       last log lines of a card
    POST /m/<token>/api/cards/<guid>/start   {"mode": "in_order"|"only"|null}
    POST /m/<token>/api/cards/<guid>/stop
    POST /m/<token>/api/run-all

Requests without the right token get 404 — nothing reveals the server.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import time
from collections import deque
from typing import Callable

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets", "mobile")
MAX_LOG_LINES = 200


def available() -> bool:
    try:
        import aiohttp  # noqa: F401
        import qrcode   # noqa: F401
    except ImportError:
        return False
    return True


def local_addresses() -> list[str]:
    """IPv4 addresses a phone could use, most likely first."""
    found: list[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in found and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    return found or ["127.0.0.1"]


class MobileServer:
    """Owns the token, the clients and the current board page."""

    def __init__(self, port: int = 8765, allow_control: Callable[[], bool] | None = None):
        self.port = port
        self.token = secrets.token_urlsafe(16)
        self.allow_control = allow_control or (lambda: False)
        self.page = None                     # BoardPage or None
        self._clients: set = set()
        self._logs: dict[str, deque] = {}
        self._progress: dict[str, dict] = {}
        self._runner = None
        self._site = None
        self.on_clients_changed: Callable[[int], None] | None = None
        self.on_remote_action: Callable[[str], None] | None = None
        self.started_at = 0.0

    # ---- lifecycle --------------------------------------------------------------- #

    def build_app(self):
        from aiohttp import web
        app = web.Application()
        t = "/m/{token}"
        app.router.add_get(t, self._page)
        app.router.add_get(t + "/", self._page)
        app.router.add_get(t + "/static/{name}", self._static)
        app.router.add_get(t + "/api/board", self._board)
        app.router.add_get(t + "/api/events", self._events)
        app.router.add_get(t + "/api/log/{guid}", self._log)
        app.router.add_post(t + "/api/cards/{guid}/start", self._start)
        app.router.add_post(t + "/api/cards/{guid}/stop", self._stop)
        app.router.add_post(t + "/api/run-all", self._run_all)
        return app

    async def start(self) -> None:
        from aiohttp import web
        if self._site is not None:
            return
        self._runner = web.AppRunner(self.build_app(), access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()
        self.started_at = time.time()

    async def stop(self) -> None:
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = self._site = None

    @property
    def running(self) -> bool:
        return self._site is not None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def url(self, host: str) -> str:
        return f"http://{host}:{self.port}/m/{self.token}"

    def renew_token(self) -> None:
        """Invalidate every old QR code / link."""
        self.token = secrets.token_urlsafe(16)
        for ws in list(self._clients):
            asyncio.ensure_future(ws.close())
        self._clients.clear()

    # ---- board binding ------------------------------------------------------------- #

    def set_page(self, page) -> None:
        self.page = page
        self._logs.clear()
        self._progress.clear()
        self.broadcast({"type": "flow", **self.full_state()})

    @staticmethod
    def theme_payload() -> dict:
        """The Viewer's board theme for the phone page (colours only)."""
        from polytess.viewer.style import (STATUS_FILL, board_theme,
                                           status_colour, text_on)
        theme = board_theme()
        return {
            "columns": {col: {"head": theme["column_head"][col],
                              "body": theme["column_body"][col],
                              "text": text_on(theme["column_head"][col])}
                        for col in ("backlog", "active", "done")},
            "status": {st: status_colour(theme, st) for st in STATUS_FILL},
            "status_text": {st: text_on(status_colour(theme, st)) for st in STATUS_FILL},
            "card_fill": dict(theme.get("card_fill", {})),
        }

    def notify_theme(self) -> None:
        self.broadcast({"type": "theme", "theme": self.theme_payload()})

    def full_state(self) -> dict:
        page = self.page
        if page is None:
            return {"flow": None, "cards": [], "summary": None,
                    "control": bool(self.allow_control()),
                    "theme": self.theme_payload()}
        runner = page.runner
        cards = []
        for card in runner.spec.cards:
            cs = runner.state.card(card.guid)
            progress = self._progress.get(card.guid, {})
            cards.append({
                "guid": card.guid, "title": card.title,
                "description": card.description, "status": cs.status,
                "level": card.level,
                "predecessors": [runner.spec.card(p).title for p in card.predecessors],
                "blocked_by": [c.title for c in runner.unfinished_predecessors(card.guid)],
                "duration": cs.duration, "error": cs.error,
                "started": cs.started, "finished": cs.finished,
                "progress": progress.get("fraction", 0.0),
                "step": progress.get("step", ""),
            })
        summary = runner.state.summary(runner.spec)
        return {"flow": page.graph.name,
                "file": os.path.basename(page.graph.path or ""),
                "cards": cards, "summary": summary,
                "problems": list(runner.spec.problems),
                "control": bool(self.allow_control()),
                "theme": self.theme_payload(),
                "server_time": time.time()}

    # ---- notifications from the page --------------------------------------------- #

    def notify_change(self, guid: str, status: str) -> None:
        if self.page is None:
            return
        cs = self.page.runner.state.card(guid)
        if status != "active":
            self._progress.pop(guid, None)
        self.broadcast({"type": "card", "guid": guid, "status": status,
                        "duration": cs.duration, "error": cs.error,
                        "blocked": {c.guid: [b.title for b in
                                             self.page.runner.unfinished_predecessors(c.guid)]
                                    for c in self.page.runner.spec.cards},
                        "summary": self.page.runner.state.summary(self.page.runner.spec)})

    def notify_progress(self, guid: str, fraction: float, step: str) -> None:
        self._progress[guid] = {"fraction": fraction, "step": step}
        self.broadcast({"type": "progress", "guid": guid,
                        "progress": fraction, "step": step})

    def notify_log(self, guid: str, level: str, text: str) -> None:
        line = {"t": time.strftime("%H:%M:%S"), "level": level, "text": text}
        self._logs.setdefault(guid, deque(maxlen=MAX_LOG_LINES)).append(line)
        self.broadcast({"type": "log", "guid": guid, **line})

    def notify_control(self) -> None:
        self.broadcast({"type": "control", "control": bool(self.allow_control())})

    def broadcast(self, message: dict) -> None:
        if not self._clients:
            return
        data = json.dumps(message, default=str)
        for ws in list(self._clients):
            asyncio.ensure_future(self._send(ws, data))

    async def _send(self, ws, data: str) -> None:
        try:
            await ws.send_str(data)
        except Exception:
            self._clients.discard(ws)
            self._clients_changed()

    def _clients_changed(self) -> None:
        if self.on_clients_changed:
            self.on_clients_changed(len(self._clients))

    # ---- handlers ----------------------------------------------------------------------- #

    def _check(self, request) -> None:
        from aiohttp import web
        if not secrets.compare_digest(request.match_info.get("token", ""), self.token):
            raise web.HTTPNotFound()

    async def _page(self, request):
        from aiohttp import web
        self._check(request)
        path = os.path.join(ASSETS, "index.html")
        with open(path, encoding="utf-8") as fh:
            html = fh.read().replace("__BASE__", f"/m/{self.token}")
        return web.Response(text=html, content_type="text/html",
                            headers={"Cache-Control": "no-store"})

    _icon_png: bytes | None = None

    async def _static(self, request):
        from aiohttp import web
        self._check(request)
        name = request.match_info["name"]
        if name == "icon.png":                 # favicon / home-screen icon
            if MobileServer._icon_png is None:
                try:
                    from polytess.gui.app_icon import icon_png_bytes
                    MobileServer._icon_png = icon_png_bytes(180, "viewer")
                except Exception:
                    raise web.HTTPNotFound()
            return web.Response(body=MobileServer._icon_png, content_type="image/png",
                                headers={"Cache-Control": "max-age=86400"})
        if name not in ("app.js", "style.css", "manifest.json"):
            raise web.HTTPNotFound()
        path = os.path.join(ASSETS, name)
        types = {"app.js": "application/javascript", "style.css": "text/css",
                 "manifest.json": "application/manifest+json"}
        with open(path, encoding="utf-8") as fh:
            body = fh.read().replace("__BASE__", f"/m/{self.token}")
        return web.Response(text=body, content_type=types[name],
                            headers={"Cache-Control": "no-store"})

    async def _board(self, request):
        from aiohttp import web
        self._check(request)
        return web.json_response(self.full_state(), dumps=lambda o: json.dumps(o, default=str))

    async def _log(self, request):
        from aiohttp import web
        self._check(request)
        guid = request.match_info["guid"]
        return web.json_response({"guid": guid,
                                  "lines": list(self._logs.get(guid, ()))})

    async def _events(self, request):
        from aiohttp import web
        self._check(request)
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        self._clients.add(ws)
        self._clients_changed()
        try:
            await ws.send_str(json.dumps({"type": "flow", **self.full_state()},
                                         default=str))
            async for _message in ws:
                pass                                    # phone never sends
        finally:
            self._clients.discard(ws)
            self._clients_changed()
        return ws

    def _control_or_403(self):
        from aiohttp import web
        if self.page is None:
            raise web.HTTPConflict(text="no board open")
        if not self.allow_control():
            raise web.HTTPForbidden(text="control from phone is off")

    async def _start(self, request):
        from aiohttp import web
        self._check(request)
        self._control_or_403()
        guid = request.match_info["guid"]
        try:
            body = await request.json()
        except Exception:
            body = {}
        mode = body.get("mode") if isinstance(body, dict) else None
        result = self.page.remote_start(guid, mode)
        if self.on_remote_action and result.get("ok"):
            self.on_remote_action(f"start {self.page.runner.spec.card(guid).title}")
        return web.json_response(result)

    async def _stop(self, request):
        from aiohttp import web
        self._check(request)
        self._control_or_403()
        guid = request.match_info["guid"]
        self.page.stop_card(guid)
        if self.on_remote_action:
            self.on_remote_action(f"stop {self.page.runner.spec.card(guid).title}")
        return web.json_response({"ok": True})

    async def _run_all(self, request):
        from aiohttp import web
        self._check(request)
        self._control_or_403()
        self.page.run_all()
        if self.on_remote_action:
            self.on_remote_action("run all")
        return web.json_response({"ok": True})
