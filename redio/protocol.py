import json

from functools import partial

from redio import conv
from redio.exc import ProtocolError, ServerError

class Protocol:
    def __init__(self):
        self.inbuf = bytearray()
        self.outbuf = bytearray()

    def data_to_send(self):
        ret = bytes(self.outbuf)
        del self.outbuf[:]
        return ret

    async def receive(self):
        t, arg = await self._recvline()
        if t == "+": return arg
        if t == "-": return ServerError(arg)
        arg = int(arg)
        if t == ":": return arg
        if t == "$": return None if arg == -1 else await self._recvbulk(arg)
        if t == "*": return [await self.receive() for _ in range(arg)]
        raise ProtocolError(f"Redis protocol out of sync (line begins with {t}).")

    async def _recvline(self):
        buffer = self.inbuf
        while (pos := buffer.find(b"\r\n")) == -1:
            buffer += await self.receiver()
        ret = buffer[:pos].decode()
        del buffer[:pos + 2]
        return ret[0], ret[1:]

    async def _recvbulk(self, num):
        buffer = self.inbuf
        while len(buffer) < num + 2:
            buffer += await self.receiver()
        if buffer[num:num+2] != b"\r\n":
            raise ProtocolError(f"Redis protocol out of sync (no CRLF after bulk)")
        ret = buffer[:num]
        del buffer[:num+2]
        return bytes(ret)

    def command(self, cmd: tuple):
        buffer = self.outbuf
        buffer += b"*%d\r\n" % len(cmd)
        for a in cmd:
            buffer += b"$%d\r\n%b\r\n" % (len(a), a)
        return self

    def __getattr__(self, name):
        """Allow calling protocol.PING() etc. to queue commands."""
        if name.isupper():
            setattr(self, name, partial(self._command, name.encode()))
        return super().__getattribute__(name)
