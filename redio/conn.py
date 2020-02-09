from functools import partial
from ssl import create_default_context
from urllib.parse import urlparse, parse_qs

import trio

from redio.protocol import Protocol
from redio.exc import ProtocolError, RedisError


class Connection(Protocol):
    def __init__(self, url="redis://localhost/", *, ssl_context=None, connection_commands=[]):
        super().__init__()
        # Parse URL for settings
        url = urlparse(url if "//" in url else f"//{url}")
        options = parse_qs(url.query)
        self.server_hostname = url.hostname
        if url.username or url.params or url.fragment:
            raise ValueError(f"URL {url} contains unsupported elements")
        schemes = set(url.scheme.split("+")) if url.scheme else set()
        if not schemes <= frozenset(["redis", "unix", "tls"]):
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
            self._connect = partial(trio.open_unix_socket, url.path)
        else:
            if len(url.path) > 1:
                self.db = int(url.path[1:])
            self._connect = partial(trio.open_tcp_stream, url.hostname, url.port or 6379)
        # TLS config
        if ssl_context or "rediss" in schemes: schemes.add("tls")
        self.ssl = ssl_context or create_default_context() if "tls" in schemes else None
        # Connection commands
        commands = []
        if url.password:
            commands += (b"AUTH", url.encode())
        if "database" in options:
            commands += (b"SELECT", b"%d" % options["database"]),
        self.connection_commands = [*commands, *connection_commands]
        self.sock = None

    def __bool__(self):
        return self.sock is not None

    async def connect(self):
        """Make server connection.

        This must only be called once after Protocol object construction.
        """
        # Connect to server
        sock = await self._connect()
        # Upgrade to TLS if needed
        if self.ssl:
            sock = trio.SSLStream(sock, self.ssl, server_hostname=self.server_hostname)
            await sock.do_handshake()
        # Authenticate and choose database
        self.sock = sock
        self.receiver = self.sock.receive_some
        del self._connect  # Prevent reconnection because we don't reset protocol
        if self.connection_commands:
            cmds = self.connection_commands
            for cmd, res in zip(cmds, await self.run(cmds)):
                if res != "OK":
                    raise RedisError(f"Connection command {cmd[0].decode()} returned {res}")
        return self

    async def aclose(self):
        """Close connection. Connection objects may not be reconnected afterwards."""
        if self.sock is not None:
            await self.sock.aclose()
            self.sock = None

    async def run(self, commands):
        """Run a set of commands and return responses.

        Uses pipelining but no transactions. Each command must return exactly
        one response. For commands where this is not true, Protocol must be
        accessed directly.
        """
        try:
            for cmd in commands:
                self.command(cmd)
            if self.inbuf:
                raise ProtocolError(f"Pipelining error; previous bytes unread: {self.inbuf[:10000]}")
            await self.sock.send_all(self.data_to_send())
            ret = [await self.receive() for _ in commands]
            if self.inbuf:
                raise ProtocolError(f"Pipelining error; bytes left unread: {self.inbuf[:10000]}")
            return ret
        except:
            await self.aclose()
            raise
