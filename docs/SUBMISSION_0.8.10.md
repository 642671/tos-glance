# Glance 0.8.10 submission record

Status: **x86_64 submitted and in review**. The x86_64 0.8.10 Version is
`68b2810c-b143-4a42-aa13-8f83e2afa2be` (status 0). The aarch64 package is built
and awaits an ARM real-device regression before submission.

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
- `postrm` resolves an app-owned `/Volume1/@apps/glance` symlink and removes
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
byte-identical. The final rebuild only changed metadata: the `help` URL and the
removal of ASCII semicolons from `glance.lang`.

## Validation status

Local checks passed:

- `python3 -m py_compile build.py backend/glance-service backend/tos_unix_proxy.py`
- `node --check frontend/app.js`
- repository build contract and `dpkg-deb --info/--contents`
- `.spec-audit/audit.py`: all PASS except the expected `useradd` fallback WARN
- WSL launcher smoke: socket created, `/` and `/v2/proxy/glance/` return 200,
  a generated static asset returns 200, SIGTERM exits within one second, and
  the socket, port, and upstream process are gone

x86_64 final-package regression on 10.18.15.189 (passed, 43/43 checks):

- remote `sha256sum` matched `8842f891...`; `dpkg -i` completed in 1 second
- `postinst` reported service active and socket ready after 1 second; the unit
  was active and enabled with `NRestarts=0`, port 18741 listened on
  127.0.0.1, and `/var/api/glance.sock` existed
- `/glance/` returned 200 (1,112 bytes) with the `Glance` title and
  `/v2/proxy/glance/` reference; `/glance/index.html`, the launcher CSS/JS, and
  `/v2/proxy/glance/` all returned 200
- graceful stop completed in 164 ms with no `timed out`/SIGKILL entries; the
  port closed, the socket and upstream process were gone
- `systemctl disable --now` left the unit inactive/disabled with the wants
  symlink removed; `enable --now` restored active/enabled and portal 200
- `dpkg --purge` completed in 1.275 seconds and left no package, unit, wants
  symlink, nginx route, socket, port, process, `/usr/local/glance`,
  `/Volume1/@apps/glance`, or `glance` user/group; `nginx -t` still passed and
  `/glance/` returned 404 only because the app had been removed

aarch64 was only smoke-tested on 10.18.15.190 before that machine was reclaimed:
install completed, the service was active, port 18741 listened, `webui.bz2` was
extracted, and `/glance/` returned 302 instead of 404. Stop/start/disable/
enable/purge did not complete, so it is not a device pass.

## Release

- Tag `v0.8.10` on commit `6ccaa58`.
- Release: https://github.com/642671/tos-glance/releases/tag/v0.8.10
- Uploaded now: `glance_0.8.10_x86_64.deb` and its `.sha256` sidecar.
- The aarch64 `.deb` and `.sha256` will be added after the ARM regression.

Release notes in the GitHub Release and `glance.lang` cover the portal route,
`webui.bz2`, proxy alignment, graceful shutdown, sandbox writable paths,
privacy/help, INI punctuation, and binary provenance.

## TDP record

x86_64 (`b1e3aa9c-4df1-4a32-aee9-9aaa447aff8f`):

- 0.8.9 version `0a124ceb-de6c-41b2-a721-9c3a20516c46` withdrawn, status 4
- 0.8.10 version `68b2810c-b143-4a42-aa13-8f83e2afa2be` status 0 (reviewing)
- creation task `a891bd32-155d-4914-8dbe-bae9f41cfb7e`, `all_status=2`
- Parse Result: name `Glance`, version `0.8.10`, platform `x86_64`, size
  6,322,372, SHA-256 `8842f891a012109effcfd3ca3d7fb4d0e845897ab553b01562d47761caf22a42`,
  and the full English release note
- App record: `current_version=0.8.10`

aarch64 (`fe40eccf-109e-40c9-8cfe-e7b75991f07b`):

- 0.8.9 version `56a7fd94-0de1-4d4b-bf27-90c1a1b2df0a` is still status 0
- 0.8.10 is not submitted yet

## Remaining steps

1. Run the complete aarch64 regression on the final package when an ARM machine
   is available.
2. Add the validated `glance_0.8.10_aarch64.deb` and `.sha256` to the existing
   `v0.8.10` Release.
3. Withdraw aarch64 0.8.9, submit aarch64 0.8.10, verify its Parse Result, and
   confirm.