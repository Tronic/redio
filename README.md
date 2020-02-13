# RedIO - Redis for Trio

A Python module for using Redis database in async programs based on the Trio library.

```
pip install git+https://github.com/Tronic/redio.git
```

This module is not ready for production use and all APIs are still likely to change. It works with my applications and performs roughly at the same speed as other Redis modules for Python.

## Normal mode (high level API)

```python
from redio import Redis

# Initialise a connection pool
redis = Redis("redis://localhost/")
```

A simple syntax for pipelining multiple commands with high performance:

```python
somekey, anotherkey = await redis().get("somekey").get("anotherkey")
```

Most normal [Redis commands](https://redis.io/commands) are available this way and they can either be called in such sequence, or if more convenient:

```
db = redis()
db.get("bar")
db.set("bar", "value").expire("bar", 0.5)
db.get("bar")
old_bar, bar = await db
```

### Dict interface to hash keys

```python
await redis().hmset_dict(
  "hashkey",
  field1=bytes([255, 0, 255]),
  field2="text",
  field3=1.23,
)
```

Instead of keyword arguments, a `dict` may also be passed.

```python
>>> await redis().hgetall("hashkey").autodecode
{
  'field1': b'\xff\x00\xff',
  'field2': 'text',
  'field3': 1.23,
}
```

### Transactions (WATCH/MULTI/EXEC)

```python
redis = redio.Redis()
db = redis()

foo = await db.watch("foo").get("foo")

# Do something with the value (e.g. switch capitalization)
foo = (foo or b"Default Value").swapcase()

# The following commands are in transaction
db.multi()
db.set("foo", foo)

# Someone else (think another program) touches the watched key
if random:
    await redis().set("foo", b"Another Value")

result = await db.exec()
```

If any of the watched keys are touched prior to execution, none of the commands after `multi` are run and the result is `False`.

Otherwise all of the commands are run in sequence with no intervening commands from other users. `True` is returned if none of the commands had any output (as in this example), or otherwise a list of the command results is returned.

Note: Redis has no rollback and it cannot abort an ongoing transaction once it has started. Instead all remaining commands are run and any exceptions are **returned** as part of the exec response rather than raised.


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

Instead of `async for` you may equivalently `await pubsub` to receive a single message.

Messages are published via normal mode:

```python
await redis().publish("channel", "message")
```

## Bytes encoding and decoding

### Command encoding

Redis commands only take bytes and have no other data types. Any non-bytes arguments are automatically encoded (strings, numbers, json):

```python
db = redis()
db.set("binary", bytes([128, 0, 255]))
db.set("number", 10)
db.set("jsonkey", dict(foo=123, bar=[1, 2, 3]))
await db
```

### Response decoding

Keys such as field names and channel names are always decoded into `str` and the decoding modes only affect handling of values (content). Many Redis protocol commands also give integer or other typed responses.

By default, the returned results are not decoded:

```python
>>> await db.get("binary").get("number").get("jsonkey")
[
  b"\x80\x00\xFF",
  b"10",
  b'{"foo": 123, "bar": [1, 2, 3]}'
]
```

Add `.strdecode` or `.autodecode` to have all values decoded. This setting affects the next `await` and then **resets** back to default. Pub/Sub mode does not reset its decoding settings.

### .strdecode

```python
>>> await redis().get("binary").get("number").get("jsonkey").strdecode
[
  '\udc80\x00\udcff',
  '10',
  '{"foo": 123, "bar": [1, 2, 3]}',
]
```

All values are decoded into `str` with invalid UTF-8 sequences replaced by Unicode surrogate values.

### .autodecode

```python
>>> await redis().get("binary").get("number").get("jsonkey").autodecode
[
  b"\x80\x00\xFF",
  10,
  {'foo': 123, 'bar': [1, 2, 3]},
]
```

The autodecode mode tries to guess correct format based on content. This is mostly useful when you know that the data is only JSON or numbers. Arbitrary binary or string data might be accidentally decoded further than it should.

## Async safety

Notice that the `redis` object may be shared by multiple async workers but each must obtain a separate connection by calling it, as in the examples.

A connection may be stored in a variable and used for multiple commands that rely on each other, e.g. transactions. This module attempts to keep track of whether the connection is reusable and thus can be returned to connection pool.

It is possible to use `.prevent_pooling` modifier on a DB object to prevent its connection being pooled after use.

## Connection URLs

There are no separate arguments for hostname, port number and such. Instead all settings are encoded in an URL passed to Redis(). A format similar to other Redis modules is used. Some examples:

* `redis://localhost/` - default setting (localhost:6379, database 0, no auth)
* `redis://:password@localhost/2` - password authentication, using database 2
* `rediss://secure.cloud/` or `redis+tls://secure.cloud/` - both are the same: secure connection
* `redis+unix:///var/run/redis.sock?database=2` - UNIX socket connection must use three slashes
* `redis+unix+tls://hostname.on.certificate/tmp/redis.sock` - why'd you want TLS on unix socket?
