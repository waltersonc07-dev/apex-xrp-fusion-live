"""Notify-only TradingView alert relay (Telegram + recent buffer).

Never places orders. Used so TradingView can webhook a public URL we control
while LIVE_TRADING stays false.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ALERT_BUFFER = Path(os.getenv("APEX_JOURNAL_DIR", "journals")) / "recent_alerts.json"
MAX_ALERTS = 50


def _expected_secret() -> str | None:
    return os.getenv("ALERT_WEBHOOK_SECRET") or os.getenv("TRADINGVIEW_WEBHOOK_SECRET")


def secret_ok(provided: str | None) -> bool:
    expected = _expected_secret()
    return bool(expected) and bool(provided) and provided == expected


def send_telegram(text: str) -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "error": "telegram_env_missing"}
    body = json.dumps({"chat_id": chat_id, "text": text[:3500]}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return {
                "ok": bool(data.get("ok")),
                "message_id": (data.get("result") or {}).get("message_id"),
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def format_alert(payload: dict[str, Any]) -> str:
    action = str(payload.get("action") or payload.get("side") or "ALERT").upper()
    symbol = payload.get("symbol") or payload.get("ticker") or "?"
    price = payload.get("price")
    note = payload.get("note") or payload.get("message") or payload.get("text") or ""
    strategy = payload.get("strategy") or "StackedMTF"
    price_s = f" @ {price}" if price is not None else ""
    lines = [f"{action} {symbol}{price_s}", str(strategy)]
    if note:
        lines.append(str(note))
    return "\n".join(lines)


def append_alert(record: dict[str, Any]) -> None:
    ALERT_BUFFER.parent.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    if ALERT_BUFFER.exists():
        try:
            loaded = json.loads(ALERT_BUFFER.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                items = loaded
        except Exception:  # noqa: BLE001
            items = []
    items.append(record)
    items = items[-MAX_ALERTS:]
    ALERT_BUFFER.write_text(json.dumps(items, indent=2), encoding="utf-8")


def load_recent(limit: int = 20) -> list[dict[str, Any]]:
    if not ALERT_BUFFER.exists():
        return []
    try:
        items = json.loads(ALERT_BUFFER.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            return []
        return items[-limit:]
    except Exception:  # noqa: BLE001
        return []


def handle_alert_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = format_alert(payload)
    tg = send_telegram(text)
    record = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload": payload,
        "text": text,
        "telegram_ok": bool(tg.get("ok")),
        "mirrored": False,
    }
    append_alert(record)
    return {"ok": True, "telegram": tg, "text": text}
