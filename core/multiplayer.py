import json
import secrets
from pathlib import Path

_SESSION_FILE = Path("/app/data/.2p_session")
RELAY_WS_BASE = "wss://relay.intercept.work/relay"

_VALID_MODES = frozenset(["off", "local", "remote"])


def _load() -> dict:
    try:
        return json.loads(_SESSION_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(data))


def _trunc(h: str) -> str:
    return h[:4] + "..." + h[-4:] if len(h) > 8 else h


def _remote_fields(data: dict) -> dict:
    sid = data.get("session_id", "")
    key = data.get("session_key", "")
    return {
        "session_id":       _trunc(sid),
        "session_key":      _trunc(key),
        "session_id_full":  sid,
        "session_key_full": key,
        "relay_url":        f"{RELAY_WS_BASE}/{sid}" if sid else "",
    }


def get_status(local_configured: bool) -> dict:
    data = _load()
    mode = data.get("mode", "off")
    out: dict = {"mode": mode, "local_configured": local_configured}
    if mode == "remote":
        out.update(_remote_fields(data))
    return out


def set_mode(mode: str, local_configured: bool) -> dict:
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode!r}")
    if mode == "local" and not local_configured:
        raise ValueError("local mode requires PIHOLE2_URL")
    data = _load()
    data["mode"] = mode
    if mode == "remote" and not (data.get("session_id") and data.get("session_key")):
        data["session_id"] = secrets.token_hex(32)
        data["session_key"] = secrets.token_hex(32)
    _save(data)
    return get_status(local_configured)


def rotate(local_configured: bool) -> dict:
    data = _load()
    data["session_id"] = secrets.token_hex(32)
    data["session_key"] = secrets.token_hex(32)
    _save(data)
    return get_status(local_configured)
