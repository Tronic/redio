from redio.conv import ByteDecoder, bytedecode_str, encode
from redio.exc import ProtocolError

class PubSub(ByteDecoder):
    """Publish/subscribe receiver."""
    def __init__(self, protocol, *channels):
        super().__init__()
        self.protocol = protocol
        self.subscribed = set()
        self.psubscribed = set()
        self._sub = set()
        self._psub = set()
        self._with_channel = False
        self._messages = []
        if channels:
            self.subscribe(*channels)

    @property
    def with_channel(self):
        """Enable receiving of receive (channel, message) tuples rather than
        plain messages."""
        self._with_channel = True
        return self

    def subscribe(self, *channels):
        """Subscribe to receive channels. Takes effect on `await`."""
        self._sub.update(encode(a) for a in channels)
        return self

    def psubscribe(self, *channels):
        """Subscribe to receive channel patterns. Takes effect on `await`."""
        self._psub.update(encode(a) for a in channels)
        return self

    async def _subscribe(self):
        if self._sub:
            self.protocol._command([b"SUBSCRIBE", *self._sub])
        if self._psub:
            self.protocol._command([b"PSUBSCRIBE", *self._psub])
        await self.protocol.send_all()
        while self._sub or self._psub:
            res = await self.protocol.receive()
            if res[0] == b"subscribe":
                self.subscribed.add(res[1].decode())
                self._sub.remove(res[1])
                subscription_count = res[2]
            elif res[0] == b"psubscribe":
                self.psubscribed.add(res[1].decode())
                self._psub.remove(res[1])
                subscription_count = res[2]
            else:
                self._messages.append(res)
            if subscription_count != len(self.subscribed) + len(self.psubscribed):
                raise ProtocolError(
                    f"PubSub channel tracking out of sync len({self.subscribed!r}) != {subscription_count}"
                )

    async def __aiter__(self):
        while True:
            yield await self

    def __await__(self):
        return self._run().__await__()

    async def connect(self):
        """Connect to Redis if needed and subscribe requested channels."""
        if self.protocol.closed:
            await self.protocol.connect()
        await self._subscribe()
        self.connected = True
        return self

    async def _run(self):
        await self.connect()  # Connect and subscribe if needed
        while True:
            res = (
                self._messages.pop(0)
                if self._messages else
                await self.protocol.receive()
            )
            if not isinstance(res, (list, tuple)) or not 3 <= len(res) <= 4:
                raise ProtocolError(f"Unexpected message received in PubSub mode: {res!r}")

            if res[0] in (b"message", b"pmessage"):
                msg = self._decode(res[-1])
                return (bytedecode_str(res[-2]), msg) if self._with_channel else msg

            self._subresponse(res)
