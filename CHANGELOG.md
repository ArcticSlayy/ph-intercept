# Changelog

All notable changes to ph-intercept are documented here.

---

## [1.1.1] - 2026-05-07

### Fixed

- **Sprite visibility after sleep/wake** -- entity sprites (friendlies and baddies) could become invisible after the computer slept and resumed. The browser silently clears off-screen canvas pixel data on resume; the sprite cache is now invalidated on visibility restore so sprites are rebuilt on next use.

---

## [1.1.0] - 2026-05-06

### Added

- **Settings menu** -- hamburger button in the HUD opens an on-canvas panel for display options and links. The Pi-hole dashboard link has moved here from its previous fixed position in the HUD. Choices are persisted to `localStorage`.
- **Client label display** -- entities can now show the requesting client (IP or hostname) as a label above the domain. Toggle it on from the settings menu.
- **Display toggles** -- show/hide friendly entities, domain labels, and client labels independently via the settings menu.
- **`PIHOLE_VERIFY_SSL` env var** -- set to `"false"` if your Pi-hole uses HTTPS with a self-signed certificate. Defaults to `"true"`. See `compose.yaml` for usage. Thanks to [@hassan-odimi](https://github.com/hassan-odimi) for the idea.
- **Improved mobile display** -- `viewport-fit=cover` and `env(safe-area-inset-bottom)` for better layout handling on mobile devices.
- **Memory limit** in `compose.yaml` (256 MB cap).

### Performance

- **Sprite cache** -- pixel-art bitmaps are now pre-rendered with shadow/glow to an `OffscreenCanvas` once per unique (sprite, color, glow) combination. Each frame uses a single `drawImage` call per entity instead of many shadow-blurred `fillRect` calls, significantly reducing per-frame canvas overhead at higher entity counts. This should make the game noticeably smoother across a wider range of hardware.

### Fixed

- **Drone re-dock behavior** -- drones now re-dock when 1 or fewer enemies remain on screen. Previously they would not dock until the screen was completely clear.
- **Drone targeting zone** -- drones were targeting entities anywhere on screen, including near display edges. Target selection is now clamped to the safe playfield area.
- **Friendly entity tiers** -- allowed entities were not incrementing their hit count, so friendly sprites were always stuck at tier 1 regardless of repeat queries. Friendlies now correctly display tier 2 and tier 3 sprites when the same domain appears multiple times while on screen.
- **Friendly entity brightness** -- friendly entity sprites are slightly dimmed for a cleaner overall look alongside blocked entities.
- **Background image injection** -- double-quotes in `BG_IMAGE` paths are now percent-encoded before being placed in the CSS `url()`, preventing broken styles with certain paths.
- **HUD panel overflow** -- INTERCEPT, GRAVITY, and SHIPS panels now clip their content to their own bounds, preventing edge-case draw bleed into adjacent panels.
- **SSE reconnect** -- the event stream reconnect delay now backs off exponentially on repeated failures (starting at 3 seconds, doubling up to 60 seconds max) and resets on a successful connection. Reduces noise when Pi-hole is temporarily unreachable.

### Security

- Added `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` response headers.
- Internal exception details from `toggle_blocking` and `trigger_gravity_update` are no longer forwarded to the client. A generic error is returned and the full traceback is logged server-side. (Flagged by CodeQL.)

### Removed

- DSO cluster and galaxy rendering code from `dso-render.js`. This was removed to prevent potential ugly gradient renders bleeding into the background. The starfield is unaffected.

---

## [1.0.0] - 2026-05-04

Initial public release.
