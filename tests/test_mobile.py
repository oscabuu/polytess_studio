# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Phone mirror (polytess.viewer.mobile_server + share dialog): token
protection, full state, live deltas over the WebSocket, per-card log,
control endpoints gated by the setting, QR rendering."""

import asyncio
import json
import os
import shutil

import pytest

from polytess.core.app_settings import AppSettings
from polytess.core.variables import GlobalScope
from polytess.graph.board import DONE
from polytess.graph.model import Graph

pytest.importorskip("aiohttp")
pytest.importorskip("qrcode")

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "examples", "viewer")


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    monkeypatch.setenv("POLYTESS_USER_DIR", str(tmp_path / "userdir"))
    AppSettings.reset(path="", use_command_server=False, viewer_celebrations="off",
                      mobile_allow_control=False)
    GlobalScope.reset()
    yield
    GlobalScope.reset()


def _board_page(tmp_path):
    from polytess.viewer.board_page import BoardPage
    folder = tmp_path / "demo"
    shutil.copytree(EXAMPLES, folder,
                    ignore=shutil.ignore_patterns("*.board.json", ".runs"))
    graph = Graph.load(str(folder / "main_process.flow.json"))
    graph.variables.set("work_folder", str(folder / "work"))
    return BoardPage(graph)


async def _client(server):
    from aiohttp.test_utils import TestClient, TestServer
    client = TestClient(TestServer(server.build_app()))
    await client.start_server()
    return client


async def test_server_token_state_events_and_log(tmp_path):
    from polytess.viewer.mobile_server import MobileServer
    page = _board_page(tmp_path)
    server = MobileServer(port=0)
    page.mirror = server
    server.set_page(page)
    client = await _client(server)
    try:
        base = f"/m/{server.token}"
        # wrong token: 404 everywhere, page included
        assert (await client.get("/m/wrong/api/board")).status == 404
        assert (await client.get("/m/wrong")).status == 404
        # page + assets carry the token base
        html = await (await client.get(base)).text()
        assert "polytess" in html and f"{base}/static/app.js" in html
        js = await (await client.get(f"{base}/static/app.js")).text()
        css = await (await client.get(f"{base}/static/style.css")).text()
        assert "[hidden] { display: none !important; }" in css   # overlays start hidden
        assert f'const BASE = "{base}"' in js
        assert (await client.get(f"{base}/static/evil.txt")).status == 404
        icon = await client.get(f"{base}/static/icon.png")
        assert icon.status == 200 and (await icon.read())[:4] == b"\x89PNG"
        assert 'rel="apple-touch-icon"' in html
        # full state
        data = await (await client.get(f"{base}/api/board")).json()
        assert data["flow"] == "Bracket Study" and len(data["cards"]) == 5
        titles = {c["title"]: c for c in data["cards"]}
        assert titles["Mesh"]["predecessors"] == ["Prepare Model"]
        assert titles["Report"]["blocked_by"] == ["Prepare Model", "Mesh", "Static Load Case"]
        assert data["control"] is False and data["summary"]["total"] == 5
        # the phone follows the Viewer's board theme (default: icon colours)
        theme = data["theme"]
        assert theme["columns"]["backlog"]["head"] == "#a692e9"
        assert theme["columns"]["active"]["head"] == "#87d8f6"
        assert theme["columns"]["done"]["head"] == "#c2f771"
        assert theme["status"]["done"] == "#c2f771" and theme["status_text"]["done"] == "#1b1b1b"

        # websocket: first message is the full state, then deltas while a card runs
        ws = await client.ws_connect(f"{base}/api/events")
        first = json.loads((await ws.receive()).data)
        assert first["type"] == "flow" and first["flow"] == "Bracket Study"
        assert server.client_count == 1
        prep = page.runner.spec.card_by_title("Prepare Model")
        page.auto_box.setChecked(False)
        page.start_card(prep.guid, mode="only")
        seen = []
        while True:
            msg = json.loads((await asyncio.wait_for(ws.receive(), 20)).data)
            seen.append(msg)
            if msg["type"] == "card" and msg["status"] == DONE:
                break
        types = {m["type"] for m in seen}
        assert {"card", "progress", "log"} <= types
        done = seen[-1]
        assert done["guid"] == prep.guid and done["duration"] > 0
        assert done["summary"]["counts"]["done"] == 1
        assert done["blocked"][page.runner.spec.card_by_title("Mesh").guid] == []
        assert any(m["type"] == "log" and "Preparing model" in m["text"] for m in seen)
        # per-card log endpoint keeps the lines
        log = await (await client.get(f"{base}/api/log/{prep.guid}")).json()
        assert any("Preparing model" in l["text"] for l in log["lines"])
        await ws.close()
        await asyncio.sleep(0.05)
        assert server.client_count == 0
        for task in list(page._tasks.values()):
            if not task.done():
                await task
    finally:
        await client.close()


async def test_control_endpoints_respect_setting_and_choice(tmp_path):
    from polytess.viewer.mobile_server import MobileServer
    page = _board_page(tmp_path)
    page.auto_box.setChecked(False)
    settings = AppSettings.instance()
    server = MobileServer(port=0, allow_control=lambda: bool(settings.get("mobile_allow_control")))
    actions = []
    server.on_remote_action = actions.append
    page.mirror = server
    server.set_page(page)
    client = await _client(server)
    try:
        base = f"/m/{server.token}"
        report = page.runner.spec.card_by_title("Report")
        # off: 403, nothing starts
        resp = await client.post(f"{base}/api/cards/{report.guid}/start", json={})
        assert resp.status == 403 and not page.is_running
        settings.set("mobile_allow_control", True)
        # unfinished predecessors without a mode -> the phone must choose
        data = await (await client.post(f"{base}/api/cards/{report.guid}/start",
                                        json={})).json()
        assert data["needs_choice"] == ["Prepare Model", "Mesh", "Static Load Case"]
        assert not page.is_running
        # "only" starts just the card (it will fail: no mesh result) — stop it
        data = await (await client.post(f"{base}/api/cards/{report.guid}/start",
                                        json={"mode": "only"})).json()
        assert data["ok"] is True and page.is_running
        assert actions == ["start Report"]
        resp = await client.post(f"{base}/api/cards/{report.guid}/stop")
        assert resp.status == 200 and actions[-1] == "stop Report"
        for task in list(page._tasks.values()):
            try:
                await task
            except asyncio.CancelledError:
                pass
        # unknown card
        data = await (await client.post(f"{base}/api/cards/nope/start", json={})).json()
        assert data["ok"] is False
        # renewing the token kills old links
        old = base
        server.renew_token()
        assert (await client.get(f"{old}/api/board")).status == 404
        assert (await client.get(f"/m/{server.token}/api/board")).status == 200
    finally:
        await client.close()


async def test_server_without_page_and_lifecycle():
    from polytess.viewer.mobile_server import MobileServer, local_addresses
    server = MobileServer(port=0)
    assert server.full_state()["flow"] is None
    client = await _client(server)
    try:
        base = f"/m/{server.token}"
        data = await (await client.get(f"{base}/api/board")).json()
        assert data["cards"] == []
        resp = await client.post(f"{base}/api/run-all")
        assert resp.status in (403, 409)
    finally:
        await client.close()
    assert local_addresses()          # never empty
    # real listener on an ephemeral port
    server = MobileServer(port=0)
    await server.start()
    assert server.running
    await server.stop()
    assert not server.running


def test_share_dialog_renders_qr_and_toggles_control(tmp_path):
    from polytess.viewer.mobile_server import MobileServer
    from polytess.viewer.share_dialog import ShareDialog, qr_pixmap
    pixmap = qr_pixmap("http://192.168.1.10:8765/m/abc")
    assert pixmap.width() > 100 and pixmap.width() == pixmap.height()
    server = MobileServer(port=8765)
    dialog = ShareDialog(server)
    assert dialog.link.text().startswith("http://") and server.token in dialog.link.text()
    assert "No phone" in dialog.status.text()
    dialog.control.setChecked(True)
    assert AppSettings.instance().get("mobile_allow_control") is True
    old = server.token
    dialog._renew()
    assert server.token != old and server.token in dialog.link.text()
    server.on_clients_changed(2)
    assert "2 phones" in dialog.status.text()
    # the link field copies the whole address, selection or not
    from PySide6.QtWidgets import QApplication
    QApplication.clipboard().setText("")
    dialog.link.copy_all()
    assert QApplication.clipboard().text() == dialog.link.text()
    assert dialog.link.selectedText() == dialog.link.text()
