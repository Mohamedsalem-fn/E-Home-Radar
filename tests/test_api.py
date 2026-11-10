# -*- coding: utf-8 -*-
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect) | (c) 2026
from fastapi.testclient import TestClient

from ehome_radar.config import Config
from ehome_radar.engine import Engine
from ehome_radar.server import create_app


def make_client():
    cfg = Config()
    cfg.storage.path = ":memory:"
    cfg.alerts.desktop = False
    eng = Engine(cfg)
    return TestClient(create_app(eng, autostart=False)), eng


def test_endpoints():
    c, _ = make_client()
    assert c.get("/api/health").json()["ok"] is True
    assert c.get("/api/status").json()["state"] == "CALIBRATING"
    assert c.get("/api/events").json() == []
    assert c.post("/api/profile", json={"name": "high"}).json()["profile"] == "high"
    assert c.post("/api/profile", json={"name": "zzz"}).status_code == 400
    assert c.post("/api/calibrate").json()["ok"]
    assert "E-Home Radar" in c.get("/").text


def test_websocket_hello():
    c, _ = make_client()
    with c.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
