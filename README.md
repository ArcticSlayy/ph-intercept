# ph-intercept

A DNS dashboard that runs as a standalone web app. Streams live DNS query
events from Pi-hole v6, AdGuard Home, or Technitium DNS Server and renders them
as pixel-art friendlies and enemies. Blocked queries are destroyed by the ship,
allowed queries fly through. Providers that expose write APIs support blocking
toggles and filter updates from the HUD.

Designed to be dropped in alongside an existing DNS server without replacing the
server's normal web UI.

<img width="1713" height="1254" alt="image" src="https://github.com/user-attachments/assets/791ba70f-c6cd-4495-8135-0e0d2286668e" />

---

> **AdGuard Home user?** See the [AdGuard setup guide](adguard/README.md).
>
> **Technitium DNS Server user?** Set `PROVIDER=technitium` and configure
> `TECHNITIUM_API_URL` plus a Technitium API token or login. This dashboard runs
> separately from the normal Technitium web UI and does not replace it.

## Contents

- [What This Fork Adds](#what-this-fork-adds)
- [Quick Start](#quick-start)
- [Technitium DNS Server](#technitium-dns-server)
- [Docker Images](#docker-images)
- [Visual Guide](#visual-guide)
- [Pi-hole Configuration](#pi-hole-configuration)
- [Requirements](#requirements)
- [Testing](#testing)

## What This Fork Adds

This fork keeps the original Pi-hole and AdGuard Home behavior and adds a
Technitium DNS Server provider.

| Area | Added in this fork |
|------|--------------------|
| Technitium provider | `PROVIDER=technitium`, Technitium HTTP API polling, bearer-token support, Technitium stats, icons, HUD labels, and dashboard links. |
| Defender view | Optional Squadron mode that shows recent clients as side-by-side defender ships with their own labels and visual accents. |
| Client targeting | In Squadron mode, blocked-query fire comes from the defender for the client that made the request. |
| Display labels | Optional defender names through `TECHNITIUM_CLIENT_NAMES`, built-in best-effort domain family labels, and custom labels through `TECHNITIUM_DOMAIN_LABELS`. |
| Safety | Technitium controls are read-only by default. Blocking/filter controls appear only when `TECHNITIUM_API_ALLOW_CONTROL=true`. |
| Setup | Technitium compose example, PowerShell local-run helper, and public setup docs for API tokens, LAN exposure, and private config files. |

## Quick Start

Choose a provider first:

| Provider | Required settings | Quick start |
|----------|-------------------|-------------|
| Pi-hole v6 | `PIHOLE_URL`, `PIHOLE_PASSWORD` | Use [`compose.yaml`](compose.yaml). |
| AdGuard Home | `ADGUARD_URL`, optional basic auth | See [AdGuard setup](adguard/README.md). |
| Technitium DNS Server | `PROVIDER=technitium`, `TECHNITIUM_API_URL`, credentials | See the [Technitium setup guide](technitium/README.md). |

The dashboard is a separate web app from your DNS server's normal UI. Examples
use port `4653` and bind to localhost by default so DNS activity stays private
on the host machine. For a local Technitium run, LAN access is controlled with
`PH_INTERCEPT_HOST`; for Docker, LAN access is controlled with the compose
`ports` mapping. State-changing routes require JSON and same-origin requests by
default. Expose the app only on trusted networks or behind authentication.

### Workspace layout

ph-intercept does not require a specific parent directory, but a clean DNS
workspace makes it easier to keep dashboards, DNS server config, backups, and
private runtime config separate:

```text
DNS/
  Dashboards/
    ph-intercept/
      README.md
      run-technitium-local.ps1
      compose.yaml
      compose.technitium.yaml
      technitium.local.env.example
      technitium.docker.env.example
      .env
      bg/
  Technitium/
    backups/
    configs/
    logs/
    scripts/
  Pi-hole/
    compose/
    backups/
  AdGuard/
    compose/
    backups/
```

| Path | Purpose |
|------|---------|
| `ph-intercept/.env` | Private runtime config. Put API tokens, passwords, and `TECHNITIUM_CLIENT_NAMES` here. This file is ignored by git. |
| `ph-intercept/technitium.*.env.example` | Public templates only. Copy one to `.env`; do not put real secrets in example files. |
| `ph-intercept/bg/` | Optional local background images. Ignored by git so personal images do not get committed by accident. |
| `compose.override.yaml` | Optional private Docker overrides, such as local port binding changes. Ignored by git. |

Keep real API tokens, passwords, device names, LAN IP addresses, copied query
logs, and compose overrides in ignored files.

### Pi-hole

**1.** Get your Pi-hole **app password** (not your web login password): from the Pi-hole admin panel, go to **Settings -> Web interface / API -> Configure app password**.

- **CLI users:** Create a `.env` file in the same directory as your `compose.yaml`:

  ```env
  PIHOLE_PASSWORD=your_pihole_app_password
  ```

- **Portainer users:** Skip the `.env` file. Add `PIHOLE_PASSWORD` as an environment variable directly in the Portainer stack config.

**2.** Create a `compose.yaml` (copy the example below or grab [`compose.yaml`](compose.yaml) from the repo) and update `PIHOLE_URL` to your Pi-hole's address:

<details>
<summary>Docker Compose example</summary>

```yaml
services:
  ph-intercept:
    image: ghcr.io/arcticslayy/ph-intercept:latest
    hostname: ph-intercept
    container_name: ph-intercept
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128m
          cpus: "1"
          pids: 20

    environment:
      # REQUIRED: Pi-hole v6 API endpoint
      # Example: "http://pihole.example.test:80/api"
      PIHOLE_URL: "http://CHANGE.ME:PORT/api"

      # CLI users: Create a .env file in the same dir as this compose file with:
      #  PIHOLE_PASSWORD=your_pihole_app_password
      # Portainer Web users: Add the environment variable: PIHOLE_PASSWORD=your_pihole_app_password
      PIHOLE_PASSWORD: ${PIHOLE_PASSWORD}

      # Optional: where ESC navigates to (like your homelab dashboard or homepage)
      # Accepts http://, https://, protocol-relative (//), relative paths, and custom app schemes
      # Leave blank ("") to disable ESC entirely
      RETURN_URL: ""

      # Background style: starfield | dark | nebula
      BG_MODE: starfield

      # Sky region shown when BG_MODE=starfield:
      #   summer_triangle | orion | scorpius | southern_cross
      SKY_PRESET: summer_triangle

      # Set BG_IMAGE to use a custom background. URL for an image, or /bg/your-filename.jpg
      # If set, BG_IMAGE overrides BG_MODE entirely
      BG_IMAGE: ""

      # SSL certificate verification. Set to "false" if Pi-hole uses HTTPS
      #  with a self-signed certificate. Leave as "true" for HTTP or valid HTTPS.
      PIHOLE_VERIFY_SSL: "true"

      # Optional: comma-separated regex patterns. Matching domains spawn no ships. Case-insensitive.
      # PIHOLE_IGNORE_DOMAINS: .*\.local$,.*\.internal$

    volumes:
      # Portainer Web users: This will resolve to /data/compose/<stack-id>/bg/
      - ./bg:/app/static/bg

    cap_drop:
      - ALL

    security_opt:
      - "no-new-privileges:true"

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    ports:
      # Localhost-only by default. Use "4653:4653" only behind LAN/VPN/reverse-proxy auth.
      - "127.0.0.1:4653:4653"

    # Optional: point DNS at your Pi-hole (if used for DNS resolution) or resolver directly (like Unbound)
    # dns:
    #   - your.dns.dockernet.ip

    # Optional: only needed if you use static IPs on a custom Docker network
    # Uncomment both networks blocks if you need this
    # networks:
    #   dns_net:
    #     ipv4_address: this.container.dockernet.ip

# networks:
#   dns_net:
#     external: true
```

</details>

**3.** Start the container:

```bash
docker compose up -d
```

Open `http://127.0.0.1:4653` on the host, or your authenticated LAN/reverse
proxy URL if you deliberately expose it.

---

## Technitium DNS Server

The Technitium provider is an API client. It uses Technitium's HTTP API for
dashboard stats and recent query-log events, then renders those events in the
same ph-intercept visualizer used by Pi-hole and AdGuard Home.

It does **not** replace the normal Technitium web UI. Technitium can keep
running on `http://127.0.0.1:5380` while ph-intercept runs separately on another
port, such as `http://127.0.0.1:4653`.

| Topic | Behavior |
|-------|----------|
| Data source | Technitium HTTP API: `/api/dashboard/stats/get`, `/api/logs/query`, and `/api/settings/get`. |
| Query logs | Requires an installed Query Logs app, normally **Query Logs (Sqlite)**. |
| Normal Technitium UI | Stays on its own port and remains usable. |
| Write controls | Disabled by default. Enable only with `TECHNITIUM_API_ALLOW_CONTROL=true`. |
| Private config | API tokens, login fallback values, and client display names belong in `.env`. |

For install steps, API-token permissions, LAN exposure, Docker usage, client
name mapping, and Technitium-specific variables, see the
[Technitium setup guide](technitium/README.md).

---

## Docker Images

| Tag | What it is |
|-----|------------|
| `:latest` | Latest stable release from this fork once a tag has been published. |
| `:X.Y.Z` | Pinned release (e.g. `1.2.0`). |
| `:develop` | Built automatically on every push to the `develop` branch when that workflow is enabled. May be unstable. |

### Custom backgrounds in Portainer

- Drop image files into `/data/compose/<stack-id>/bg/` on the Portainer host (where the `./bg` bind mount resolves).

## Visual Guide

### Entities

Each DNS query spawns an entity. Tier scales with how many times that domain has
queried while the entity is still on screen.

| Query result | Visual role | Notes |
|--------------|-------------|-------|
| Allowed | Friendly ship | Cache-answered queries move faster than upstream-answered ones. |
| Blocked | Enemy ship | The defender targets and destroys it. Repeat blocks mutate the sprite to the next tier while it is still on screen. |

Allowed query tiers:

<img width="487" height="354" alt="image" src="https://github.com/user-attachments/assets/7c80bb93-6ccd-4ac2-b1c9-e34a1f54cc31" />

| Tier | Condition | Shape | Color |
|------|-----------|-------|-------|
| 1 | First query | Rounded shuttle / Delta wing / X-wing | Green / Blue / Lime |
| 2 | Queried again while on screen | Heavy transport | Cyan |
| 3+ | Three or more queries while on screen | Capital ship | Gold |

Blocked query tiers:

<img width="621" height="471" alt="image" src="https://github.com/user-attachments/assets/a2da33be-7015-4b34-9c51-6904b06573d0" />

| Tier | Condition | Shape | Color |
|------|-----------|-------|-------|
| 1 | First block | Crab invader / Squid | Red |
| 2 | Blocked twice | Heavy drone | Orange |
| 3+ | Three or more | Boss | Purple |

Ship weapon color tracks tier: green for tier 1, cyan for tier 2, gold for tier 3+.

---

### Ship

The ship targets and destroys blocked entities autonomously. At five on-screen
threats, a support drone launches and flanks. At ten, a second drone deploys.
Drones are recalled when the threat count drops.

Seven ships are selectable from the HUD:

| Slot | Ship |
|------|------|
| 1 | **Protector** (NSEA Protector, default) |
| 2 | **Falcon** (Millennium Falcon) |
| 3 | **Swordfish** (Swordfish II) |
| 4 | **Enterprise** (NCC-1701) |
| 5 | **Serenity** (Firefly) |
| 6 | **Normandy** (Mass Effect) |
| 7 | **PES** (Planet Express Ship) |

Switching ships triggers a warp-out/warp-in transition that pushes nearby
entities aside.

<img width="370" height="176" alt="ships" src="https://github.com/user-attachments/assets/694a3786-10b5-4427-8f35-7d160b28c67b" />

---

### HUD

A strip across the bottom is divided into four panels:

| Panel | Shows | Interaction |
|-------|-------|-------------|
| `INTERCEPT` | Blocking status, toggle state, and active timer countdown. | Opens timed-disable choices: 10 sec, 30 sec, 5 min, or full disable. |
| `STATS` | Total queries, blocked queries, allowed queries, and block percentage. | Updates live. |
| `GRAVITY` | Current list size. | The arrow triggers a list update and confirms when done. |
| `SHIPS` | Active ship name. | Opens the ship selector. |

<img width="1376" height="105" alt="download" src="https://github.com/user-attachments/assets/cc4adf89-ac1e-402f-aed2-68ed282b49a3" />

A hamburger button at the left edge of the HUD opens the **Settings** panel:

| Setting | What it does |
|---------|--------------|
| **Friendlies** | Shows or hides friendly allowed-query entities. |
| **Client** | Shows the requesting client as a label in normal view. In Squadron view, client names move under the defender ships instead. |
| **Domain** | Shows or hides the domain label beneath each entity. |
| **Squadron** | Shows recent clients as side-by-side defender ships. Each defender has its own accent and client label. |
| **Max** | Controls how many client defenders may be visible in Squadron mode. |
| **Provider** | Opens the configured provider dashboard. |

Display settings are saved to `localStorage` and restored on next load.

For Technitium, the provider link opens `TECHNITIUM_DASHBOARD`. For Pi-hole,
it opens the Pi-hole admin panel. For AdGuard Home, it opens the AdGuard Home
UI.

---

### Background

Three modes are available via `BG_MODE`:

| Mode | Behavior |
|------|----------|
| `starfield` | Default. Renders a real section of the night sky from an accurate star catalog. The sky region is set by `SKY_PRESET`. |
| `nebula` | Procedural GPU-rendered nebula with color lobes, value noise, dust lanes, and synthetic stars. |
| `dark` | Plain black background with no extra canvas rendering overhead. |

`starfield` uses about 12,200 stars to magnitude 6.8, color-coded by spectral
type. Positions use equatorial coordinates; what you see is where the stars
actually are.

<img width="684" height="487" alt="image" src="https://github.com/user-attachments/assets/d6a04374-9341-464b-8f24-71cafc8bbbeb" />

Star data is from the **HYG Database** by David Nash ([astronexus.com](https://astronexus.com)), combining Hipparcos (ESA) and the Yale Bright Star Catalogue.

**Planets:** Mars, Jupiter, Saturn (with ring), and the Moon are computed from real orbital elements and appear at their actual sky positions, updated hourly.

**Transients:** occasional satellite passes and meteors, including the ISS.

---

## Pi-hole Configuration

Pi-hole configuration is via environment variables. Docker users usually set
them in `compose.yaml` or `.env`. Technitium-specific variables are documented
in the [Technitium variables](#technitium-variables) table above.

### Required variables

| Variable | Description |
|----------|-------------|
| `PIHOLE_PASSWORD` | Pi-hole app password. CLI: set in a `.env` file. Portainer: add as an environment variable in the stack. Get it from **Settings -> Web interface / API -> Configure app password**. |
| `PIHOLE_URL` | Pi-hole v6 API base URL, e.g. `http://pihole.example.test:8053/api` |

### Optional variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RETURN_URL` | `""` | URL that ESC navigates to. Accepts `http://`, `https://`, protocol-relative (`//`), relative paths, and custom app schemes. Leave blank to disable ESC. |
| `BG_MODE` | `starfield` | `starfield`, `dark`, or `nebula` |
| `SKY_PRESET` | `summer_triangle` | `summer_triangle`, `orion`, `scorpius`, or `southern_cross` |
| `BG_IMAGE` | `""` | Image URL or `/bg/filename.jpg`. Overrides `BG_MODE` when set. |
| `PIHOLE_VERIFY_SSL` | `true` | Set to `false` if Pi-hole uses HTTPS with a self-signed certificate. |
| `PIHOLE_IGNORE_DOMAINS` | _(unset)_ | Comma-separated regex patterns. Domains that match spawn no ships. Case-insensitive; escape literal dots (`\.local$`). Example: `.*\.local$,.*\.internal$` |

---

## Requirements

- Pi-hole provider: Pi-hole v6. Pi-hole v5 is not compatible.
- AdGuard provider: AdGuard Home reachable from the dashboard.
- Technitium provider: Technitium DNS Server, a token or login credentials, and
  a Query Logs app such as Query Logs (Sqlite).
- Local Technitium run: Python 3 and PowerShell on Windows.
- Docker run: Docker with Compose and a network route from the container to
  the selected DNS server.
- Container architectures: `linux/amd64`, `linux/arm64`, `linux/arm/v7`,
  `linux/arm/v6`, `linux/386`, `linux/riscv64`.

The default container examples listen on port `4653` and bind to localhost
unless you deliberately change the port mapping.

---

## Testing

This fork currently keeps verification lightweight. Before publishing changes,
run syntax checks and the Squadron render harness:

```bash
python -m py_compile app.py core/config.py core/technitium.py core/pihole.py core/adguard.py
node --check static/js/game.js
node tools/squadron-render-harness.cjs
```

The Squadron harness does not need a browser and confirms that multiple client
defender labels render without throwing.
