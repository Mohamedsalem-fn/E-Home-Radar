#!/usr/bin/env bash
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
# Installs E-Home Radar into a local venv and (optionally) as a systemd user service.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -q -e ".[dev]"
[ -f config.yaml ] || cp config.example.yaml config.yaml
.venv/bin/ehome-radar doctor || echo "doctor reported issues (see above)"
if [ "${1:-}" = "--service" ]; then
  mkdir -p ~/.config/systemd/user
  cp deploy/ehome-radar.service ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now ehome-radar.service
  echo "service enabled: systemctl --user status ehome-radar"
fi
echo "Run: .venv/bin/ehome-radar run   ->  http://127.0.0.1:8787"

