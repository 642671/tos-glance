# Privacy Policy — Glance for TOS 7

This policy describes how the TOS 7 packaging of **Glance** (`glance`) handles information. The application is installed and runs on the user's own TerraMaster NAS. The packager of this TOS wrapper does not operate a cloud account service for the app and does not receive a copy of data created by a local installation.

## Who provides the application

This package is a TOS 7 wrapper around the official [Glance](https://github.com/glanceapp/glance) dashboard (AGPL-3.0). The wrapper is published by the independent publisher **qishiyi** through [github.com/642671/tos-glance](https://github.com/642671/tos-glance). This is not a TerraMaster official application. No company legal department or formal postal privacy contact is claimed here. Questions about this wrapper's policy can be opened as issues on the wrapper repository.

## What the application does

Glance shows a local homepage dashboard (for example calendar, bookmarks, and widgets) in a TOS window. The official Glance binary listens only on the NAS loopback interface. A local proxy exposes it to the TOS portal through `/var/api/glance.sock`.

## Information stored on this NAS

The wrapper and Glance may store configuration and working files only on this NAS, typically under `/usr/local/glance/data` and `/usr/local/glance/logs`, including:

- the dashboard configuration, such as `/usr/local/glance/data/glance.yml`
- cache or widget working files created by Glance
- service logs and install diagnostic files

The application does not require you to create an account with the wrapper publisher.

## Network requests made from this NAS

Some Glance widgets can fetch information from locations the NAS administrator configures, such as public RSS feeds, calendars, or other widget endpoints. Those requests go directly from this NAS to the destinations set in the dashboard configuration. This wrapper does not insert a publisher analytics channel into those requests, and it does not receive a copy of that traffic.

If you do not add widgets that contact external sites, Glance stays a local dashboard. The wrapper does not send dashboard contents, configuration, or logs to the publisher.

## Access on this NAS

Anyone who can sign in to TOS and open the application can see the dashboard configured on that NAS.

## Sharing and third parties

The wrapper publisher does not sell dashboard data, share it with advertisers, or operate a remote account service for the application. Data is shared with a third party only when the NAS administrator configures a widget or link that sends a request to that third party, or when the administrator deliberately exports or publishes information from the dashboard.

## Security

Glance listens only on the loopback interface. TOS reaches it through the local Unix socket `/var/api/glance.sock`, and the systemd unit runs as the dedicated `glance` service user with sandbox restrictions. Access to the dashboard is therefore governed by TOS sign-in and the permissions of the NAS account. Administrators should protect their TOS credentials, keep TOS and Glance updated, and review custom widget URLs before saving configuration that contains secrets.

## International transfers

The wrapper does not transfer dashboard data internationally on its own. If a configured widget contacts an external service, that request may leave the NAS and may be processed in another country under that service's own policy.

## Children

The application is intended for NAS administration and general dashboard use. It is not directed to children, and the wrapper does not knowingly collect personal information from children.

## Retention and uninstall

Configuration remains on the NAS until the user changes or deletes it, or uninstalls the application. Uninstalling the package stops the service and removes this application's own configuration, cache, logs, Unix socket, systemd unit, and service user. When TOS exposes the app through `/usr/local/glance`, the package also removes the exact app-owned `/Volume1/@apps/glance` target if that is the symlink destination. It does not delete unrelated user files on shared storage volumes.

## Contact

Privacy questions about this wrapper can be opened as issues at https://github.com/642671/tos-glance/issues. This is an independent packaging project and is not a TerraMaster official application.

## Changes

The current policy for a given package version is the copy shipped in that package at `/usr/local/glance/docs/PRIVACY.md`, also published at [docs/PRIVACY.md](https://github.com/642671/tos-glance/blob/main/docs/PRIVACY.md).
