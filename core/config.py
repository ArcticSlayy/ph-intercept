import os
import re

PROVIDER = os.environ.get("PROVIDER", "pihole").lower()

PIHOLE_BASE = os.environ.get("PIHOLE_URL", "http://pihole:8053/api")
_ssl_raw = os.environ.get("PIHOLE_VERIFY_SSL", "true").strip().lower()
PIHOLE_VERIFY_SSL = _ssl_raw not in ("false", "0", "no")
PIHOLE_DASHBOARD = PIHOLE_BASE.rstrip('/').removesuffix('/api') + '/admin'

ADGUARD_BASE = os.environ.get("ADGUARD_URL", "http://adguard:3000/control")
_adguard_ssl_raw = os.environ.get("ADGUARD_VERIFY_SSL", "true").strip().lower()
ADGUARD_VERIFY_SSL = _adguard_ssl_raw not in ("false", "0", "no")
ADGUARD_DASHBOARD = ADGUARD_BASE.rstrip('/').removesuffix('/control') + '/'

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
