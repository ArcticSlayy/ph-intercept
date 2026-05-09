"""ph-intercept - Pi-hole DNS game."""

import asyncio
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

from core.config import BG_MODE, BG_IMAGE, PIHOLE_DASHBOARD, PIHOLE_VERIFY_SSL, RETURN_URL, SKY_PRESET, SKY_PRESETS
from core.pihole import (
    add_ws_client, get_pihole_stats, query_poller,
    remove_ws_client, reset_watermark, toggle_blocking, trigger_gravity_update,
    drop_session,
)

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_app):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=1.5, headers={"User-Agent": "ph-intercept"}, verify=PIHOLE_VERIFY_SSL)
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

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src * data: blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors *"
)


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
        "pihole_dashboard": PIHOLE_DASHBOARD,
        "bg_config": {
            "bg_mode": BG_MODE,
            "bg_image": BG_IMAGE,
            "sky_ra": preset["ra"],
            "sky_dec": preset["dec"],
            "return_url": RETURN_URL,
        },
    })


async def pihole_stats(_request: Request) -> JSONResponse:
    data = await get_pihole_stats(_http_client)
    if not data:
        return JSONResponse({})
    return JSONResponse({
        "percent":  data.get("percent"),
        "queries":  data.get("queries"),
        "blocked":  data.get("blocked"),
        "gravity":  data.get("gravity"),
        "blocking": data.get("blocking"),
        "block_timer": data.get("block_timer"),
    })


async def pihole_toggle(request: Request) -> JSONResponse:
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
    return JSONResponse(await trigger_gravity_update(_http_client))


async def pihole_events(request: Request) -> StreamingResponse:
    async def generate():
        q: asyncio.Queue = asyncio.Queue(maxsize=60)
        add_ws_client(q)
        reset_watermark()
        yield ": ok\n\n"
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
