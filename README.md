# Glance for TOS 7

This is a **TerraMaster TOS 7 packaging wrapper** for the official
[Glance](https://github.com/glanceapp/glance) dashboard (AGPL-3.0).

It is not the upstream Glance project. The official Linux `x86_64` and
`aarch64` binaries from the Glance v0.8.8 release are packaged unchanged.
Copyright in Glance remains with the upstream authors. This repository only
adds TOS 7 Deb packaging, a local Unix-socket reverse proxy, systemd units,
and a default configuration.

- Upstream: https://github.com/glanceapp/glance
- Upstream tag: `v0.8.8`
- Corresponding source: https://github.com/glanceapp/glance/archive/refs/tags/v0.8.8.tar.gz
- License: [AGPL-3.0](LICENSE) (upstream binary and this packaging)
- Attribution: see [NOTICE](NOTICE)

## What the TOS app does

The application is a TOS 7 iframe Deb (`kind=deb`, not Docker). The official
Glance binary listens on `127.0.0.1` only. A thin Python 3.10+ standard-library
proxy exposes it to the TOS portal through `/var/api/glance.sock` so the
service is not published on a LAN port.

The packaged application id is `glance`. Separate packages are built for
`x86_64` and `aarch64`.

On first start, the default dashboard from `apps/tos7/conf/glance.yml` is
copied to `/usr/local/glance/data/glance.yml` if that file does not already
exist. Later upgrades do not overwrite a customized config.

## Build

Requirements: Python 3.10+ (the build uses only the standard library).
Network access is needed once to download the official Glance release assets;
SHA-256 sums are verified before packaging.

```bash
cd apps/tos7
python3 build.py --platform x86_64 --twice
python3 build.py --platform aarch64 --twice
```

`--twice` builds the package two times and fails if the `.deb` bytes differ.
The builder also writes a `.sha256` sidecar and, when `dpkg-deb` is available,
runs `dpkg-deb --info` and `dpkg-deb --contents`.

Output:

- `apps/tos7/dist/glance_0.8.8_x86_64.deb`
- `apps/tos7/dist/glance_0.8.8_aarch64.deb`

Build directories, downloaded upstream binaries, and `.deb` files are gitignored
and must not be committed.

## Upstream assets (v0.8.8)

| Platform | Official asset | SHA-256 |
| --- | --- | --- |
| x86_64 | [glance-linux-amd64.tar.gz](https://github.com/glanceapp/glance/releases/download/v0.8.8/glance-linux-amd64.tar.gz) | `396b1ee30337afd5cac8d2e744dd449674d9691156536363096c1b92d96b291b` |
| aarch64 | [glance-linux-arm64.tar.gz](https://github.com/glanceapp/glance/releases/download/v0.8.8/glance-linux-arm64.tar.gz) | `3aee9fee61b9c5ce9a2b68f415db0806a5e0096e335d0bb4f1fee064932d2124` |

## License

Glance and this packaging are licensed under the GNU Affero General Public
License v3.0. You must preserve the license and notices when redistributing.
If you modify Glance itself, you must also release the corresponding source
under AGPL-3.0. This wrapper does not modify the official Glance binary.
