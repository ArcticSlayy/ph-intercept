import base64
import hashlib
import json
import re
import secrets
from pathlib import Path

_SESSION_FILE = Path("/app/data/.2p_session")
RELAY_WS_BASE = "wss://relay.intercept.work/relay"

_VALID_MODES = frozenset(["off", "local", "remote"])
_B64URL43 = re.compile(r'^[A-Za-z0-9_-]{43}$')       # session_id:  base64url, 43 chars (token_urlsafe(32))
_B85_40   = re.compile(r'^[\x21-\x7e]{40}$')         # session_key: base85,    40 printable-ASCII chars


def _load() -> dict:
    try:
        return json.loads(_SESSION_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(data))
    _SESSION_FILE.chmod(0o600)


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


def get_status(local_configured: bool, remote_enabled: bool = True) -> dict:
    data = _load()
    mode = data.get("mode", "off")
    if mode == "local" and not local_configured:
        mode = "off"
    if mode == "remote" and not remote_enabled:
        mode = "off"
    out: dict = {"mode": mode, "local_configured": local_configured, "remote_enabled": remote_enabled}
    if mode == "remote":
        out.update(_remote_fields(data))
    return out


def _new_session_id() -> str:
    return secrets.token_urlsafe(32)


def _new_session_key() -> str:
    return base64.b85encode(hashlib.blake2b(secrets.token_bytes(64), digest_size=32).digest()).decode()


def set_mode(mode: str, local_configured: bool, remote_enabled: bool = True) -> dict:
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode!r}")
    if mode == "local" and not local_configured:
        raise ValueError("local mode requires PIHOLE2_URL")
    if mode == "remote" and not remote_enabled:
        raise ValueError("remote mode is disabled (REMOTE_2P not enabled)")
    data = _load()
    data["mode"] = mode
    if mode == "remote" and not (data.get("session_id") and data.get("session_key")):
        data["session_id"] = _new_session_id()
        data["session_key"] = _new_session_key()
    _save(data)
    return get_status(local_configured, remote_enabled)


def rotate(local_configured: bool, remote_enabled: bool = True) -> dict:
    data = _load()
    data["session_id"] = _new_session_id()
    data["session_key"] = _new_session_key()
    _save(data)
    return get_status(local_configured, remote_enabled)


def get_key(remote_enabled: bool = True) -> dict | None:
    data = _load()
    if data.get("mode") != "remote" or not remote_enabled:
        return None
    return {
        "session_id_full": data.get("session_id", ""),
        "session_key_full": data.get("session_key", ""),
    }


def update_hashes(session_id: str | None, session_key: str | None, local_configured: bool, remote_enabled: bool = True) -> dict:
    if session_id is not None and not _B64URL43.match(session_id):
        raise ValueError("session_id must be 43 base64url chars")
    if session_key is not None and not _B85_40.match(session_key):
        raise ValueError("session_key must be 40 base85 chars")
    data = _load()
    if session_id is not None:
        data["session_id"] = session_id
    if session_key is not None:
        data["session_key"] = session_key
    _save(data)
    return get_status(local_configured, remote_enabled)
