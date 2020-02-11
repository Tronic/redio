from contextlib import contextmanager
from functools import partial

from redio import conv
from redio.commands import CommandBase
from redio.conn import Connection
from redio.exc import RedisError

class RedisDB(CommandBase):
    """Redis database connection."""
    def __init__(self, connector):
        self.connector = connector
        self.conn = connector._borrow_connection()
        self.commands = []
        self.bytedecode = None

    def __del__(self):
        """Restore still usable connection to pool on garbage collect. We rely
        partially on CPython's reference counting but also note that it is not
        crucial for connections to be returned immediately."""
        if self.connector and self.conn:
            self.connector._restore_connection(self.conn)

    @property
    def prevent_pooling(self):
        """Prevent this connection being returned to connection pool."""
        self.connector = None
        return self

    def __await__(self):
        """Execute any pending commands and return their results.

        Generally there is one response per each command but some commands may
        not return anything.

        RedisError objects may be returned instead of being raised because the
        database does not abort or rollback anything, and thus all responses
        should be returned.

        Two or more responses are returned as a list."""
        return self._run().__await__()

    @property
    def fulldecode(self):
        """Enable decoding of strings, numbers and json. Undecodable sequences
        remain as bytes.

        This setting resets after each await."""
        return self.decode(conv.bytedecode_full)

    @property
    def strdecode(self):
        """Enable decoding of bytes into strs. Only UTF-8 bytes are decoded.

        This setting resets after each await."""
        return self.decode(conv.bytedecode_str)

    def decode(self, bytedecode):
        """Set custom byte decoding function.

        This setting resets after each await."""
        self.bytedecode = bytedecode
        return self

    async def _run(self):
        """Execute queued commands, equivalent to await self."""
        if not self.conn:
            await self.conn.connect()
        try:
            if self.commands:
                return await self._execute()
        except:
            # Any error and we assume that the connection is in invalid state.
            self.prevent_pooling
            await self.conn.aclose()
            self.conn = None
            raise

    async def _execute(self):
        """Execute queued commands without error handling."""
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


class Redis:
    """Redis connection pool."""
    def __init__(self, url="redis://localhost/", *, ssl_context=None, pool_max=100):
        self.new = partial(Connection, url, ssl_context=ssl_context)
        self.pool_max = pool_max
        self.pool = [self.new()]  # Mainly to test that args are OK!

    def __call__(self) -> RedisDB:
        """Get a Redis database connection."""
        return RedisDB(self)

    def _borrow_connection(self) -> Connection:
        return self.pool.pop() if self.pool else self.new()

    def _restore_connection(self, connection: Connection):
        if len(self.pool) < self.pool_max:
            self.pool += connection,
