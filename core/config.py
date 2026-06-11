import os
import re
import logging

logger = logging.getLogger(__name__)


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s: invalid integer %r; using %s", name, raw, default)
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        logger.warning("%s: invalid float %r; using %s", name, raw, default)
        return default


def _get_csv(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())


def _frame_ancestors() -> str:
    raw = os.environ.get("PH_INTERCEPT_FRAME_ANCESTORS", "'self'").strip() or "'self'"
    parts = []
    for source in raw.split():
        normalized = source.strip()
        if normalized in {"self", "none"}:
            normalized = f"'{normalized}'"
        parts.append(normalized)
    return " ".join(parts) or "'self'"


PROVIDER = os.environ.get("PROVIDER", "pihole").lower()

PIHOLE_BASE = os.environ.get("PIHOLE_URL", "http://pihole:8053/api")
_ssl_raw = os.environ.get("PIHOLE_VERIFY_SSL", "true").strip().lower()
PIHOLE_VERIFY_SSL = _ssl_raw not in ("false", "0", "no")
PIHOLE_DASHBOARD = PIHOLE_BASE.rstrip('/').removesuffix('/api') + '/admin'

ADGUARD_BASE = os.environ.get("ADGUARD_URL", "http://adguard:3000/control")
_adguard_ssl_raw = os.environ.get("ADGUARD_VERIFY_SSL", "true").strip().lower()
ADGUARD_VERIFY_SSL = _adguard_ssl_raw not in ("false", "0", "no")
ADGUARD_DASHBOARD = ADGUARD_BASE.rstrip('/').removesuffix('/control') + '/'

TECHNITIUM_DASHBOARD = os.environ.get("TECHNITIUM_DASHBOARD", "http://127.0.0.1:5380")
_technitium_ssl_raw = os.environ.get("TECHNITIUM_VERIFY_SSL", "true").strip().lower()
TECHNITIUM_VERIFY_SSL = _technitium_ssl_raw not in ("false", "0", "no")
TECHNITIUM_API_BASE = os.environ.get("TECHNITIUM_API_URL", TECHNITIUM_DASHBOARD).strip().rstrip("/")
TECHNITIUM_API_TOKEN = os.environ.get("TECHNITIUM_API_TOKEN", "").strip()
TECHNITIUM_API_USER = os.environ.get("TECHNITIUM_API_USER", "").strip()
TECHNITIUM_API_PASSWORD = os.environ.get("TECHNITIUM_API_PASSWORD", "")
TECHNITIUM_API_TOTP = os.environ.get("TECHNITIUM_API_TOTP", "").strip()
TECHNITIUM_API_NODE = os.environ.get("TECHNITIUM_API_NODE", "").strip()
TECHNITIUM_API_QUERY_LOG_NAME = os.environ.get("TECHNITIUM_API_QUERY_LOG_NAME", "Query Logs (Sqlite)").strip()
TECHNITIUM_API_QUERY_LOG_CLASS_PATH = os.environ.get("TECHNITIUM_API_QUERY_LOG_CLASS_PATH", "QueryLogsSqlite.App").strip()
TECHNITIUM_API_STATS_TYPE = os.environ.get("TECHNITIUM_API_STATS_TYPE", "LastDay").strip()
TECHNITIUM_API_ENTRIES_PER_PAGE = _get_int("TECHNITIUM_API_ENTRIES_PER_PAGE", 50)
TECHNITIUM_API_POLL_SECONDS = _get_float("TECHNITIUM_API_POLL_SECONDS", 1.0)
_technitium_api_control_raw = os.environ.get("TECHNITIUM_API_ALLOW_CONTROL", "false").strip().lower()
TECHNITIUM_API_ALLOW_CONTROL = _technitium_api_control_raw in ("true", "1", "yes")
TECHNITIUM_REPLAY_RECENT = _get_int("TECHNITIUM_REPLAY_RECENT", 20)
TECHNITIUM_REPLAY_MAX_AGE_SECONDS = _get_int("TECHNITIUM_REPLAY_MAX_AGE_SECONDS", 120)
TECHNITIUM_CLIENT_NAMES = os.environ.get("TECHNITIUM_CLIENT_NAMES", "")
TECHNITIUM_DOMAIN_LABELS = os.environ.get("TECHNITIUM_DOMAIN_LABELS", "")
TECHNITIUM_DOMAIN_LABEL_MODE = os.environ.get("TECHNITIUM_DOMAIN_LABEL_MODE", "prefix").strip().lower()
_technitium_infer_labels_raw = os.environ.get("TECHNITIUM_INFER_DOMAIN_LABELS", "true").strip().lower()
TECHNITIUM_INFER_DOMAIN_LABELS = _technitium_infer_labels_raw not in ("false", "0", "no")

PH_INTERCEPT_ALLOWED_ORIGINS = _get_csv("PH_INTERCEPT_ALLOWED_ORIGINS")
PH_INTERCEPT_FRAME_ANCESTORS = _frame_ancestors()

RETURN_URL = os.environ.get("RETURN_URL", "")
BG_IMAGE = os.environ.get("BG_IMAGE", "")
BG_MODE = "image" if BG_IMAGE else os.environ.get("BG_MODE", "starfield").lower()
SKY_PRESET = os.environ.get("SKY_PRESET", "summer_triangle").lower()

SKY_PRESETS = {
    "summer_triangle": {"ra": 19.27, "dec": 15.86},
    "orion": {"ra": 5.60, "dec": 0.00},
    "scorpius": {"ra": 17.00, "dec": -30.0},
    "southern_cross": {"ra": 12.47, "dec": -60.0},
}

def _compile_ignore_patterns(raw: str, env_var: str = "pattern") -> list[re.Pattern]:
    import logging
    patterns = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            patterns.append(re.compile(p, re.IGNORECASE))
        except re.error as e:
            logging.getLogger(__name__).warning("%s: invalid pattern %r skipped (%s)", env_var, p, e)
    return patterns

IGNORE_DOMAIN_PATTERNS: list[re.Pattern] = _compile_ignore_patterns(
    os.environ.get("PIHOLE_IGNORE_DOMAINS", ""), "PIHOLE_IGNORE_DOMAINS"
)
ADGUARD_IGNORE_DOMAIN_PATTERNS: list[re.Pattern] = _compile_ignore_patterns(
    os.environ.get("ADGUARD_IGNORE_DOMAINS", ""), "ADGUARD_IGNORE_DOMAINS"
)
TECHNITIUM_IGNORE_DOMAIN_PATTERNS: list[re.Pattern] = _compile_ignore_patterns(
    os.environ.get("TECHNITIUM_IGNORE_DOMAINS", ""), "TECHNITIUM_IGNORE_DOMAINS"
)
