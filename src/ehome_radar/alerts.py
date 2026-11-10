# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Alert sinks: desktop notification and webhook."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import urllib.request
from typing import Callable, List

from .config import AlertConfig

log = logging.getLogger("ehome.alerts")


class Alerts:
    def __init__(self, cfg: AlertConfig):
        self.cfg = cfg
        self.extra: List[Callable[[str, dict], None]] = []

    def fire(self, kind: str, payload: dict) -> None:
        threading.Thread(target=self._fire, args=(kind, payload), daemon=True).start()

    def _fire(self, kind: str, payload: dict) -> None:
        if self.cfg.desktop and shutil.which("notify-send"):
            try:
                subprocess.run(
                    ["notify-send", "E-Home Radar", f"{kind}: score {payload.get('score', 0):.0f}"],
                    timeout=5, capture_output=True,
                )
            except Exception as e:  # pragma: no cover
                log.warning("notify-send failed: %s", e)
        if self.cfg.webhook_url:
            try:
                req = urllib.request.Request(
                    self.cfg.webhook_url,
                    data=json.dumps({"kind": kind, **payload}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5).read()
            except Exception as e:
                log.warning("webhook failed: %s", e)
        for fn in self.extra:
            try:
                fn(kind, payload)
            except Exception as e:  # pragma: no cover
                log.warning("custom sink failed: %s", e)

