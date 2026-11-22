#!/usr/bin/env python3
"""Thin HTTP/1.1 + WebSocket reverse proxy: Unix socket -> 127.0.0.1:port.

Standard library only. Intended for TOS iframe apps that listen on a local
TCP port while the TOS portal talks to /var/api/<app_id>.sock.
"""

from __future__ import annotations

import argparse
import os
import select
import socket
import socketserver
import sys
import threading
from typing import Iterable
from urllib.parse import urlsplit

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "proxy-connection",
}


def log(level: str, message: str) -> None:
    print(f"[tos-unix-proxy] [{level}] {message}", flush=True)


def prepare_socket(path: str, mode: int = 0o660) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    if os.path.lexists(path):
        try:
            os.unlink(path)
        except OSError as exc:
            raise SystemExit(
                f"{path} exists but cannot be removed: {exc}. "
                "The shared /var/api directory is sticky; a foreign-owned "
                "socket must be removed by its owner or root."
            ) from exc


def rewrite_path(raw_path: str, strip_prefix: str) -> str:
    if not strip_prefix:
        return raw_path
    prefix = strip_prefix if strip_prefix.startswith("/") else "/" + strip_prefix
    prefix = prefix.rstrip("/")
    if raw_path == prefix:
        return "/"
    if raw_path.startswith(prefix + "/"):
        rewritten = raw_path[len(prefix) :]
        return rewritten if rewritten else "/"
    return raw_path


def _read_headers(sock: socket.socket, limit: int = 1024 * 1024) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if len(data) > limit:
            raise OSError("HTTP header block is too large")
    return data


def _split_request(block: bytes) -> tuple[bytes, bytes, bytes, dict[str, str], bytes]:
    header_blob, body = block.split(b"\r\n\r\n", 1)
    lines = header_blob.split(b"\r\n")
    if not lines or not lines[0]:
        raise OSError("empty HTTP request")
    try:
        method, target, version = lines[0].split(b" ", 2)
    except ValueError as exc:
        raise OSError("malformed HTTP request line") from exc
    headers: dict[str, str] = {}
    raw_headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if b":" not in line:
            continue
        name, value = line.split(b":", 1)
        key = name.decode("latin1").strip()
        val = value.decode("latin1").strip()
        headers[key.lower()] = val
        raw_headers.append((key, val))
    # keep last occurrence in headers dict; preserve list separately later
    return method, target, version, headers, body


def _header_list(block: bytes) -> list[tuple[str, str]]:
    header_blob = block.split(b"\r\n\r\n", 1)[0]
    items: list[tuple[str, str]] = []
    for line in header_blob.split(b"\r\n")[1:]:
        if b":" not in line:
            continue
        name, value = line.split(b":", 1)
        items.append((name.decode("latin1").strip(), value.decode("latin1").strip()))
    return items


def _is_hop_by_hop(name: str, connection_value: str) -> bool:
    if name.lower() in HOP_BY_HOP:
        return True
    extra = [part.strip().lower() for part in connection_value.split(",") if part.strip()]
    return name.lower() in extra


def _format_headers(start: bytes, headers: Iterable[tuple[str, str]]) -> bytes:
    parts = [start]
    for name, value in headers:
        parts.append(f"{name}: {value}".encode("latin1"))
    parts.append(b"")
    parts.append(b"")
    return b"\r\n".join(parts)


def _tunnel(left: socket.socket, right: socket.socket) -> None:
    sockets = [left, right]
    try:
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, 60)
            if exceptional:
                break
            if not readable:
                continue
            for src in readable:
                dst = right if src is left else left
                try:
                    data = src.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                try:
                    dst.sendall(data)
                except OSError:
                    return
    finally:
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass


def _copy_chunked(src: socket.socket, dst: socket.socket, initial: bytes) -> None:
    buffer = initial
    while True:
        while b"\r\n" not in buffer:
            chunk = src.recv(4096)
            if not chunk:
                if buffer:
                    dst.sendall(buffer)
                return
            buffer += chunk
        line, buffer = buffer.split(b"\r\n", 1)
        dst.sendall(line + b"\r\n")
        try:
            size = int(line.split(b";", 1)[0].strip() or b"0", 16)
        except ValueError as exc:
            raise OSError("invalid chunk size") from exc
        needed = size + 2  # data + trailing CRLF
        while len(buffer) < needed:
            chunk = src.recv(4096)
            if not chunk:
                dst.sendall(buffer)
                return
            buffer += chunk
        dst.sendall(buffer[:needed])
        buffer = buffer[needed:]
        if size == 0:
            # possible trailers
            if b"\r\n" in buffer:
                dst.sendall(buffer)
            return


def _copy_fixed(src: socket.socket, dst: socket.socket, initial: bytes, length: int) -> None:
    remaining = length
    if initial:
        dst.sendall(initial[:length])
        remaining -= min(len(initial), length)
        initial = initial[length:]
    while remaining > 0:
        chunk = src.recv(min(65536, remaining))
        if not chunk:
            break
        dst.sendall(chunk)
        remaining -= len(chunk)


def _copy_until_close(src: socket.socket, dst: socket.socket, initial: bytes) -> None:
    if initial:
        dst.sendall(initial)
    while True:
        chunk = src.recv(65536)
        if not chunk:
            break
        dst.sendall(chunk)


class ProxyHandler(socketserver.StreamRequestHandler):
    timeout = 60

    def handle(self) -> None:
        client = self.request
        try:
            block = _read_headers(client)
        except OSError as exc:
            log("ERROR", f"failed to read request: {exc}")
            return
        if b"\r\n\r\n" not in block:
            return
        try:
            method, target, version, headers, body = _split_request(block)
        except OSError:
            return

        raw_target = target.decode("latin1")
        if raw_target.startswith("http://") or raw_target.startswith("https://"):
            split = urlsplit(raw_target)
            path = split.path or "/"
            if split.query:
                path = f"{path}?{split.query}"
        else:
            path = raw_target

        new_path = rewrite_path(path, self.server.strip_prefix)
        connection_value = headers.get("connection", "")
        incoming = _header_list(block)
        outgoing: list[tuple[str, str]] = []
        host = f"{self.server.backend_host}:{self.server.backend_port}"
        has_host = False
        for name, value in incoming:
            lower = name.lower()
            if _is_hop_by_hop(name, connection_value):
                continue
            if lower == "host":
                outgoing.append((name, host))
                has_host = True
                continue
            outgoing.append((name, value))
        if not has_host:
            outgoing.append(("Host", host))
        forwarded_for = headers.get("x-forwarded-for")
        peer = "127.0.0.1"
        try:
            peer = self.client_address[0]
        except Exception:
            pass
        if forwarded_for:
            outgoing.append(("X-Forwarded-For", f"{forwarded_for}, {peer}"))
        else:
            outgoing.append(("X-Forwarded-For", peer))
        if "x-forwarded-proto" not in headers:
            outgoing.append(("X-Forwarded-Proto", "http"))
        if "x-forwarded-host" not in {n.lower() for n, _ in incoming}:
            original_host = headers.get("host", host)
            outgoing.append(("X-Forwarded-Host", original_host))

        upgrade = "upgrade" in {part.strip().lower() for part in connection_value.split(",") if part.strip()}
        upgrade_header = headers.get("upgrade", "")
        if upgrade and upgrade_header:
            outgoing.append(("Connection", "upgrade"))
            outgoing.append(("Upgrade", upgrade_header))
        else:
            outgoing.append(("Connection", "close"))

        request_line = b" ".join([method, new_path.encode("latin1"), version])
        payload = _format_headers(request_line, outgoing) + body

        backend = socket.create_connection(
            (self.server.backend_host, self.server.backend_port),
            timeout=30,
        )
        try:
            backend.sendall(payload)
            content_length = headers.get("content-length")
            if (
                method.upper() not in {b"GET", b"HEAD"}
                and content_length
                and len(body) < int(content_length)
            ):
                _copy_fixed(client, backend, b"", int(content_length) - len(body))
            elif headers.get("transfer-encoding", "").lower() == "chunked" and method.upper() not in {b"GET", b"HEAD"}:
                _copy_chunked(client, backend, b"")

            response = _read_headers(backend)
            if b"\r\n\r\n" not in response:
                return
            header_blob, rest = response.split(b"\r\n\r\n", 1)
            status_line = header_blob.split(b"\r\n", 1)[0]
            resp_headers = {}
            for line in header_blob.split(b"\r\n")[1:]:
                if b":" not in line:
                    continue
                name, value = line.split(b":", 1)
                resp_headers[name.decode("latin1").lower()] = value.decode("latin1").strip()
            # Send only the header block here. The already-read body prefix
            # (`rest`) must be forwarded exactly once by the body copier.
            client.sendall(header_blob + b"\r\n\r\n")
            if upgrade and resp_headers.get("upgrade") and "101" in status_line.decode("latin1", "replace"):
                if rest:
                    client.sendall(rest)
                _tunnel(client, backend)
                return
            if resp_headers.get("transfer-encoding", "").lower() == "chunked":
                _copy_chunked(backend, client, rest)
            elif "content-length" in resp_headers:
                length = int(resp_headers["content-length"])
                _copy_fixed(backend, client, rest, length)
            elif method.upper() != b"HEAD":
                _copy_until_close(backend, client, rest)
        finally:
            try:
                backend.close()
            except OSError:
                pass


class ThreadingUnixProxy(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        socket_path: str,
        backend_host: str,
        backend_port: int,
        strip_prefix: str = "",
        socket_mode: int = 0o660,
    ) -> None:
        prepare_socket(socket_path, socket_mode)
        self.backend_host = backend_host
        self.backend_port = backend_port
        self.strip_prefix = strip_prefix.rstrip("/")
        self.socket_path = socket_path
        self.socket_mode = socket_mode
        super().__init__(socket_path, ProxyHandler)
        try:
            os.chmod(socket_path, socket_mode)
        except OSError as exc:
            log("ERROR", f"chmod {socket_path} failed: {exc}")

    def server_close(self) -> None:
        super().server_close()
        if os.path.lexists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass


def serve_proxy(
    socket_path: str,
    backend_host: str,
    backend_port: int,
    strip_prefix: str = "",
    socket_mode: int = 0o660,
) -> int:
    server = ThreadingUnixProxy(
        socket_path,
        backend_host,
        backend_port,
        strip_prefix=strip_prefix,
        socket_mode=socket_mode,
    )
    log(
        "INFO",
        f"proxying {socket_path} -> {backend_host}:{backend_port} "
        f"strip_prefix={strip_prefix or '-'}",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unix socket HTTP reverse proxy")
    parser.add_argument("--socket", required=True, help="path of the listening Unix socket")
    parser.add_argument("--backend-host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--strip-prefix", default="", help="URL prefix to strip, e.g. /glance")
    parser.add_argument("--socket-mode", default="660")
    args = parser.parse_args(argv)
    mode = int(args.socket_mode, 8) if str(args.socket_mode).startswith("0") or len(str(args.socket_mode)) == 3 else int(args.socket_mode)
    return serve_proxy(
        args.socket,
        args.backend_host,
        args.backend_port,
        strip_prefix=args.strip_prefix,
        socket_mode=mode,
    )


if __name__ == "__main__":
    raise SystemExit(main())
