from __future__ import annotations
from functools import partial
from ssl import create_default_context
from urllib.parse import urlparse, parse_qs

from dataclasses import dataclass
from typing import Callable

import trio

@dataclass(frozen=True)
class ConnectInfo:
    socket_connect: Callable
    password: str
    database: int

    @classmethod
    def from_url(cls, url: str, *, ssl_context=None) -> ConnectInfo:
        # Parse URL for settings
        url = urlparse(url if "//" in url else f"//{url}")
        options = parse_qs(url.query)
        database = int(options.get("database", [0])[0])
        if url.username or url.params or url.fragment:
            raise ValueError(f"URL {url} contains unsupported elements")
        schemes = set(url.scheme.split("+")) if url.scheme else set()
        if not schemes <= {"redis", "rediss", "unix", "tls"}:
            raise ValueError(f"Unsupported scheme {url.scheme}")
        # Socket type
        if "unix" in schemes or "redis-socket" in schemes:
            if len(url.path) <= 1:
                raise ValueError(
                    f"Invalid Redis socket path {url.path!r}.\n"
                    "  - Try URL like: redis+unix://localhost/var/run/redis.sock\n"
                )
            if url.port is not None:
                raise ValueError("UNIX socket URL should not contain port")
            socket_connect = partial(trio.open_unix_socket, url.path)
        else:
            if len(url.path) > 1:
                database = int(url.path[1:])
                assert "database" not in options
            socket_connect = partial(
                trio.open_tcp_stream, url.hostname, url.port or 6379)
        # TLS config
        if ssl_context or "rediss" in schemes:
            schemes.add("tls")
        if "tls" in schemes:
            socket_connect = _ssl_wrap(
                socket_connect,
                ssl_context=ssl_context or create_default_context(),
                server_hostname=url.hostname,
            )
        return cls(
            socket_connect=socket_connect,
            password=url.password,
            database=database,
        )

def _ssl_wrap(socket_connect, ssl_context, server_hostname):
    async def ssl_wrapper():
        sock = await socket_connect()
        sock = trio.SSLStream(
            sock,
            ssl_context,
            server_hostname=server_hostname
        )
        await sock.do_handshake()
        return sock
    return ssl_wrapper
