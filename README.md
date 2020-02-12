# RedIO - Redis for Trio

A Python module for using Redis database in async programs based on the Trio
library.

```
pip install git+https://github.com/Tronic/redio.git
```

This module is not ready for production use and all APIs are still likely to
change. It works with my applications and performs roughly at the same speed
as other Redis modules for Python.

## High level API in normal mode

```python
from redio import Redis

# Connection pool
redis = Redis("redis://localhost/")

# Pipelining of multiple commands
somekey, anotherkey = await redis().get("somekey").get("anotherkey")

# Parameters are encoded automatically
await redis().set("number", 10).set("jsonkey", dict(foo=123, bar=[1, 2, 3])).get("jsonkey")
b'{"foo": 123, "bar": [1, 2, 3]}'

# Redis normally stores bytes only. Add .strdecode or .fulldecode to have all
# values decoded based on content (only effective until the next await).
await redis().get("number").get("jsonkey").fulldecode
[10, {'foo': 123, 'bar': [1, 2, 3]}]

# Dict interface to hash keys
redis().hmset_dict("hashkey", field1=bytes([255, 0, 255]), field2="text", field3=1.23)
await redis().hgetall("hashkey")
{'field1': b'\xff\x00\xff', 'field2': b'text', 'field3': b'1.23'}

# Decoding also applies to dict values. Note that dict keys are always decoded.
await redis().hgetall("hashkey").fulldecode
{'field1': b'\xff\x00\xff', 'field2': 'text', 'field3': 1.23}
```

Notice that the `redis` object may be shared by multiple async workers but each
must obtain a separate connection by calling it, as in the examples.

A connection may be stored in a variable and used for multiple commands that
rely on each other, e.g. transactions


## Pub/Sub channels

```python
redis = redio.Redis()

async for message in redis.pubsub("foo"):
    # ...
```

Additional channels may be subscribed by `subscribe` and `psubscribe` commands
on the PubSub object, and zero or more initial channels may be specified while
creating the object by calling `redis.pubsub()`.

By default only messages are received. When subscribing multiple channels on the
same PubSub receiver, it may be useful to receive channel names as well, enabled
by the `.with_channel` modifier. As with the standard interface, all commands
and modifiers can be chained or called separately, as they return `self`.

```python
pubsub = redis.pubsub().strdecode.with_channel
pubsub.subscribe("foo", "bar")
pubsub.psubscribe("chan*")

async for channel, message in pubsub:
    # ...
```

Instead of `async for ... in pubsub` you may equivalently `await pubsub`.

Messages are published via normal mode:

```python
await redis().publish("channel", "message")
```
