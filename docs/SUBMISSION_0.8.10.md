# Glance 0.8.10 submission packet

Status: **draft, not submitted**. Platform submission is blocked until the
x86_64 and aarch64 packages both pass the complete real-device regression.

## Review findings addressed

- Added the missing `webui.bz2` launcher and made `postinst` extract it to
  `/usr/local/glance/webui` on every install and upgrade.
- Added `nginx/glance.conf` and made `postinst` deploy it to
  `/etc/nginx/conf.d/glance.conf` (validated with `nginx -t` before reload), so
  the portal's `/glance/` path serves the extracted WebUI instead of returning
  404 on a manual `dpkg -i` as well as a store install. `postrm` removes the
  route on uninstall.
- Aligned the TOS window at `/glance/`, the iframe at
  `/v2/proxy/glance/?v=0.8.10`, Glance's `server.base-url`, and the local
  socket proxy prefix.
- Added bounded SIGTERM shutdown: the proxy stops accepting requests, Glance is
  terminated with a 5-second grace period, SIGKILL is a bounded fallback, and
  the socket is removed.
- Removed `Restart=`/`RestartSec=`, added `NoNewPrivileges=true`, and kept
  volume and legacy `/mnt` writable paths optional so a missing path cannot
  cause `226/NAMESPACE`.
- Added `BUILD_PROVENANCE.md` with the upstream tag, commit, release workflow,
  license, downloaded asset names, and SHA-256 values.
- Pointed `help` at the rendered wrapper README (usage plus privacy links)
  instead of a GitHub file-browsing page, expanded the privacy policy, and
  synchronized all 14 `release_note` entries at 0.8.10.
- `postrm` now resolves an app-owned `/Volume1/@apps/glance` symlink and removes
  that exact target during purge so manual uninstall does not leave app data.
- Removed ASCII semicolons from all language values. The platform INI parser
  treats them as comment starts and truncates the Parse Result description and
  release notes (the same issue found in MiloVault).

## Build artifacts

| Platform | Package | Bytes | SHA-256 |
| --- | --- | --- | --- |
| x86_64 | `glance_0.8.10_x86_64.deb` | 6,322,372 | `8842f891a012109effcfd3ca3d7fb4d0e845897ab553b01562d47761caf22a42` |
| aarch64 | `glance_0.8.10_aarch64.deb` | 5,736,950 | `76ca02c1c0695cd3023730d8bf3da7098eccac4c8a60c34f74942f0b2fe85cdc` |

Both packages were built twice with `--twice`; consecutive builds were
byte-identical.
After the first x86_64 device pass, ASCII semicolons were removed from
`glance.lang` because the platform INI parser treats them as comment starts
(the same issue found in MiloVault), and `help` was changed from a GitHub
file-browsing URL to the rendered wrapper README. Both packages were rebuilt.
Runtime code is unchanged. These are metadata-only changes, but the runtime
evidence predates the final bytes; re-run the x86_64 device check on these
final packages when 189 is free.

## Validation status

Local checks passed:

- `python3 -m py_compile build.py backend/glance-service backend/tos_unix_proxy.py`
- `node --check frontend/app.js`
- repository build contract and `dpkg-deb --info/--contents`
- `.spec-audit/audit.py`: all PASS except the expected `useradd` fallback WARN
- WSL launcher smoke: socket created, `/` and `/v2/proxy/glance/` return 200,
  a generated static asset returns 200, SIGTERM exits within one second, and
  the socket, port, and upstream process are gone

aarch64 device smoke on 10.18.15.190 before the machine was reclaimed:

- upgrade install completed in 18 seconds; `postinst` reported active and
  socket ready after 1 second
- service active, port 18741 listening, `/var/api/glance.sock` present
- `/glance/` returned 302 to the TOS login page instead of 404; the launcher
  CSS/JS also returned 302, and the socket returned 200 with assets under
  `/v2/proxy/glance/static/...`
- the machine was immediately purged on request; full stop/start/disable/
  uninstall regression was not completed and does not count as a device pass

x86_64 full regression on 10.18.15.189 (pre-final-metadata build; passed):

- upgraded 0.8.9 to the final 0.8.10 package with `dpkg -i` (12 seconds; this
  was the first 0.8.10 build), then reinstalled the final rebuilt package
  (2 seconds) and did one fresh install on the purged machine (1 second)
- `postinst` reported service active and socket ready after 1 second; the unit
  was active and enabled, port 18741 listened on 127.0.0.1, and
  `/var/api/glance.sock` existed
- device testing exposed the remaining portal root cause: the 0.8.9 and first
  0.8.10 builds had no nginx route, so `/glance/` was 404. The final build
  ships `nginx/glance.conf`; `postinst` deployed it, `nginx -t` passed, and
  `/glance/`, `/glance/index.html`, the launcher CSS/JS, and
  `/v2/proxy/glance/` all returned 200
- graceful stop completed in 164 ms with no `timed out`/SIGKILL entries; the
  port closed, the socket and upstream process were gone
- `systemctl disable`/`stop` left the unit inactive/disabled with the wants
  symlink removed; `enable`/`start` restored active/enabled and portal 200
- `dpkg --purge` completed in 1.3 seconds and left no unit, wants symlink,
  nginx route, socket, port, process, `/usr/local/glance`,
  `/Volume1/@apps/glance`, or `glance` user/group; `nginx -t` still passed and
  `/glance/` returned 404 only because the app had been removed

aarch64 full regression is pending on an available ARM test machine. Both
device runs above predate the final metadata-only rebuild; final-byte x86_64
re-check is also pending.

## Release notes (GitHub `v0.8.10`)

```text
Glance 0.8.10 for TOS 7 (wrapper revision; upstream binaries remain v0.8.8)

- Fix the portal 404: ship nginx/glance.conf and deploy it from postinst
  (validated with nginx -t), so /glance/ serves the extracted WebUI on manual
  dpkg installs as well as store installs.
- Ship the missing webui.bz2 launcher and re-extract it on every install and
  upgrade; align the iframe, server.base-url, and socket proxy prefixes.
- Add bounded SIGTERM shutdown with a 5-second grace period and SIGKILL
  fallback; the socket is removed on stop.
- Remove Restart=, add NoNewPrivileges=true, and keep volume and /mnt paths
  optional to avoid 226/NAMESPACE.
- Expand the privacy policy, point help at the rendered wrapper README (usage
  and privacy links), and synchronize all 14 release_note entries.
- Remove ASCII semicolons from language values so the platform INI parser does
  not truncate the description or release notes.
- Document prebuilt binary provenance (upstream tag, commit, workflow, hashes).

Assets: glance_0.8.10_x86_64.deb and glance_0.8.10_aarch64.deb, each with a
.sha256 sidecar.
```

## Withdrawal prerequisites (0.8.9 in review)

| Platform | Version ID | Status |
| --- | --- | --- |
| x86_64 | `0a124ceb-de6c-41b2-a721-9c3a20516c46` | 0 (reviewing) |
| aarch64 | `56a7fd94-0de1-4d4b-bf27-90c1a1b2df0a` | 0 (reviewing) |

Withdraw each with `POST /v1/apps/{uuid}/versions/{version_id}/withdraw`
and `{"comments":"..."}` (not DELETE) after both regressions pass, then submit
0.8.10.

Run only after both real-device regressions pass.

1. Commit the 0.8.10 changes on `main` and push to
   `https://github.com/642671/tos-glance`.
2. Create and push tag `v0.8.10`.
3. Create the GitHub Release with the text above and attach
   `dist/glance_0.8.10_x86_64.deb`, `dist/glance_0.8.10_x86_64.deb.sha256`,
   `dist/glance_0.8.10_aarch64.deb`, and
   `dist/glance_0.8.10_aarch64.deb.sha256`.
4. Submit both architectures with `POST /v1/apps/{uuid}/versions` using the
   payloads below, then poll the task.
5. Check the Parse Result against the expected values: name `Glance`, version
   `0.8.10`, architecture `amd64`/`arm64`, size 6,322,372 / 5,736,950 bytes,
   the SHA-256 values above, and the full 0.8.10 release note.
6. Confirm only when both Parse Results match. If either one differs, stop and
   report instead of confirming.

```bash
git push origin main
git tag v0.8.10
git push origin v0.8.10
gh release create v0.8.10 \
  apps/tos7/dist/glance_0.8.10_x86_64.deb \
  apps/tos7/dist/glance_0.8.10_x86_64.deb.sha256 \
  apps/tos7/dist/glance_0.8.10_aarch64.deb \
  apps/tos7/dist/glance_0.8.10_aarch64.deb.sha256 \
  --title "Glance 0.8.10 for TOS 7" \
  --notes-file <release-notes.txt>
```

## TDP submission draft

Do not send these requests until both architectures pass the full regression.

| Architecture | App UUID | Version payload |
| --- | --- | --- |
| x86_64 | `b1e3aa9c-4df1-4a32-aee9-9aaa447aff8f` | `{"tag":"v0.8.10","browser_download_url":"https://github.com/642671/tos-glance/releases/download/v0.8.10/glance_0.8.10_x86_64.deb"}` |
| aarch64 | `fe40eccf-109e-40c9-8cfe-e7b75991f07b` | `{"tag":"v0.8.10","browser_download_url":"https://github.com/642671/tos-glance/releases/download/v0.8.10/glance_0.8.10_aarch64.deb"}` |

Release tag and GitHub Release `v0.8.10` have not been created yet. After
validation, publish both `.deb` files and their `.sha256` sidecars, submit each
architecture with `POST /v1/apps/{uuid}/versions`, poll the task, verify the
Parse Result (name, 0.8.10, architecture, size, SHA-256, release note), and only
then confirm.
