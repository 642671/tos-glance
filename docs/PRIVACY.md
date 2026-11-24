# Privacy Policy — Glance for TOS 7

Last updated: 2026-11-24
Applies to: TOS package `glance` 0.8.10 and later builds of this repository
Bundled upstream: Glance `v0.8.8`

This policy describes how the TOS 7 packaging of **Glance** (`glance`) handles information. The application is installed and runs on the user's own TerraMaster NAS. The packager of this TOS wrapper does not operate a cloud account service for the app and does not receive a copy of data created by a local installation.

## Who provides the application

This package is a TOS 7 wrapper around the official [Glance](https://github.com/glanceapp/glance) dashboard (AGPL-3.0). The wrapper is published by the independent publisher **qishiyi** through [github.com/642671/tos-glance](https://github.com/642671/tos-glance). This is not a TerraMaster official application. Questions about this wrapper's policy can be opened as issues on the wrapper repository.

## What the application does

Glance renders a local homepage dashboard — calendar, clock, weather, bookmarks, RSS feeds, Hacker News, Lobsters and GitHub releases in the shipped default configuration. The official Glance binary listens only on the NAS loopback interface. A small Python wrapper starts it and exposes it to the TOS portal through `/var/api/glance.sock` and an nginx route under `/glance/`.

## What the application accesses

- **Dashboard configuration** — `data/glance.yml`, seeded from `conf/glance.yml`, containing the pages, columns and widgets the administrator chooses.
- **Widget responses** — content fetched by the widgets listed below, cached locally so the dashboard renders quickly.
- **Application state** — Glance's local cache and working files, plus wrapper logs used to start, stop and troubleshoot the service.
- **Nothing from the TOS account system.** The wrapper does not read TOS usernames, passwords, sessions, or files outside its own application directory.

The application does not ask for an account with the publisher and does not collect personal identifiers.

## Where data is stored

All data stays on the NAS:

| Path | Contents |
| --- | --- |
| `/usr/local/glance/data/glance.yml` | active dashboard configuration (seeded from `conf/glance.yml`) |
| `/usr/local/glance/data/` | Glance cache and widget working files |
| `/usr/local/glance/logs/` | wrapper and service logs |
| `/usr/local/glance/docs/PRIVACY.md` | this policy, shipped with the package |

When TOS installs the app through `/Volume1/@apps/glance`, `/usr/local/glance` is a link to that application directory. Logs are not rotated or expired by the package; the administrator can delete them at any time.

## Network requests made from this NAS

The packaged default dashboard already contains widgets that fetch content from the public internet. Each request goes directly from the NAS to the destination below. The wrapper publisher does not operate these endpoints, does not proxy the traffic, and does not receive a copy.

| Widget in the shipped default config | Destination |
| --- | --- |
| weather (Shanghai) | the public weather service used by Glance (Open-Meteo geocoding and forecast APIs) |
| rss | `https://selfh.st/rss/` and `https://github.com/glanceapp/glance/releases.atom` |
| hacker-news | the Hacker News API |
| lobsters | the Lobsters API |
| releases | the GitHub API for `glanceapp/glance`, `gtsteffaniak/filebrowser` and `syncthing/syncthing` |
| bookmarks | nothing until the user clicks a link |

These requests carry the NAS network address and standard HTTP metadata such as the user agent and requested URL. They do not carry dashboard contents to the publisher. Removing or editing the corresponding widgets in `data/glance.yml` makes the dashboard local-only again.

The wrapper itself adds no analytics, update check, or telemetry channel, and it does not send dashboard contents, configuration, or logs to the publisher.

## Third-party components

| Component | Version | License | Role |
| --- | --- | --- | --- |
| Glance (upstream) | `v0.8.8` | AGPL-3.0 | dashboard binary and frontend, unmodified official release asset |
| Python wrapper | 3.10+ standard library | PSF License | service launcher, socket proxy, lifecycle scripts |
| systemd, nginx, `/var/api` socket | platform-provided by TOS | TerraMaster | service supervision, portal route, platform proxy |

The bundled binary is downloaded by the build script from the official release, checked against a fixed SHA-256, and shipped unchanged. `BUILD_PROVENANCE.md` and `NOTICE` in the package record the origin and checksums.

## Permissions and system access

| Capability | Purpose |
| --- | --- |
| Read and write `/usr/local/glance/data` and `/usr/local/glance/logs` | configuration, cache, and logs |
| Create and remove `/var/api/glance.sock` | platform proxy access |
| Listen on `127.0.0.1:18741` | loopback HTTP for the local proxy |
| Outbound HTTP/HTTPS to the widget destinations listed above | render the default dashboard widgets |
| Install an nginx route under `/glance/` | expose the dashboard on the portal origin |

The service runs as the dedicated user `glance` with `ProtectSystem=strict` and `NoNewPrivileges=true`; it does not run as root and does not open a LAN port.

## Retention and uninstall

Configuration, cache and logs remain on the NAS until the administrator edits or deletes them, or uninstalls the package.

Uninstalling stops and disables the service and removes this application's own files: the resolved application directory (normally `/Volume<N>/@apps/glance`, reached through `/usr/local/glance`), the `data` configuration and cache, `logs`, the extracted WebUI, the systemd unit, `/var/api/glance.sock`, the nginx route `/glance/`, and the `glance` service user and group.

Uninstall does **not** delete unrelated user files on shared volumes, other applications' data under `@apps`, or `/var/api` itself. Backups and snapshots created by the user or by other NAS features are outside this package and are not removed by it.

## Security

Glance listens only on the loopback interface. TOS reaches it through the local Unix socket `/var/api/glance.sock`, and the systemd unit runs as the dedicated `glance` service user with sandbox restrictions. Access to the dashboard is therefore governed by TOS sign-in and the permissions of the NAS account. Administrators should protect their TOS credentials, keep TOS and Glance updated, and review custom widget URLs before saving configuration that contains secrets.

## International transfers

The wrapper does not transfer dashboard data internationally on its own. The default widgets listed above contact services that may process requests outside the user's country under their own policies. Removing those widgets keeps all processing on the NAS.

## Children

The application is intended for NAS administration and general dashboard use. It is not directed to children, and the wrapper does not knowingly collect personal information from children.

## Contact

Privacy questions about this wrapper can be opened as issues at https://github.com/642671/tos-glance/issues. This is an independent packaging project and is not a TerraMaster official application.

## Changes

The current policy for a given package version is the copy shipped in that package at `/usr/local/glance/docs/PRIVACY.md`, also published at [docs/PRIVACY.md](https://github.com/642671/tos-glance/blob/main/docs/PRIVACY.md). Material changes are made in a new package version and noted in its release notes.