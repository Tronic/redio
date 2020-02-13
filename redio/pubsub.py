from redio.conv import ByteDecoder, bytedecode_str, encode
from redio.exc import ProtocolError

class PubSub(ByteDecoder):
    """Publish/subscribe receiver."""
    def __init__(self, redis, *channels):
        super().__init__()
        self.protocol = redis._borrow_connection()
        self.subscribed = set()
        self.psubscribed = set()
        self.requested_count = 0
        self.subscription_count = 0
        self.messages = []
        self._with_channel = False
        if channels:
            self.subscribe(*channels)

    @property
    def with_channel(self):
        """Enable receiving of receive (channel, message) tuples rather than
        plain messages."""
        self._with_channel = True
        return self

    def subscribe(self, *channels):
        return self._subscribe(b"SUBSCRIBE", channels)

    def psubscribe(self, *channels):
        return self._subscribe(b"PSUBSCRIBE", channels)

    def _subscribe(self, command, channels):
        channels = [encode(a) for a in channels]
        self.protocol._command((command, *channels))
        self.requested_count += len(channels)
        return self

    async def __aiter__(self):
        while self.requested_count > 0:
            yield await self

    def __await__(self):
        return self._run().__await__()

    async def _run(self):
        if self.protocol.closed:
            await self.protocol.connect()
        await self.protocol.send_all()
        while True:
            res = await self.protocol.receive()

            if not isinstance(res, (list, tuple)) or not 3 <= len(res) <= 4:
                raise ProtocolError(f"Unexpected message received in PubSub mode: {res!r}")

            if res[0] in (b"message", b"pmessage"):
                msg = self._decode(res[-1])
                return (bytedecode_str(res[-2]), msg) if self._with_channel else msg

            if res[0] == b"subscribe":
                self.subscribed.add(res[1].decode())
                self.subscription_count = res[2]
            elif res[0] == b"psubscribe":
                self.psubscribed.add(res[1].decode())
                self.subscription_count = res[2]
            else:
                raise ProtocolError(f"Unexpected message received in PubSub mode: {res!r}")

            if self.subscription_count != len(self.subscribed) + len(self.psubscribed):
                raise ProtocolError(
                    f"PubSub channel tracking out of sync len({self.subscribed!r}) != {self.subscription_count}")
