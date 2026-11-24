# Build provenance

This package contains prebuilt Linux executables from the upstream Glance
project. They are not compiled by this wrapper at package build time and are
not modified after download.

| Item | Value |
| --- | --- |
| Upstream project | https://github.com/glanceapp/glance |
| Upstream release tag | `v0.8.8` |
| Upstream commit | `53aec7f392ca72143870dcb45526ec7c80a68f32` |
| Upstream source archive | https://github.com/glanceapp/glance/archive/refs/tags/v0.8.8.tar.gz |
| Upstream release workflow | https://github.com/glanceapp/glance/blob/v0.8.8/.github/workflows/release.yaml |
| Upstream license | GNU Affero General Public License v3.0 |
| TOS wrapper package version | `0.8.11` |

## Downloaded assets

| Platform | Upstream asset | SHA-256 |
| --- | --- | --- |
| x86_64 | `glance-linux-amd64.tar.gz` | `396b1ee30337afd5cac8d2e744dd449674d9691156536363096c1b92d96b291b` |
| aarch64 | `glance-linux-arm64.tar.gz` | `3aee9fee61b9c5ce9a2b68f415db0806a5e0096e335d0bb4f1fee064932d2124` |

The upstream release workflow runs GoReleaser to produce the Linux archives.
`build.py` downloads these exact release archives, verifies the SHA-256 values
above, and extracts the unchanged `glance` member to
`/usr/local/glance/bin/glance`.

This repository contributes only the TOS 7 wrapper: configuration, systemd
unit, Unix-socket proxy, lifecycle scripts, the TOS `webui.bz2` launcher page,
tests, and build tooling.

## Reproduce a package

```bash
cd apps/tos7
python3 build.py --platform x86_64 --twice
python3 build.py --platform aarch64 --twice
```

The build fails if either upstream download does not match the recorded
SHA-256, and writes a `.sha256` sidecar next to every generated `.deb`.
