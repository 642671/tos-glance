#!/usr/bin/env python3
"""Build a deterministic TOS 7 iframe Deb around an official upstream binary."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parent
APP_ID = "glance"
APP_USER = "glance"
SYSTEM_ID = "glance-system"
PACKAGE_VERSION = "0.8.8"
UPSTREAM_TAG = "v0.8.8"
UPSTREAM_BIN_NAME = "glance"
DEFAULT_CONF_NAME = "glance.yml"
PLATFORM_ARCH = {"x86_64": "amd64", "aarch64": "arm64"}
EXECUTABLE_NAMES = {
    "glance-service",
    "glance",
    "postinst",
    "prerm",
    "postrm",
}
UPSTREAM = {
    "x86_64": {
        "url": "https://github.com/glanceapp/glance/releases/download/v0.8.8/glance-linux-amd64.tar.gz",
        "sha256": "396b1ee30337afd5cac8d2e744dd449674d9691156536363096c1b92d96b291b",
        "kind": "tar_member",
        "member": "glance",
    },
    "aarch64": {
        "url": "https://github.com/glanceapp/glance/releases/download/v0.8.8/glance-linux-arm64.tar.gz",
        "sha256": "3aee9fee61b9c5ce9a2b68f415db0806a5e0096e335d0bb4f1fee064932d2124",
        "kind": "tar_member",
        "member": "glance",
    },
}

REQUIRED_LANGUAGES = {
    "zh-cn",
    "zh-hk",
    "en-us",
    "fr-fr",
    "de-de",
    "it-it",
    "es-es",
    "hu-hu",
    "ja-jp",
    "ko-kr",
    "pl-pl",
    "ru-ru",
    "tr-tr",
    "pt-pt",
}
REQUIRED_LANG_FIELDS = {"name", "auth", "descript"}
MTIME = 1_704_067_200
ICON_MTIME_EPOCH = 1_792_627_200


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def read_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", version):
        raise SystemExit("version must contain 1 to 3 numeric segments")
    if version != PACKAGE_VERSION:
        raise SystemExit(
            f"VERSION file is {version!r}, expected {PACKAGE_VERSION!r}"
        )
    return version


def validate_config(config: dict, version: str) -> None:
    required = {
        "id",
        "icon",
        "publisher",
        "exec",
        "version",
        "low_version",
        "category",
        "platform",
        "user",
        "system_id",
        "package",
        "application_type",
        "path",
        "type",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("config.ini is missing fields: " + ", ".join(missing))
    checks = {
        "id": APP_ID,
        "system_id": SYSTEM_ID,
        "package": APP_ID,
        "application_type": "deb",
        "type": "iframe",
        "path": f"/{APP_ID}/",
        "version": version,
        "user": APP_USER,
        "icon": f"/images/icons/{APP_ID}.svg",
    }
    for field, expected in checks.items():
        if config.get(field) != expected:
            raise SystemExit(
                f"config.ini {field} must be {expected!r}, got {config.get(field)!r}"
            )
    if "open_path" in config:
        raise SystemExit("config.ini must not contain open_path with type=iframe")
    if config.get("platform") not in PLATFORM_ARCH:
        raise SystemExit("config.ini platform must be x86_64 or aarch64")


def validate_language(path: Path) -> None:
    import configparser

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    sections = set(parser.sections())
    if sections != REQUIRED_LANGUAGES:
        raise SystemExit(
            "language sections do not match the TOS 14-language set: "
            f"missing={sorted(REQUIRED_LANGUAGES - sections)}, "
            f"extra={sorted(sections - REQUIRED_LANGUAGES)}"
        )
    for section in REQUIRED_LANGUAGES:
        for field in REQUIRED_LANG_FIELDS:
            if not parser[section].get(field, "").strip():
                raise SystemExit(f"language section {section} is missing {field}")


def validate_icon(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"icon not found: {path}")
    raw = path.read_bytes()
    if len(raw) > 50 * 1024:
        raise SystemExit("icon must be at most 50 KB")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SystemExit(f"icon is not valid SVG/XML: {exc}") from exc
    forbidden_tags = {"script", "foreignobject", "iframe", "object", "embed"}
    forbidden_prefixes = ("javascript:", "vbscript:", "file:", "ftp:", "about:", "blob:")
    count = 0
    for element in root.iter():
        count += 1
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag in forbidden_tags:
            raise SystemExit(f"icon contains forbidden tag: {tag}")
        for name, value in element.attrib.items():
            if name.lower().startswith("on"):
                raise SystemExit(f"icon contains event attribute: {name}")
            if name.lower().endswith("href") and str(value).lower().startswith(
                forbidden_prefixes
            ):
                raise SystemExit(f"icon contains unsafe href: {value}")
    if count > 50:
        raise SystemExit("icon contains too many XML elements")


def normalize_lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def make_tar_bytes(
    entries: Iterable[tuple[Path, str]],
    content_overrides: Mapping[str, bytes] | None = None,
    mtime_overrides: Mapping[str, int] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    text_suffixes = {
        ".css",
        ".env",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".lang",
        ".md",
        ".py",
        ".service",
        ".sh",
        ".txt",
        ".yml",
        ".yaml",
    }
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for source, archive_name in entries:
            if not source.exists():
                raise SystemExit(f"staging entry does not exist: {source}")
            info = archive.gettarinfo(str(source), arcname=archive_name)
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = (
                mtime_overrides.get(archive_name, MTIME)
                if mtime_overrides is not None
                else MTIME
            )
            if info.isdir():
                info.mode = 0o755
                archive.addfile(info)
                continue
            if info.isfile():
                info.mode = 0o755 if source.name in EXECUTABLE_NAMES else 0o644
                override = (
                    content_overrides.get(archive_name)
                    if content_overrides is not None
                    else None
                )
                if override is not None:
                    data = override
                elif source.suffix.lower() in text_suffixes:
                    data = normalize_lf(source)
                else:
                    data = source.read_bytes()
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            else:
                archive.addfile(info)
    return buffer.getvalue()


def make_tar_gz(
    entries: Iterable[tuple[Path, str]],
    mtime_overrides: Mapping[str, int] | None = None,
) -> bytes:
    return gzip.compress(
        make_tar_bytes(entries, mtime_overrides=mtime_overrides),
        compresslevel=9,
        mtime=0,
    )


def release_icon_mtime(version: str) -> int:
    version_offset = int("".join(re.findall(r"\d+", version)) or "0")
    return ICON_MTIME_EPOCH + version_offset


def write_ar(path: Path, members: list[tuple[str, bytes]]) -> None:
    with path.open("wb") as output:
        output.write(b"!<arch>\n")
        for name, data in members:
            encoded_name = name.encode("ascii")
            if len(encoded_name) > 16:
                raise SystemExit(f"ar member name is too long: {name}")
            header = (
                encoded_name.ljust(16, b" ")
                + b"0".ljust(12, b" ")
                + b"0".ljust(6, b" ")
                + b"0".ljust(6, b" ")
                + b"100644".ljust(8, b" ")
                + str(len(data)).encode("ascii").ljust(10, b" ")
                + b"`\n"
            )
            output.write(header)
            output.write(data)
            if len(data) % 2:
                output.write(b"\n")


def read_ar(path: Path) -> dict[str, bytes]:
    raw = path.read_bytes()
    if not raw.startswith(b"!<arch>\n"):
        raise SystemExit(f"{path} is not an ar archive")
    members: dict[str, bytes] = {}
    offset = 8
    while offset < len(raw):
        header = raw[offset : offset + 60]
        if len(header) != 60 or header[58:60] != b"`\n":
            raise SystemExit("invalid ar member header")
        name = header[0:16].decode("ascii").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        data_start = offset + 60
        data_end = data_start + size
        members[name] = raw[data_start:data_end]
        offset = data_end + (size % 2)
    return members


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_upstream(platform: str) -> Path:
    spec = UPSTREAM[platform]
    cache = ROOT / "build" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    filename = Path(spec["url"]).name
    dest = cache / filename
    if dest.is_file() and sha256_file(dest) == spec["sha256"]:
        return dest
    log = f"downloading {spec['url']}"
    print(log)
    # Token-free official GitHub download.
    request = urllib.request.Request(
        spec["url"],
        headers={"User-Agent": "tos-packaging-builder"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != spec["sha256"]:
        raise SystemExit(
            f"SHA-256 mismatch for {filename}: got {digest}, expected {spec['sha256']}"
        )
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def extract_upstream_binary(archive: Path, platform: str, dest: Path) -> None:
    spec = UPSTREAM[platform]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if spec["kind"] == "tar_member":
        with tarfile.open(archive, mode="r:gz") as tar:
            try:
                member = tar.getmember(spec["member"])
            except KeyError as exc:
                raise SystemExit(
                    f"{archive.name} is missing member {spec['member']}"
                ) from exc
            extracted = tar.extractfile(member)
            if extracted is None:
                raise SystemExit(f"cannot extract {spec['member']} from {archive}")
            dest.write_bytes(extracted.read())
    elif spec["kind"] == "binary":
        dest.write_bytes(archive.read_bytes())
    else:
        raise SystemExit(f"unknown upstream kind: {spec['kind']}")
    dest.chmod(0o755)
    if dest.stat().st_size < 1024:
        raise SystemExit(f"upstream binary looks too small: {dest}")


def verify_package(path: Path, platform: str, version: str) -> None:
    members = read_ar(path)
    if set(members) != {"debian-binary", "control.tar.gz", "data.tar.gz"}:
        raise SystemExit(f"unexpected deb members: {sorted(members)}")
    if members["debian-binary"] != b"2.0\n":
        raise SystemExit("debian-binary must contain 2.0")

    with tarfile.open(
        fileobj=io.BytesIO(members["control.tar.gz"]), mode="r:gz"
    ) as control:
        names = {member.name for member in control.getmembers()}
        expected = {"./control", "./md5sums", "./postinst", "./prerm", "./postrm"}
        if not expected.issubset(names):
            raise SystemExit("control tar is missing lifecycle files")
        control_file = control.extractfile("./control")
        if control_file is None:
            raise SystemExit("control file cannot be read")
        control_text = control_file.read().decode("utf-8")
        if f"Version: {version}" not in control_text:
            raise SystemExit("control version mismatch")
        if f"Architecture: {PLATFORM_ARCH[platform]}" not in control_text:
            raise SystemExit("control architecture mismatch")
        for script_name in ("./postinst", "./prerm", "./postrm"):
            if not control.getmember(script_name).mode & 0o111:
                raise SystemExit(f"{script_name} is not executable")

    with tarfile.open(
        fileobj=io.BytesIO(members["data.tar.gz"]), mode="r:gz"
    ) as data:
        data_names = {member.name for member in data.getmembers()}
        required = {
            f"./usr/local/{APP_ID}/config.ini",
            f"./usr/local/{APP_ID}/{APP_ID}.lang",
            f"./usr/local/{APP_ID}/{APP_ID}.env",
            f"./usr/local/{APP_ID}/LICENSE",
            f"./usr/local/{APP_ID}/NOTICE",
            f"./usr/local/{APP_ID}/bin/{APP_ID}-service",
            f"./usr/local/{APP_ID}/bin/{UPSTREAM_BIN_NAME}",
            f"./usr/local/{APP_ID}/lib/tos_unix_proxy.py",
            f"./usr/local/{APP_ID}/images/icons/{APP_ID}.svg",
            f"./usr/local/{APP_ID}/init.d/{SYSTEM_ID}.service",
            f"./usr/local/{APP_ID}/conf/{DEFAULT_CONF_NAME}",
        }
        missing = required - data_names
        if missing:
            raise SystemExit("data tar is missing: " + ", ".join(sorted(missing)))
        config_file = data.extractfile(f"./usr/local/{APP_ID}/config.ini")
        if config_file is None:
            raise SystemExit("packaged config.ini cannot be read")
        packaged = json.loads(config_file.read().decode("utf-8"))
        if packaged.get("platform") != platform or packaged.get("version") != version:
            raise SystemExit("packaged config platform/version mismatch")
        for name in (f"{APP_ID}-service", UPSTREAM_BIN_NAME):
            entry = data.getmember(f"./usr/local/{APP_ID}/bin/{name}")
            if not entry.mode & 0o111:
                raise SystemExit(f"{name} is not executable")
        icon = data.getmember(f"./usr/local/{APP_ID}/images/icons/{APP_ID}.svg")
        if icon.mtime != release_icon_mtime(version):
            raise SystemExit("icon modification time was not version-busted")


def run_dpkg_inspection(path: Path) -> None:
    dpkg = shutil.which("dpkg-deb")
    if not dpkg:
        print("dpkg-deb not found; skipped --info/--contents inspection")
        return
    info = subprocess.check_output([dpkg, "--info", str(path)], text=True)
    contents = subprocess.check_output([dpkg, "--contents", str(path)], text=True)
    if f"Package: {APP_ID}" not in info:
        raise SystemExit("dpkg-deb --info is missing the package name")
    if f"Version: {PACKAGE_VERSION}" not in info:
        raise SystemExit("dpkg-deb --info is missing the package version")
    if f"./usr/local/{APP_ID}/bin/{UPSTREAM_BIN_NAME}" not in contents:
        raise SystemExit("dpkg-deb --contents is missing the upstream binary")
    print("dpkg-deb --info/--contents: OK")


def add_tree(entries: list[tuple[Path, str]], root: Path, arcroot: str) -> None:
    entries.append((root, arcroot))
    for path in sorted(root.rglob("*")):
        relative = "./" + path.relative_to(root).as_posix()
        entries.append((path, f"{arcroot.rstrip('/')}/{relative[2:]}"))


def build(platform: str, clean: bool) -> Path:
    if platform not in PLATFORM_ARCH:
        raise SystemExit("platform must be x86_64 or aarch64")
    version = read_version()
    config = read_json(ROOT / "config.ini")
    validate_config(config, version)
    validate_language(ROOT / f"{APP_ID}.lang")
    validate_icon(ROOT / "images" / "icons" / f"{APP_ID}.svg")

    build_dir = ROOT / "build" / platform
    staging = build_dir / "staging"
    output_dir = ROOT / "dist"
    if clean and build_dir.exists():
        # Keep the shared download cache.
        for child in build_dir.iterdir():
            if child.name == "cache":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    if staging.exists():
        shutil.rmtree(staging)
    package_root = staging / "usr" / "local" / APP_ID
    for directory in (
        staging / "DEBIAN",
        package_root / "bin",
        package_root / "lib",
        package_root / "conf",
        package_root / "images" / "icons",
        package_root / "init.d",
        package_root / "data",
        package_root / "logs",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    staged_config = dict(config)
    staged_config["platform"] = platform
    (package_root / "config.ini").write_text(
        json.dumps(staged_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copy2(ROOT / f"{APP_ID}.lang", package_root / f"{APP_ID}.lang")
    shutil.copy2(ROOT / f"{APP_ID}.env", package_root / f"{APP_ID}.env")
    shutil.copy2(ROOT / "LICENSE", package_root / "LICENSE")
    shutil.copy2(ROOT / "NOTICE", package_root / "NOTICE")
    shutil.copy2(
        ROOT / "images" / "icons" / f"{APP_ID}.svg",
        package_root / "images" / "icons" / f"{APP_ID}.svg",
    )
    shutil.copy2(
        ROOT / "init.d" / f"{SYSTEM_ID}.service",
        package_root / "init.d" / f"{SYSTEM_ID}.service",
    )
    shutil.copy2(
        ROOT / "backend" / f"{APP_ID}-service",
        package_root / "bin" / f"{APP_ID}-service",
    )
    shutil.copy2(
        ROOT / "backend" / "tos_unix_proxy.py",
        package_root / "lib" / "tos_unix_proxy.py",
    )
    shutil.copy2(
        ROOT / "conf" / DEFAULT_CONF_NAME,
        package_root / "conf" / DEFAULT_CONF_NAME,
    )

    upstream_archive = fetch_upstream(platform)
    extract_upstream_binary(
        upstream_archive,
        platform,
        package_root / "bin" / UPSTREAM_BIN_NAME,
    )

    for script_name in ("control", "postinst", "prerm", "postrm"):
        shutil.copy2(ROOT / "DEBIAN" / script_name, staging / "DEBIAN" / script_name)
    control_path = staging / "DEBIAN" / "control"
    control_text = control_path.read_text(encoding="utf-8")
    control_text = re.sub(
        r"^Version:.*$", f"Version: {version}", control_text, flags=re.MULTILINE
    )
    control_text = re.sub(
        r"^Architecture:.*$",
        f"Architecture: {PLATFORM_ARCH[platform]}",
        control_text,
        flags=re.MULTILINE,
    )
    control_path.write_text(control_text, encoding="utf-8", newline="\n")

    data_entries: list[tuple[Path, str]] = []
    add_tree(data_entries, staging / "usr", "./usr")
    checksums: list[str] = []
    for path in sorted((staging / "usr").rglob("*")):
        if path.is_file():
            relative = path.relative_to(staging).as_posix()
            digest = hashlib.md5(path.read_bytes()).hexdigest()
            checksums.append(f"{digest}  {relative}\n")
    (staging / "DEBIAN" / "md5sums").write_text(
        "".join(checksums),
        encoding="ascii",
        newline="\n",
    )

    control_entries = [
        (staging / "DEBIAN" / name, f"./{name}")
        for name in ("control", "md5sums", "postinst", "prerm", "postrm")
    ]
    icon_archive_name = f"./usr/local/{APP_ID}/images/icons/{APP_ID}.svg"
    archive_path = output_dir / f"{APP_ID}_{version}_{platform}.deb"
    write_ar(
        archive_path,
        [
            ("debian-binary", b"2.0\n"),
            ("control.tar.gz", make_tar_gz(control_entries)),
            (
                "data.tar.gz",
                make_tar_gz(
                    data_entries,
                    {icon_archive_name: release_icon_mtime(version)},
                ),
            ),
        ],
    )
    verify_package(archive_path, platform, version)
    run_dpkg_inspection(archive_path)
    checksum = sha256_file(archive_path)
    (output_dir / f"{archive_path.name}.sha256").write_text(
        f"{checksum}  {archive_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    print(f"Built: {archive_path}")
    print("Verification: OK")
    print(f"SHA256: {checksum}")
    print(f"Size: {archive_path.stat().st_size} bytes")
    return archive_path


def build_twice(platform: str) -> Path:
    first = build(platform, clean=True)
    first_bytes = first.read_bytes()
    first_hash = hashlib.sha256(first_bytes).hexdigest()
    backup = first.with_suffix(first.suffix + ".first")
    backup.write_bytes(first_bytes)
    second = build(platform, clean=True)
    second_bytes = second.read_bytes()
    second_hash = hashlib.sha256(second_bytes).hexdigest()
    if first_bytes != second_bytes:
        raise SystemExit(
            "consecutive builds produced different .deb bytes: "
            f"{first_hash} vs {second_hash}"
        )
    backup.unlink(missing_ok=True)
    print("Consecutive builds are byte-identical.")
    return second


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Build the {APP_ID} TOS 7 package")
    parser.add_argument(
        "--platform",
        choices=sorted(PLATFORM_ARCH),
        default="x86_64",
        help="target platform",
    )
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument(
        "--twice",
        action="store_true",
        help="build twice and require identical .deb bytes",
    )
    args = parser.parse_args()
    if args.twice:
        build_twice(args.platform)
    else:
        build(args.platform, clean=not args.no_clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
