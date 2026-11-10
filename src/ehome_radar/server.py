# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""FastAPI app: REST + WebSocket + dashboard."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse

from .config import PROFILES
from .engine import Engine

WEB = Path(__file__).parent / "web"


def create_app(engine: Engine, autostart: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        if autostart:
            engine.start()
        yield
        engine.stop()

    app = FastAPI(title="E-Home Radar", version="1.0.0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return FileResponse(WEB / "index.html")

    @app.get("/api/health")
    def health():
        ok = engine.detector.state.value != "SENSOR_LOST"
        return {"ok": ok, "time": time.time()}

    @app.get("/api/status")
    def status():
        return engine.status()

    @app.get("/api/latest")
    def latest():
        return engine.latest.to_dict() if engine.latest else {}

    @app.get("/api/history")
    def history(seconds: int = 120):
        cut = time.time() - seconds
        return [h for h in engine.history if h["ts"] >= cut]

    @app.get("/api/events")
    def events(limit: int = 100):
        return engine.storage.events(limit=min(limit, 1000))

    @app.post("/api/calibrate")
    def calibrate():
        engine.detector.recalibrate()
        return {"ok": True, "state": engine.detector.state.value}

    @app.post("/api/profile")
    def profile(name: str = Body(..., embed=True)):
        if name not in PROFILES:
            raise HTTPException(400, f"profile must be one of {sorted(PROFILES)}")
        engine.detector.set_profile(name)
        return {"ok": True, "profile": name}

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=200)

        def push(msg):
            def _put():
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                q.put_nowait(msg)
            loop.call_soon_threadsafe(_put)

        engine.subscribers.append(push)
        try:
            await sock.send_json({"type": "hello", "status": engine.status(), "history": list(engine.history)[-300:]})
            while True:
                await sock.send_json(await q.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            if push in engine.subscribers:
                engine.subscribers.remove(push)

    return app
