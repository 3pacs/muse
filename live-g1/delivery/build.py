#!/usr/bin/env python3
"""LIVE-G1-DELIVERY-R1 build script: embed authentic captures into dashboard template.

Data inject is placed BEFORE the app script so native boot sees it.
Receipt records exact lineage: template hash, capture hashes, build clock.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    template_path = HERE / "template.html"
    template = template_path.read_text()
    assert "__DATA_INJECT__" in template, "template missing __DATA_INJECT__ placeholder"

    status_p = HERE / "captures/status.json"
    snapshot_p = HERE / "captures/snapshot.json"
    history_p = HERE / "captures/history.json"
    status = json.loads(status_p.read_text())
    snapshot = json.loads(snapshot_p.read_text())
    history = json.loads(history_p.read_text())

    # Inject BEFORE the app script runs (fixes native boot order)
    inject = (
        "<script>\n"
        f"window.__STATUS__ = {json.dumps(status)};\n"
        f"window.__SNAPSHOT__ = {json.dumps(snapshot)};\n"
        f"window.__HISTORY__ = {json.dumps(history)};\n"
        "</script>"
    )
    html = template.replace("__DATA_INJECT__", inject)
    assert "__DATA_INJECT__" not in html, "inject placeholder survived"

    out = HERE / "0dte-dashboard-live-g1.html"
    raw = html.encode("utf-8")  # byte count is UTF-8, not str length
    out.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()

    build_at = datetime.now(timezone.utc).isoformat()  # build clock, not capture clock
    receipt = {
        "artifact": "0dte-dashboard-live-g1",
        "built_at": build_at,
        "html_sha256": sha,
        "html_bytes_utf8": len(raw),
        "adapter_version": "live-g1/v1",
        "backend_pin": "8649ad54",
        "ui_pin": "e5a8a0ce",
        "lineage": {
            "template": "template.html",
            "template_sha256": sha256_file(template_path),
            "captures": {
                "status.json": sha256_file(status_p),
                "snapshot.json": sha256_file(snapshot_p),
                "history.json": sha256_file(history_p),
            },
            "capture_recipe": [
                "python3 live_g1_adapter.py status > delivery/captures/status.json",
                "python3 live_g1_adapter.py snapshot > delivery/captures/snapshot.json",
                "python3 live_g1_adapter.py history --limit 20 > delivery/captures/history.json",
                "python3 delivery/build.py",
            ],
            "capture_clock": status.get("checked_at"),
            "build_clock": build_at,
        },
    }
    (HERE / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"built {out.name}: {len(raw)} UTF-8 bytes, sha256={sha}")

if __name__ == "__main__":
    main()
