from redio import conv
from redio.commands import CommandBase
from redio.conn import Connection
from redio.exc import RedisError

class Redis(CommandBase):
    def __init__(self, *args, **kwargs):
        self.conn = Connection(*args, **kwargs)
        self.commands = []
        self.bytedecode = None

    def __await__(self):
        return self._run().__await__()

    @property
    def fulldecode(self):
        return self.decode(conv.bytedecode_full)

    @property
    def strdecode(self):
        return self.decode(conv.bytedecode_str)

    def decode(self, bytedecode):
        self.bytedecode = bytedecode
        return self

    async def _run(self):
        if not self.conn:
            await self.conn.connect()

        if not self.commands:
            return await self.ping()
        commands = []
        handlers = []
        for handler, cmd in self.commands:
            handlers.append(handler)
            commands.append([conv.encode(a) for a in cmd])
        self.commands = []
        res = await self.conn.run(commands)
        ret = []
        for h, r in zip(handlers, res):
            if h is None:
                ret += r,
                continue
            if isinstance(h, str):
                if r != h:
                    raise RedisError(f"Expected {h}, got {r}")
                continue
            ret += h(r),
        if self.bytedecode:
            ret = conv.decode(ret, bytedecode=self.bytedecode)
            self.bytedecode = None
        return ret if len(ret) != 1 else ret[0]

    def _command(self, *cmd, handler=None):
        self.commands.append((handler, cmd))
        return self
