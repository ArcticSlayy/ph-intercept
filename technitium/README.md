# ph-intercept - Technitium DNS Server

A standalone DNS dashboard for Technitium DNS Server. It reads live stats and
recent query events through Technitium's HTTP API, then renders those events as
the ph-intercept pixel-art dashboard.

ph-intercept runs beside Technitium. It does not replace the normal Technitium
web UI.

<img width="1713" height="1254" alt="ph-intercept dashboard" src="https://github.com/user-attachments/assets/791ba70f-c6cd-4495-8135-0e0d2286668e" />

---

## Quick Start

Use this path for a normal Technitium install on the same machine as
ph-intercept.

**1. Prepare Technitium**

1. Install and start Technitium DNS Server.
2. Open the Technitium web UI, usually `http://127.0.0.1:5380`.
3. Install or enable **Query Logs (Sqlite)** from Technitium's Apps area.
4. Make sure clients are actually using Technitium for DNS.
5. Create an API token from the Technitium user menu.

**2. Create a private `.env` file**

From the `ph-intercept` folder:

```powershell
Copy-Item technitium.local.env.example .env
notepad .env
```

Add your API token to `.env`:

```env
PROVIDER=technitium
TECHNITIUM_DASHBOARD=http://127.0.0.1:5380
TECHNITIUM_API_URL=http://127.0.0.1:5380
TECHNITIUM_API_TOKEN=replace-with-your-token
TECHNITIUM_API_ALLOW_CONTROL=false
PH_INTERCEPT_HOST=127.0.0.1
PH_INTERCEPT_PORT=4653
```

The repo ignores `.env`. Do not commit real API tokens, passwords, LAN IPs,
device names, hostnames, or copied query logs.

**3. Run ph-intercept**

On Windows PowerShell:

```powershell
.\run-technitium-local.ps1
```

Open ph-intercept:

```text
http://127.0.0.1:4653
```

The normal Technitium UI remains available at:

```text
http://127.0.0.1:5380
```

---

## How It Reads Technitium

ph-intercept does not open Technitium's query-log database file directly. It
uses Technitium's HTTP API:

| Data | Technitium API |
|------|----------------|
| Dashboard counters | `/api/dashboard/stats/get` |
| Recent query events | `/api/logs/query` |
| Blocking status | `/api/settings/get` |

The query-log API is backed by the installed Query Logs app. For a normal
single-server setup, keep these defaults:

```env
TECHNITIUM_API_QUERY_LOG_NAME=Query Logs (Sqlite)
TECHNITIUM_API_QUERY_LOG_CLASS_PATH=QueryLogsSqlite.App
```

Change them only if your Technitium install uses a different query-log app.

ph-intercept maps Technitium `responseType` values into dashboard behavior:

| Technitium response type | ph-intercept source | Visual behavior |
|--------------------------|---------------------|-----------------|
| `Blocked` or `4` | `blocked` | Enemy ship, targeted by defender |
| `Cache` or `3` | `cache` | Allowed ship, faster movement |
| `Authoritative`, `Local`, or `1` | `local` | Allowed ship |
| Everything else, including `Upstream` or `2` | `upstream` | Allowed ship |

---

## API Token Permissions

For observe-only mode, leave `TECHNITIUM_API_ALLOW_CONTROL=false` and use the
smallest permission set that works:

| Purpose | Technitium permission |
|---------|-----------------------|
| Dashboard counters | `Dashboard: View` |
| Recent query events | `Logs: View` |
| Blocking status | `Settings: View` |

Only grant `Settings: Modify` if you want ph-intercept's HUD controls to
temporarily disable/enable blocking or force a block-list update.

If an API token is not available, use the login fallback in `.env`:

```env
TECHNITIUM_API_USER=
TECHNITIUM_API_PASSWORD=
TECHNITIUM_API_TOTP=
```

Tokens and login credentials stay local to `.env`; do not put real values in
the checked-in `*.env.example` files.

---

## Defender Names

Squadron mode labels each defender with the client value reported by
Technitium, usually an IP address or hostname. To show friendlier labels, add
`TECHNITIUM_CLIENT_NAMES` to your private `.env`.

Comma-separated form:

```env
TECHNITIUM_CLIENT_NAMES=::1=Local Host,127.0.0.1=Local Host,192.168.1.50=Living Room TV
```

JSON form:

```env
TECHNITIUM_CLIENT_NAMES={"::1":"Local Host","127.0.0.1":"Local Host","192.168.1.50":"Living Room TV"}
```

`::1` is IPv6 loopback. `127.0.0.1` is IPv4 loopback. If the same physical
machine appears once as loopback and once as a LAN address, map both raw values
to the same label in `.env`.

---

## Domain Display Labels

Domain labels are display-only. They do not add block rules. Use Technitium for
blocking and use `TECHNITIUM_DOMAIN_LABELS` only when you want nicer on-screen
names.

```env
TECHNITIUM_DOMAIN_LABELS=(^|\.)ads\.example\.com$=Example Ads,(^|\.)telemetry\.example\.net$=Example Telemetry
TECHNITIUM_DOMAIN_LABEL_MODE=prefix
```

With `prefix`, ph-intercept shows labels like
`Example Ads: ads.example.com`. With `replace`, it shows only `Example Ads`.

Use `TECHNITIUM_IGNORE_DOMAINS` when a domain should not spawn any visual
entity:

```env
TECHNITIUM_IGNORE_DOMAINS=.*\.local$,.*\.home\.arpa$
```

These settings affect only the dashboard. They do not allow or block DNS.

---

## Adding Domains To Block

ph-intercept visualizes what Technitium blocks; Technitium remains the source of
truth for block lists and allow lists.

Common flows:

- For a one-off domain, add it as a blocked domain or blocked zone in
  Technitium's normal blocking UI.
- If you use the Advanced Blocking app, add it to the appropriate Advanced
  Blocking group.
- For a maintained list, add the block-list URL in Technitium's block-list
  settings or Advanced Blocking group.
- Add exceptions in Technitium's allow-list area when a list blocks something
  you need.

ph-intercept can force a block-list update only when
`TECHNITIUM_API_ALLOW_CONTROL=true` and the token has `Settings: Modify`.

---

## LAN Access

The local helper binds to localhost by default:

```env
PH_INTERCEPT_HOST=127.0.0.1
PH_INTERCEPT_PORT=4653
```

To make ph-intercept reachable from other LAN devices, bind to all interfaces:

```env
PH_INTERCEPT_HOST=0.0.0.0
PH_INTERCEPT_PORT=4653
```

Then open:

```text
http://<ph-intercept-host-lan-ip>:4653
```

This app has no built-in login. Exposing it to the LAN exposes dashboard DNS
activity to devices that can reach that port. For anything beyond a trusted LAN,
put it behind a VPN, authenticated reverse proxy, or another access-control
layer. Do not port-forward it to the public internet.

If a trusted reverse proxy changes the browser-facing origin, add that exact
origin:

```env
PH_INTERCEPT_ALLOWED_ORIGINS=https://dns.example.test,http://192.168.1.20:4653
```

---

## Docker

Docker is optional. Use it when you want a containerized dashboard:

```bash
cp technitium.docker.env.example .env
# Edit .env and add TECHNITIUM_API_TOKEN
docker compose -f compose.technitium.yaml up -d --build
```

In Docker, `TECHNITIUM_DASHBOARD` is the browser-facing Technitium link and
`TECHNITIUM_API_URL` is the container-facing API URL. On Docker Desktop,
`http://host.docker.internal:5380` usually reaches Technitium running on the
host machine.

The compose file binds ph-intercept to localhost by default:

```yaml
ports:
  - "127.0.0.1:4653:4653"
```

Change that to `4653:4653` only when the dashboard is protected appropriately
for your LAN.

---

## Same-Port Deployment

Two independent web servers cannot bind the same host and port at the same
time. To expose Technitium and ph-intercept from one public port, put a reverse
proxy in front of both services:

| Service | Internal port |
|---------|---------------|
| Technitium DNS Server UI | `5380` |
| ph-intercept | `4653` |

For example, a proxy can route `/` to Technitium and route `/intercept`,
`/static`, `/api/pihole`, and `/bg` to ph-intercept. A true in-Technitium UI
toggle would require packaging this as a Technitium app or modifying
Technitium's UI.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER` | `pihole` | Set to `technitium`. |
| `TECHNITIUM_DASHBOARD` | `http://127.0.0.1:5380` | Browser-facing Technitium UI link. |
| `TECHNITIUM_API_URL` | `TECHNITIUM_DASHBOARD` | Base URL for Technitium's HTTP API. |
| `TECHNITIUM_VERIFY_SSL` | `true` | Set to `false` only for a trusted HTTPS endpoint with a self-signed certificate. |
| `TECHNITIUM_API_TOKEN` | unset | Preferred API credential. Keep it in `.env`. |
| `TECHNITIUM_API_USER` / `TECHNITIUM_API_PASSWORD` / `TECHNITIUM_API_TOTP` | unset | Optional login fallback when no API token is supplied. |
| `TECHNITIUM_API_NODE` | unset | Optional Technitium cluster node parameter. Leave unset for a normal single-server install. |
| `TECHNITIUM_API_QUERY_LOG_NAME` | `Query Logs (Sqlite)` | Query Logs app name sent to `/api/logs/query`. |
| `TECHNITIUM_API_QUERY_LOG_CLASS_PATH` | `QueryLogsSqlite.App` | Query Logs app class path sent to `/api/logs/query`. |
| `TECHNITIUM_API_STATS_TYPE` | `LastDay` | Dashboard stats window for `/api/dashboard/stats/get`. |
| `TECHNITIUM_API_ENTRIES_PER_PAGE` | `50` | Recent API query-log rows fetched per poll, capped to 100. |
| `TECHNITIUM_API_POLL_SECONDS` | `1.0` | API query-log polling interval in seconds. |
| `TECHNITIUM_API_ALLOW_CONTROL` | `false` | Enables Technitium write controls. Keep `false` for observe-only mode. |
| `TECHNITIUM_REPLAY_RECENT` | `20` | Recent query-log rows replayed when the browser connects. |
| `TECHNITIUM_REPLAY_MAX_AGE_SECONDS` | `120` | Maximum age for startup replay rows. Set `0` to allow replay regardless of age. |
| `TECHNITIUM_CLIENT_NAMES` | unset | Optional client-to-defender-label map. |
| `TECHNITIUM_DOMAIN_LABELS` | built-in common labels | Optional domain-to-label rules. |
| `TECHNITIUM_DOMAIN_LABEL_MODE` | `prefix` | `prefix` shows `Example: domain`; `replace` shows only `Example`. |
| `TECHNITIUM_INFER_DOMAIN_LABELS` | `true` | Infer readable labels from domains when no explicit label matches. |
| `TECHNITIUM_IGNORE_DOMAINS` | unset | Comma-separated regex patterns. Matching domains spawn no ships. |
| `PH_INTERCEPT_HOST` | `127.0.0.1` | Local PowerShell helper bind address. |
| `PH_INTERCEPT_PORT` | `4653` | Local PowerShell helper port. |
| `PH_INTERCEPT_ALLOWED_ORIGINS` | unset | Optional exact trusted browser origins for write routes. |
| `PH_INTERCEPT_FRAME_ANCESTORS` | `'self'` | CSP `frame-ancestors` policy. |
| `RETURN_URL` | `http://127.0.0.1:5380` in Technitium examples | URL that ESC navigates to and dashboard link fallback. |
| `BG_MODE` | `starfield` | `starfield`, `dark`, or `nebula`. |
| `BG_IMAGE` | unset | Image URL or `/bg/filename.jpg`. Overrides `BG_MODE`. |
| `SKY_PRESET` | `summer_triangle` | `summer_triangle`, `orion`, `scorpius`, or `southern_cross`. |

---

## Requirements

- Technitium DNS Server reachable from ph-intercept.
- Query Logs app, normally **Query Logs (Sqlite)**.
- API token or login credentials.
- Local run: Python 3 and PowerShell on Windows.
- Docker run: Docker with Compose and a network route from the container to
  Technitium.

## References

- [Technitium HTTP API documentation](https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md)
- [Technitium ad-blocking/block-list overview](https://blog.technitium.com/2018/10/blocking-internet-ads-using-dns-sinkhole.html)
- [Technitium DNS Server help topics](https://technitium.com/dns/help.html)
