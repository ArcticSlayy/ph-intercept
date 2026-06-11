"""ph-intercept - DNS game (Pi-hole, AdGuard Home, and Technitium DNS)."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from core.config import (
    BG_MODE,
    BG_IMAGE,
    PH_INTERCEPT_ALLOWED_ORIGINS,
    PH_INTERCEPT_FRAME_ANCESTORS,
    PROVIDER,
    RETURN_URL,
    SKY_PRESET,
    SKY_PRESETS,
)

if PROVIDER == "adguard":
    from core.config import ADGUARD_DASHBOARD as _DASHBOARD, ADGUARD_VERIFY_SSL as _VERIFY_SSL
    _READ_ONLY_PROVIDER = False
    from core.adguard import (
        add_ws_client, get_stats, query_poller, remove_ws_client,
        reset_watermark, toggle_blocking, trigger_filter_update, drop_session,
        get_initial_events,
    )
elif PROVIDER == "technitium":
    from core.config import (
        TECHNITIUM_API_ALLOW_CONTROL,
        TECHNITIUM_DASHBOARD as _DASHBOARD,
        TECHNITIUM_VERIFY_SSL as _VERIFY_SSL,
    )
    _READ_ONLY_PROVIDER = not TECHNITIUM_API_ALLOW_CONTROL
    from core.technitium import (
        add_ws_client, get_stats, query_poller, remove_ws_client,
        reset_watermark, toggle_blocking, trigger_filter_update, drop_session,
        get_initial_events,
    )
else:
    from core.config import PIHOLE_DASHBOARD as _DASHBOARD, PIHOLE_VERIFY_SSL as _VERIFY_SSL
    _READ_ONLY_PROVIDER = False
    from core.pihole import (
        add_ws_client, remove_ws_client, reset_watermark, toggle_blocking, drop_session, query_poller,
        get_pihole_stats as get_stats, trigger_gravity_update as trigger_filter_update,
        get_initial_events,
    )

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_app):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=1.5, headers={"User-Agent": "ph-intercept"}, verify=_VERIFY_SSL)
    poller = asyncio.create_task(query_poller(_http_client))
    yield
    poller.cancel()
    try:
        await poller
    except asyncio.CancelledError:
        pass
    try:
        async with asyncio.timeout(1.0):
            await drop_session(_http_client)
    except Exception:
        pass
    await _http_client.aclose()


_base = Path(__file__).parent
templates = Jinja2Templates(directory=_base / "templates")


def _asset_version() -> str:
    """Keep browser caches from serving stale JS/CSS after local updates."""
    newest = 0
    for path in (
        _base / "static" / "css" / "theme.css",
        _base / "static" / "css" / "game.css",
        _base / "static" / "js" / "splash.js",
        _base / "static" / "js" / "game-bitmaps.js",
        _base / "static" / "js" / "game.js",
    ):
        try:
            newest = max(newest, path.stat().st_mtime_ns)
        except OSError:
            pass
    return str(newest)

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src * data: blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    f"frame-ancestors {PH_INTERCEPT_FRAME_ANCESTORS}"
)


def _request_origin(request: Request) -> str:
    host = request.headers.get("host", "")
    if not host:
        return ""
    return f"{request.url.scheme}://{host}".rstrip("/")


def _origin_allowed(request: Request, origin: str) -> bool:
    normalized = origin.strip().rstrip("/")
    if not normalized:
        return False
    if normalized == _request_origin(request):
        return True
    return normalized in PH_INTERCEPT_ALLOWED_ORIGINS


def _reject_unsafe_request(request: Request) -> JSONResponse | None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return JSONResponse({"error": "application/json required"}, status_code=415)

    origin = request.headers.get("origin", "")
    if origin and not _origin_allowed(request, origin):
        return JSONResponse({"error": "origin not allowed"}, status_code=403)

    sec_fetch_site = request.headers.get("sec-fetch-site", "").lower()
    if not origin and sec_fetch_site == "cross-site":
        return JSONResponse({"error": "origin not allowed"}, status_code=403)

    return None


class ResponseHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = _CSP
        if request.url.path.startswith("/static/"):
            if request.url.path.endswith(('.woff2', '.woff', '.ttf', '.otf')):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response


async def index(request: Request) -> HTMLResponse:
    preset = SKY_PRESETS.get(SKY_PRESET, SKY_PRESETS["summer_triangle"])
    return templates.TemplateResponse(request, "index.html", {
        "bg_mode": BG_MODE,
        "provider": PROVIDER,
        "provider_dashboard": _DASHBOARD,
        "read_only_provider": _READ_ONLY_PROVIDER,
        "asset_version": _asset_version(),
        "bg_config": {
            "bg_mode": BG_MODE,
            "bg_image": BG_IMAGE,
            "sky_ra": preset["ra"],
            "sky_dec": preset["dec"],
            "return_url": RETURN_URL,
        },
    })


async def pihole_stats(_request: Request) -> JSONResponse:
    data = await get_stats(_http_client)
    if not data:
        return JSONResponse({})
    return JSONResponse({
        "percent":     data.get("percent"),
        "queries":     data.get("queries"),
        "blocked":     data.get("blocked"),
        "gravity":     data.get("gravity"),
        "blocking":    data.get("blocking"),
        "block_timer": data.get("block_timer"),
        "error":       data.get("error"),
    })


async def pihole_toggle(request: Request) -> JSONResponse:
    rejected = _reject_unsafe_request(request)
    if rejected:
        return rejected
    body = await request.json()
    timer = body.get("timer")
    if timer is not None:
        try:
            timer = int(timer)
            if timer <= 0:
                timer = None
        except (TypeError, ValueError):
            timer = None
    return JSONResponse(await toggle_blocking(_http_client, bool(body.get("enable", True)), timer))


async def pihole_gravity_update(request: Request) -> JSONResponse:
    rejected = _reject_unsafe_request(request)
    if rejected:
        return rejected
    return JSONResponse(await trigger_filter_update(_http_client))


async def pihole_events(request: Request) -> StreamingResponse:
    async def generate():
        q: asyncio.Queue = asyncio.Queue(maxsize=60)
        add_ws_client(q)
        if PROVIDER != "technitium":
            reset_watermark()
        yield ": ok\n\n"
        initial_events = await get_initial_events(_http_client)
        if initial_events:
            yield f"data: {json.dumps(initial_events)}\n\n"
        try:
            while True:
                payload = await q.get()
                if payload is None:
                    break
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            remove_ws_client(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", index),
        Route("/api/pihole/stats", pihole_stats),
        Route("/api/pihole/toggle", pihole_toggle, methods=["POST"]),
        Route("/api/pihole/gravity-update", pihole_gravity_update, methods=["POST"]),
        Route("/api/pihole/events", pihole_events),
        Mount("/static", StaticFiles(directory=_base / "static"), name="static"),
        Mount("/bg", StaticFiles(directory=_base / "static" / "bg", check_dir=False), name="bg"),
    ],
)
app.add_middleware(ResponseHeaderMiddleware)
