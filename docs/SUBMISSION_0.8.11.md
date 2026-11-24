# Glance 0.8.11 submission record

Status: **x86_64 built, real-device regression passed on 192.168.2.134, ready
for TDP submission**. The aarch64 package is built and self-checked but awaits
an ARM real-device regression before submission.

## Root cause and review findings addressed

The TOSAppSelfTestingTool `-c` checker failed both architectures with:

```
ERROR [N03] nginx/glance.conf: nginx conf missing 'proxy_pass http://127.0.0.1:<listen_port>'
```

The portal path `/glance/` served the static `webui/index.html`, whose iframe
navigated to `/v2/proxy/glance/`. TOS answers a document navigation to
`/v2/proxy/<appid>/` with HTTP 403 because the navigation cannot carry the
platform CSRF header, so the application window was blank. This is the same
class of defect found in FileBrowser Quantum 2.0.4.

Changes in 0.8.11:

- `nginx/glance.conf` now proxies `/glance/` directly to
  `http://127.0.0.1:18741/` (trailing slash strips the prefix) with standard
  `X-Forwarded-*` and WebSocket headers, buffering disabled, and long read
  timeouts. `location = /glance` still redirects to `/glance/`.
- `GLANCE_BASE_URL=/glance` (was `/v2/proxy/glance`), so Glance generates asset
  and navigation URLs under the portal path.
- The Unix-socket proxy strips the platform `/v2/proxy/glance` prefix instead
  of `BASE_URL`; the socket keeps serving the platform's header-authenticated
  calls.
- `webui.bz2` remains in the package as a small compatibility landing page
  that links to `/glance/`. It is no longer in the portal request path.
- `build.py` verification now requires the nginx `proxy_pass` route, rejects
  the legacy static `alias`, and checks that the landing page links to
  `/glance/`.
- Privacy policy: version line bumped. The policy already discloses that the
  shipped default configuration enables online widgets (weather, RSS, Hacker
  News, Lobsters, GitHub releases), matching actual behaviour.
- All 14 `release_note` entries describe the direct-portal proxy fix and the
  privacy disclosure.

## Build artifacts (2026-11-24)

| Platform | Package | Bytes | SHA-256 |
| --- | --- | --- | --- |
| x86_64 | `glance_0.8.11_x86_64.deb` | 6,323,214 | `1451537b156f20cfe1ea4aa446083de1fb992d4834c8b1e2369b9e882acc8e61` |
| aarch64 | `glance_0.8.11_aarch64.deb` | 5,737,814 | `695cc1da5ffdc5eb64eea10c49f97ad6dba816b9534b825215a12cee1566341b` |

Both were built twice with `--twice`; consecutive builds were byte-identical.
The builder ran its package contract and `dpkg-deb --info/--contents` checks.

## Validation status

Official self-check (`TOSAppSelfTestingTool -c`) on both final packages:

- x86_64: `check passed`, exit 0 (N03 no longer reported)
- aarch64: `check passed`, exit 0

x86_64 real-device regression on 192.168.2.134 (TOS 7, test user, clean
machine, no prior app packages):

- remote `sha256sum` matched `1451537b...`
- `dpkg -i` completed in 2 seconds; `postinst` reported
  `service active, socket ready after 1s`
- unit `glance-system.service` active and enabled, running as non-root user
  `glance`
- `127.0.0.1:18741` listening; `/var/api/glance.sock` present with mode 660,
  owner `glance:allusers`
- portal `http://127.0.0.1:8181/glance/` returned 200 with 8,139 bytes of real
  Glance HTML (`<html lang="en" id="top" data-theme="default"...`); the old
  landing-page marker was absent, so this is the dashboard, not a wrapper
- `http://127.0.0.1:8181/glance` returned 302 to `/glance/`
- assets rendered by the dashboard returned 200:
  `/glance/static/80221f62b4/favicon.svg` and `/glance/home`
- direct request over `/var/api/glance.sock` returned 200 with the same
  8,139-byte document
- `systemctl stop` -> inactive and port closed; `start` -> active and portal
  200; `disable` -> disabled; `enable` -> enabled; `restart` -> portal 200
- `dpkg --purge` -> no `/usr/local/glance`, unit, socket, nginx route, service
  user, process, port, or dpkg entry; `nginx -t` still passed

## Release

- Tag `v0.8.11` in `642671/tos-glance`.
- Release assets: `glance_0.8.11_x86_64.deb` and its `.sha256` sidecar. The
  aarch64 `.deb` and `.sha256` will be added after the ARM regression.

## TDP record

Pending submission.