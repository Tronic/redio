import json

from functools import partial

from trio.abc import Stream

from redio import conv
from redio.conn import ConnectInfo
from redio.exc import ProtocolError, ServerError

class Protocol:
    """Redis protocol (server connection low level API)."""
    def __init__(self, conninfo: ConnectInfo):
        self.inbuf = bytearray()
        self.outbuf = bytearray()
        self.conninfo = conninfo
        self.sock = None

    @property
    def closed(self):
        return self.sock is None

    async def connect(self):
        self.sock = await self.conninfo.socket_connect()
        if self.conninfo.password:
            await self.AUTH(self.conninfo.password.encode())
        if self.conninfo.database:
            await self.SELECT(b"%d" % self.conninfo.database)

    async def aclose(self):
        """Close connection."""
        if not self.closed:
            del self.inbuf[:], self.outbuf[:]
            sock, self.sock = self.sock, None
            await sock.aclose()

    def __getattr__(self, name):
        """Allow calling protocol.PING() etc. to run commands."""
        if name.isupper():
            setattr(self, name, partial(self.run_single, name.encode()))
        return super().__getattribute__(name)

    def _command(self, cmd: tuple):
        """Queue a single command for execution."""
        buffer = self.outbuf
        buffer += b"*%d\r\n" % len(cmd)
        for a in cmd:
            buffer += b"$%d\r\n%b\r\n" % (len(a), a)
        return self

    async def run_single(self, *cmd):
        ret, = await self.run([cmd])
        if isinstance(ret, ServerError): raise ret
        return ret

    async def run(self, commands):
        """Run a set of commands and return responses.

        Uses pipelining but no transactions. Each command must return exactly
        one response. For commands where this is not true, Protocol must be
        accessed directly.

        RedisErrors are returned in the array rather than raised.
        """
        if self.closed:
            raise ValueError("Attempting to run on a closed connection")
        try:
            for cmd in commands:
                self._command(cmd)
            if self.inbuf:
                raise ProtocolError(
                    f"Pipelining error: previous bytes unread: {self.inbuf[:10000]}")
            if self.sock.socket.is_readable():
                raise ProtocolError(
                    f"Pipelining error: server sent unexpected data"
                )
            await self.send_all()
            ret = [await self.receive() for _ in commands]
            if self.inbuf:
                raise ProtocolError(
                    f"Pipelining error: bytes left unread: {self.inbuf[:10000]}")
            return ret
        except:
            await self.aclose()
            raise

    async def send_all(self):
        """Send any queued commands to server."""
        if self.outbuf:
            await self.sock.send_all(self.outbuf)
            del self.outbuf[:]

    async def receive(self):
        t, arg = await self._recvline()
        if t == "+": return arg
        if t == "-": return ServerError(arg)
        arg = int(arg)
        if t == ":": return arg
        if t == "$": return None if arg == -1 else await self._recvbulk(arg)
        if t == "*": return False if arg == -1 else [await self.receive() for _ in range(arg)]
        raise ProtocolError(f"Redis protocol out of sync (line begins with {t}).")

    async def _recvline(self):
        buffer = self.inbuf
        while True:
            pos = buffer.find(b"\r\n")
            if pos != -1: break
            buffer += await self.sock.receive_some()
        ret = buffer[:pos].decode()
        del buffer[:pos + 2]
        return ret[0], ret[1:]

    async def _recvbulk(self, num):
        buffer = self.inbuf
        while len(buffer) < num + 2:
            buffer += await self.sock.receive_some()
        if buffer[num:num+2] != b"\r\n":
            raise ProtocolError(f"Redis protocol out of sync (no CRLF after bulk)")
        ret = buffer[:num]
        del buffer[:num+2]
        return bytes(ret)
