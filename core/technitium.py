import asyncio
import ipaddress
import json
import logging
import re
from collections import deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache

import httpx

from .config import (
    TECHNITIUM_API_ALLOW_CONTROL,
    TECHNITIUM_API_BASE,
    TECHNITIUM_API_ENTRIES_PER_PAGE,
    TECHNITIUM_API_NODE,
    TECHNITIUM_API_PASSWORD,
    TECHNITIUM_API_POLL_SECONDS,
    TECHNITIUM_API_QUERY_LOG_CLASS_PATH,
    TECHNITIUM_API_QUERY_LOG_NAME,
    TECHNITIUM_API_STATS_TYPE,
    TECHNITIUM_API_TOKEN,
    TECHNITIUM_API_TOTP,
    TECHNITIUM_API_USER,
    TECHNITIUM_CLIENT_NAMES,
    TECHNITIUM_DOMAIN_LABEL_MODE,
    TECHNITIUM_DOMAIN_LABELS,
    TECHNITIUM_INFER_DOMAIN_LABELS,
    TECHNITIUM_IGNORE_DOMAIN_PATTERNS,
    TECHNITIUM_REPLAY_MAX_AGE_SECONDS,
    TECHNITIUM_REPLAY_RECENT,
)

logger = logging.getLogger(__name__)

_technitium_ws_clients: set = set()
_technitium_api_token: str | None = TECHNITIUM_API_TOKEN or None
_technitium_api_login_token = False
_technitium_api_auth_lock: asyncio.Lock = asyncio.Lock()
_technitium_api_seen_keys: deque[str] = deque()
_technitium_api_seen_set: set[str] = set()
_technitium_api_warm = False
_technitium_reenable_task: asyncio.Task | None = None
_technitium_api_last_error: str | None = None

_DEFAULT_DOMAIN_LABELS = [
    (r"(^|\.)googlesyndication\.com$", "Google Ads"),
    (r"(^|\.)doubleclick\.net$", "Google Ads"),
    (r"(^|\.)google-analytics\.com$", "Google Analytics"),
    (r"(^|\.)googleadservices\.com$", "Google Ads"),
    (r"(^|\.)2mdn\.net$", "Google Ads"),
    (r"(^|\.)googleapis\.com$", "Google APIs"),
    (r"(^|\.)googleusercontent\.com$", "Google CDN"),
    (r"(^|\.)gstatic\.com$", "Google Static"),
    (r"(^|\.)google\.com$", "Google"),
    (r"(^|\.)adnxs\.com$", "AppNexus Ads"),
    (r"(^|\.)scorecardresearch\.com$", "Comscore Tracker"),
    (r"(^|\.)amplitude\.com$", "Amplitude Analytics"),
    (r"(^|\.)segment\.com$", "Segment Analytics"),
    (r"(^|\.)mixpanel\.com$", "Mixpanel Analytics"),
    (r"(^|\.)demdex\.net$", "Adobe Tracker"),
    (r"(^|\.)omtrdc\.net$", "Adobe Tracker"),
    (r"(^|\.)adobedc\.net$", "Adobe Tracker"),
    (r"(^|\.)snapchat\.com$", "Snapchat Tracker"),
    (r"(^|\.)sc-static\.net$", "Snapchat CDN"),
    (r"(^|\.)grammarly\.com$", "Grammarly Tracker"),
    (r"(^|\.)globalsiteanalytics\.com$", "Analytics Tracker"),
    (r"(^|\.)nflxvideo\.net$", "Netflix Video"),
    (r"(^|\.)netflix\.com$", "Netflix"),
    (r"(^|\.)nel\.cloudflare\.com$", "Cloudflare Telemetry"),
    (r"(^|\.)cloudflare\.com$", "Cloudflare"),
    (r"(^|\.)apple-dns\.net$", "Apple DNS"),
    (r"(^|\.)apple\.com$", "Apple"),
    (r"(^|\.)aaplimg\.com$", "Apple CDN"),
    (r"(^|\.)icloud\.com$", "Apple iCloud"),
    (r"(^|\.)akadns\.net$", "Akamai DNS"),
    (r"(^|\.)akamai(?:hd)?\.net$", "Akamai CDN"),
    (r"(^|\.)fastly\.net$", "Fastly CDN"),
    (r"(^|\.)microsoft\.com$", "Microsoft"),
    (r"(^|\.)office\.com$", "Microsoft Office"),
    (r"(^|\.)windowsupdate\.com$", "Windows Update"),
    (r"(^|\.)delivery\.mp\.microsoft\.com$", "Microsoft Delivery"),
    (r"(^|\.)azureedge\.net$", "Microsoft Azure CDN"),
    (r"(^|\.)visualstudio\.microsoft\.com$", "Visual Studio"),
    (r"(^|\.)steampowered\.com$", "Steam"),
    (r"(^|\.)steamcommunity\.com$", "Steam Community"),
    (r"(^|\.)steaminventoryhelper\.com$", "Steam Inventory Helper"),
    (r"(^|\.)github\.com$", "GitHub"),
    (r"(^|\.)githubusercontent\.com$", "GitHub CDN"),
    (r"(^|\.)metamask\.github\.io$", "MetaMask"),
    (r"(^|\.)github\.io$", "GitHub Pages"),
    (r"(^|\.)amazonaws\.com$", "AWS"),
    (r"(^|\.)openai\.com$", "OpenAI"),
    (r"(^|\.)chatgpt\.com$", "ChatGPT"),
    (r"(^|\.)oaistatic\.com$", "OpenAI Static"),
    (r"(^|\.)facebook\.com$", "Facebook"),
    (r"(^|\.)metamask\.io$", "MetaMask"),
    (r"(^|\.)sentry\.io$", "Sentry Telemetry"),
    (r"(^|\.)sentry\.[^.]+\.", "Sentry Telemetry"),
    (r"(^|\.)bugsnag\.com$", "Bugsnag Telemetry"),
    (r"(^|\.)falais\.com$", "Anti-phishing Extension"),
    (r"(^|\.)exp-tas\.com$", "Experiments Service"),
    (r"(^|\.)jsdelivr\.net$", "jsDelivr CDN"),
]

_LOCAL_SUFFIXES = (
    ".arpa",
    ".home.arpa",
    ".in-addr.arpa",
    ".ip6.arpa",
    ".local",
    ".localhost",
)

_MULTI_PART_PUBLIC_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au",
    "co.nz", "com.br", "com.mx",
    "co.jp", "co.kr", "com.cn",
}


def _normalize_client_key(client: str) -> str:
    raw = str(client or "").strip()
    if not raw:
        return ""
    text = raw.strip("[]")
    try:
        ip = ipaddress.ip_address(text)
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if ip.is_loopback:
            return "__loopback__"
        return str(ip)
    except ValueError:
        return raw.lower()


def _store_client_name(names: dict[str, str], client: str, name: str) -> None:
    client, name = str(client or "").strip(), str(name or "").strip()
    if not client or not name:
        return
    names[client] = name
    normalized = _normalize_client_key(client)
    if normalized:
        names[normalized] = name


def _client_names() -> dict[str, str]:
    raw = TECHNITIUM_CLIENT_NAMES.strip()
    if not raw:
        return {}
    names: dict[str, str] = {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                _store_client_name(names, str(key), str(value))
            return names
    except json.JSONDecodeError:
        pass

    for item in raw.split(","):
        if "=" not in item:
            continue
        client, name = item.split("=", 1)
        _store_client_name(names, client, name)
    return names


def _client_label(client: str) -> str:
    raw = str(client or "").strip()
    if not raw:
        return ""
    normalized = _normalize_client_key(raw)
    names = _client_names()
    if raw in names:
        return names[raw]
    if normalized in names:
        return names[normalized]
    if normalized == "__loopback__":
        return "Localhost"
    return raw


def _parse_entry_timestamp(entry: dict) -> datetime | None:
    value = entry.get("timestamp") or entry.get("time")
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")
    if " " in text and "T" not in text:
        candidates.append(text.replace(" ", "T", 1))
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _entry_is_fresh_for_replay(entry: dict, now: datetime) -> bool:
    if TECHNITIUM_REPLAY_MAX_AGE_SECONDS <= 0:
        return True
    timestamp = _parse_entry_timestamp(entry)
    if timestamp is None:
        return True
    age = (now - timestamp.astimezone(timezone.utc)).total_seconds()
    return age <= TECHNITIUM_REPLAY_MAX_AGE_SECONDS


@lru_cache(maxsize=1)
def _domain_label_rules() -> list[tuple[re.Pattern, str]]:
    rules: list[tuple[re.Pattern, str]] = []

    raw = TECHNITIUM_DOMAIN_LABELS.strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for pattern, label in parsed.items():
                    rules.append((re.compile(str(pattern), re.IGNORECASE), str(label)))
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "pattern" in item and "label" in item:
                        rules.append((re.compile(str(item["pattern"]), re.IGNORECASE), str(item["label"])))
        except (json.JSONDecodeError, re.error):
            rules.clear()
            for item in raw.split(","):
                if "=" not in item:
                    continue
                pattern, label = item.split("=", 1)
                pattern, label = pattern.strip(), label.strip()
                if pattern and label:
                    try:
                        rules.append((re.compile(pattern, re.IGNORECASE), label))
                    except re.error as exc:
                        logger.warning("TECHNITIUM_DOMAIN_LABELS: invalid pattern %r skipped (%s)", pattern, exc)

    for pattern, label in _DEFAULT_DOMAIN_LABELS:
        rules.append((re.compile(pattern, re.IGNORECASE), label))
    return rules


def _display_domain(domain: str) -> str:
    for pattern, label in _domain_label_rules():
        if pattern.search(domain):
            if TECHNITIUM_DOMAIN_LABEL_MODE == "replace":
                return label
            return f"{label}: {domain}"
    inferred = _infer_domain_label(domain)
    if inferred:
        if TECHNITIUM_DOMAIN_LABEL_MODE == "replace":
            return inferred
        return f"{inferred}: {domain}"
    return domain


def _infer_domain_label(domain: str) -> str | None:
    if not TECHNITIUM_INFER_DOMAIN_LABELS:
        return None

    clean = domain.strip(".").lower()
    if not clean or any(clean.endswith(suffix) for suffix in _LOCAL_SUFFIXES):
        return None

    parts = [part for part in clean.split(".") if part]
    if len(parts) < 2:
        return None

    suffix = ".".join(parts[-2:])
    sld_index = -3 if suffix in _MULTI_PART_PUBLIC_SUFFIXES and len(parts) >= 3 else -2
    sld = parts[sld_index]
    if not sld or sld in {"www", "api", "cdn", "static", "assets"}:
        return None

    words = [word for word in re.split(r"[-_]+", sld) if word]
    if not words:
        return None

    acronyms = {
        "aws": "AWS",
        "cdn": "CDN",
        "dns": "DNS",
        "api": "API",
        "ai": "AI",
        "io": "IO",
    }
    return " ".join(acronyms.get(word, word.capitalize()) for word in words)


def _api_with_node(params: dict | None = None) -> dict:
    merged = dict(params or {})
    if TECHNITIUM_API_NODE and "node" not in merged:
        merged["node"] = TECHNITIUM_API_NODE
    return merged


def _as_bool(value, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "enabled", "enable"}:
        return True
    if text in {"false", "0", "no", "disabled", "disable"}:
        return False
    return default


def _api_response(root: dict | None) -> dict:
    if not isinstance(root, dict):
        return {}
    response = root.get("response")
    return response if isinstance(response, dict) else {}


async def _api_ensure_auth(http_client: httpx.AsyncClient) -> bool:
    global _technitium_api_last_error, _technitium_api_token, _technitium_api_login_token
    if _technitium_api_token:
        return True
    if not (TECHNITIUM_API_USER and TECHNITIUM_API_PASSWORD):
        _technitium_api_last_error = "auth_required"
        logger.debug("Technitium API source requires TECHNITIUM_API_TOKEN or user/password")
        return False

    async with _technitium_api_auth_lock:
        if _technitium_api_token:
            return True
        params = {
            "user": TECHNITIUM_API_USER,
            "pass": TECHNITIUM_API_PASSWORD,
            "includeInfo": "false",
        }
        if TECHNITIUM_API_TOTP:
            params["totp"] = TECHNITIUM_API_TOTP
        try:
            resp = await http_client.get(f"{TECHNITIUM_API_BASE}/api/user/login", params=params, timeout=5.0)
            data = resp.json()
        except Exception:
            _technitium_api_last_error = "auth_failed"
            logger.debug("Technitium API login failed", exc_info=True)
            return False
        if data.get("status") == "ok" and data.get("token"):
            _technitium_api_token = str(data["token"])
            _technitium_api_login_token = True
            _technitium_api_last_error = None
            return True
        _technitium_api_last_error = str(data.get("status") or "auth_rejected")
        logger.debug("Technitium API login rejected: %s", data.get("status") or resp.status_code)
        return False


async def _api_drop_session(http_client: httpx.AsyncClient) -> None:
    global _technitium_api_token, _technitium_api_login_token
    if not (_technitium_api_token and _technitium_api_login_token):
        _technitium_api_token = TECHNITIUM_API_TOKEN or None
        _technitium_api_login_token = False
        return
    token = _technitium_api_token
    _technitium_api_token = None
    _technitium_api_login_token = False
    try:
        await http_client.get(
            f"{TECHNITIUM_API_BASE}/api/user/logout",
            headers={"Authorization": f"Bearer {token}"},
            timeout=1.5,
        )
    except Exception:
        pass


async def _api_call(
    http_client: httpx.AsyncClient,
    path: str,
    params: dict | None = None,
    *,
    method: str = "GET",
    retry: bool = True,
    timeout: float = 3.0,
) -> dict | None:
    global _technitium_api_last_error, _technitium_api_token
    if not TECHNITIUM_API_BASE:
        _technitium_api_last_error = "api_url_missing"
        return None
    if not await _api_ensure_auth(http_client):
        return None

    url = f"{TECHNITIUM_API_BASE}/api/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {_technitium_api_token}"}
    try:
        resp = await http_client.request(method, url, params=params, headers=headers, timeout=timeout)
        data = resp.json()
    except Exception:
        _technitium_api_last_error = "api_unreachable"
        logger.debug("Technitium API call failed: %s", path, exc_info=True)
        return None

    if data.get("status") == "invalid-token":
        _technitium_api_last_error = "invalid-token"
        if retry and _technitium_api_login_token:
            _technitium_api_token = None
            return await _api_call(http_client, path, params, method=method, retry=False, timeout=timeout)
        return None
    if data.get("status") not in (None, "ok"):
        _technitium_api_last_error = str(data.get("status") or "api_error")
        logger.debug("Technitium API call %s returned %s", path, data.get("status"))
        return None
    _technitium_api_last_error = None
    return data


def _api_source_for_response_type(response_type: str) -> str:
    text = (response_type or "").strip().lower()
    if text in {"4", "blocked"} or "blocked" in text:
        return "blocked"
    if text in {"3", "cached", "cache"}:
        return "cache"
    if text in {"1", "authoritative", "local"}:
        return "local"
    return "upstream"


def _api_entry_key(entry: dict) -> str:
    fields = (
        entry.get("timestamp"),
        entry.get("clientIpAddress"),
        entry.get("protocol"),
        entry.get("responseType"),
        entry.get("rcode"),
        entry.get("qname"),
        entry.get("qtype"),
        entry.get("qclass"),
        entry.get("answer"),
    )
    return "|".join("" if value is None else str(value) for value in fields)


def _remember_api_key(key: str) -> bool:
    if key in _technitium_api_seen_set:
        return False
    while len(_technitium_api_seen_keys) >= 500:
        _technitium_api_seen_set.discard(_technitium_api_seen_keys.popleft())
    _technitium_api_seen_keys.append(key)
    _technitium_api_seen_set.add(key)
    return True


def _api_entry_to_event(entry: dict) -> dict | None:
    domain = entry.get("qname") or "unknown"
    if TECHNITIUM_IGNORE_DOMAIN_PATTERNS and any(
        pattern.search(domain) for pattern in TECHNITIUM_IGNORE_DOMAIN_PATTERNS
    ):
        return None
    source = _api_source_for_response_type(str(entry.get("responseType") or ""))
    client_ip = entry.get("clientIpAddress") or ""
    return {
        "domain": _display_domain(domain),
        "raw_domain": domain,
        "status": "blocked" if source == "blocked" else "allowed",
        "source": source,
        "client": _client_label(client_ip),
    }


async def _fetch_api_stats(http_client: httpx.AsyncClient) -> dict | None:
    stats_data = await _api_call(
        http_client,
        "dashboard/stats/get",
        _api_with_node({"type": TECHNITIUM_API_STATS_TYPE or "LastDay", "utc": "true"}),
        timeout=5.0,
    )
    if not stats_data:
        return {"error": _technitium_api_last_error or "api_unavailable", "blocking": None}

    response = _api_response(stats_data)
    stats = response.get("stats") if isinstance(response.get("stats"), dict) else {}
    queries = int(stats.get("totalQueries") or 0)
    blocked = int(stats.get("totalBlocked") or 0)
    gravity = int(stats.get("blockListZones") or 0) + int(stats.get("blockedZones") or 0)

    blocking = True
    settings_data = await _api_call(http_client, "settings/get", _api_with_node(), timeout=5.0)
    settings = _api_response(settings_data)
    if "enableBlocking" in settings:
        blocking = _as_bool(settings.get("enableBlocking"), True)

    return {
        "queries": queries,
        "blocked": blocked,
        "percent": round(blocked / queries * 100, 1) if queries else 0.0,
        "gravity": gravity,
        "blocking": blocking,
        "block_timer": None,
    }


async def _fetch_api_log_entries(http_client: httpx.AsyncClient) -> list[dict] | None:
    per_page = max(1, min(100, TECHNITIUM_API_ENTRIES_PER_PAGE))
    data = await _api_call(
        http_client,
        "logs/query",
        _api_with_node({
            "name": TECHNITIUM_API_QUERY_LOG_NAME,
            "classPath": TECHNITIUM_API_QUERY_LOG_CLASS_PATH,
            "pageNumber": "1",
            "entriesPerPage": str(per_page),
            "descendingOrder": "true",
        }),
        timeout=5.0,
    )
    if data is None:
        return None
    response = _api_response(data)
    entries = response.get("entries")
    return entries if isinstance(entries, list) else []


def _events_from_entries(entries: list[dict], limit: int = 20) -> list[dict]:
    events: list[dict] = []
    for entry in entries[:limit]:
        event = _api_entry_to_event(entry)
        if event:
            events.append(event)
    return events


async def get_initial_events(http_client: httpx.AsyncClient) -> list[dict]:
    global _technitium_api_warm
    entries = await _fetch_api_log_entries(http_client)
    if entries is None:
        return []
    if not entries:
        if not _technitium_api_warm:
            _technitium_api_warm = True
        return []

    replay_candidates = entries
    if TECHNITIUM_REPLAY_MAX_AGE_SECONDS > 0:
        now = datetime.now(timezone.utc)
        replay_candidates = [entry for entry in entries if _entry_is_fresh_for_replay(entry, now)]
    replay = max(0, min(TECHNITIUM_REPLAY_RECENT, len(replay_candidates)))
    selected = list(reversed(replay_candidates[:replay]))

    if not _technitium_api_warm:
        for entry in entries:
            _remember_api_key(_api_entry_key(entry))
        _technitium_api_warm = True

    return _events_from_entries(selected)


async def _fetch_api_events(http_client: httpx.AsyncClient) -> list[dict]:
    global _technitium_api_warm
    entries = await _fetch_api_log_entries(http_client)
    if entries is None:
        return []
    if not entries:
        if not _technitium_api_warm:
            _technitium_api_warm = True
        return []

    if not _technitium_api_warm:
        for entry in entries:
            _remember_api_key(_api_entry_key(entry))
        _technitium_api_warm = True
        return []

    selected = []
    for entry in reversed(entries):
        if _remember_api_key(_api_entry_key(entry)):
            selected.append(entry)
    return _events_from_entries(selected)


async def _api_set_blocking(http_client: httpx.AsyncClient, enable: bool, timer: int | None = None) -> dict:
    global _technitium_reenable_task
    if not TECHNITIUM_API_ALLOW_CONTROL:
        return {"error": "Technitium API controls are disabled; set TECHNITIUM_API_ALLOW_CONTROL=true", "blocking": None}

    current_task = asyncio.current_task()
    if (
        _technitium_reenable_task
        and _technitium_reenable_task is not current_task
        and not _technitium_reenable_task.done()
    ):
        _technitium_reenable_task.cancel()
    _technitium_reenable_task = None

    if not enable and timer and timer > 0:
        minutes = max(1, int((timer + 59) / 60))
        data = await _api_call(
            http_client,
            "settings/temporaryDisableBlocking",
            _api_with_node({"minutes": str(minutes)}),
            timeout=5.0,
        )
        if data:
            _technitium_reenable_task = asyncio.create_task(_reenable_after(http_client, timer))
            return {"blocking": False, "block_timer": timer}
        return {"error": "api request failed"}

    data = await _api_call(
        http_client,
        "settings/set",
        _api_with_node({"enableBlocking": "true" if enable else "false"}),
        method="POST",
        timeout=5.0,
    )
    if not data:
        return {"error": "api request failed"}
    return {"blocking": enable}


async def _reenable_after(http_client: httpx.AsyncClient, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await _api_set_blocking(http_client, True, None)
    except Exception:
        logger.debug("Technitium API scheduled re-enable failed", exc_info=True)


async def _api_force_update_block_lists(http_client: httpx.AsyncClient) -> dict:
    if not TECHNITIUM_API_ALLOW_CONTROL:
        return {"error": "Technitium API controls are disabled; set TECHNITIUM_API_ALLOW_CONTROL=true"}
    data = await _api_call(
        http_client,
        "settings/forceUpdateBlockLists",
        _api_with_node(),
        method="POST",
        timeout=10.0,
    )
    return {"ok": True} if data else {"error": "api request failed"}


async def get_stats(http_client: httpx.AsyncClient) -> dict | None:
    try:
        return await _fetch_api_stats(http_client)
    except Exception:
        logger.exception("Technitium stats failed")
        return None


async def toggle_blocking(http_client: httpx.AsyncClient, enable: bool, timer: int | None = None) -> dict:
    return await _api_set_blocking(http_client, enable, timer)


async def trigger_filter_update(http_client: httpx.AsyncClient) -> dict:
    return await _api_force_update_block_lists(http_client)


async def _broadcast(events: list[dict]) -> None:
    if not events or not _technitium_ws_clients:
        return
    payload = json.dumps(events)
    for q in list(_technitium_ws_clients):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            while True:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
            _technitium_ws_clients.discard(q)


def add_ws_client(q: asyncio.Queue) -> None:
    _technitium_ws_clients.add(q)


def remove_ws_client(q: asyncio.Queue) -> None:
    _technitium_ws_clients.discard(q)


async def drop_session(http_client: httpx.AsyncClient) -> None:
    await _api_drop_session(http_client)


def reset_watermark() -> None:
    global _technitium_api_warm
    _technitium_api_warm = False
    _technitium_api_seen_keys.clear()
    _technitium_api_seen_set.clear()


async def query_poller(http_client: httpx.AsyncClient) -> None:
    while True:
        await asyncio.sleep(max(0.25, TECHNITIUM_API_POLL_SECONDS))
        if not _technitium_ws_clients:
            continue
        try:
            await _broadcast(await _fetch_api_events(http_client))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Technitium query_poller tick error", exc_info=True)
