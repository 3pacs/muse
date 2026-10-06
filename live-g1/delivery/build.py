#!/usr/bin/env python3
"""LIVE-G1-DELIVERY build script: embed authentic captures into dashboard template."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent

def main():
    template = (HERE / "template.html").read_text()
    status = json.loads((HERE / "captures/status.json").read_text())
    snapshot = json.loads((HERE / "captures/snapshot.json").read_text())
    history = json.loads((HERE / "captures/history.json").read_text())

    embedded = json.dumps({"status": status, "snapshot": snapshot})
    html = template.replace("__EMBEDDED_JSON__", embedded)

    inject = (
        "\n<script>\n"
        f"window.__STATUS__ = {json.dumps(status)};\n"
        f"window.__SNAPSHOT__ = {json.dumps(snapshot)};\n"
        f"window.__HISTORY__ = {json.dumps(history)};\n"
        "</script>\n</body>"
    )
    html = html.replace("</body>", inject)

    out = HERE / "0dte-dashboard-live-g1.html"
    out.write_text(html)
    sha = hashlib.sha256(html.encode()).hexdigest()

    receipt = {
        "artifact": "0dte-dashboard-live-g1",
        "built_at": status.get("checked_at"),
        "html_sha256": sha,
        "html_bytes": len(html),
        "adapter_version": "live-g1/v1",
        "backend_pin": "8649ad54",
        "ui_pin": "e5a8a0ce",
        "captures": {
            "status": "captures/status.json",
            "snapshot": "captures/snapshot.json",
            "history": "captures/history.json",
        },
        "template": "template.html",
    }
    (HERE / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"built {out.name}: {len(html)} bytes, sha256={sha}")

if __name__ == "__main__":
    main()
