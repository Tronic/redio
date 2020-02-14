# RedIO - Redis for Trio

A Python 3.7+ module for using Redis database in async programs based on the Trio library.

```
pip install git+https://github.com/Tronic/redio.git
```

This module is not ready for production use and all APIs are still likely to change. It works with my applications and performs roughly at the same speed as other Redis modules for Python.

## Normal mode (high level API)

A simple program to get started:

```python
import redio, trio

# Initialise a connection pool
redis = redio.Redis("redis://localhost/")

async def main():
    some, another = await redis().get("somekey").get("anotherkey")
    print("Got values:", some, another)

trio.run(main)
```

Most normal [Redis commands](https://redis.io/commands) are available and they can either be called in such sequence like above, or if more convenient, using a variable:

```python
db = redis()  # Get a DB object
db.get("bar")
db.set("bar", "value").expire("bar", 0.5)  # Automatically deleted after 500 ms
db.get("bar")
old_bar, expire, bar = await db
```

All commands are queued and sent to server only on the next `await`, improving performance especially if the Redis server is not on localhost, as unnecessary server round-trips are eliminated and often everything fits in a single packet.

Responses are returned as a list in the same order as the commands, noting that commands such as `set` do not produce any output.

### Hash keys

Redis keys may contain dictionaries with field names and values. RedIO `hset` allows specifying fields by **keyword arguments**:

```python
await redis().hset(
  "hashkey",
  field1=bytes([255, 0, 255]),
  field2="text",
  field3=1.23,
)
```

Instead of keyword arguments, a `dict` may be used. Similarly, values returned by `hgetall` come as a dictionary:

```python
>>> await redis().hgetall("hashkey").autodecode
{
  'field1': b'\xff\x00\xff',
  'field2': 'text',
  'field3': 1.23,
}
```

### Transactions

A MULTI/EXEC transaction allows atomic execution without other clients running any commands in between. The following increments keys foo and bar atomically and returns their new values:

```python
>>> await redis().multi().incr("foo").incr("bar").exec()
[1, 1]
```

Note: Redis cannot abort and undo an ongoing transaction once it has started. The server will attempt to execute all of the commands, even after errors.

One or more WATCH commands may be used prior to transaction to implement optimistic locking using *check-and-set* where the transaction is discarded if any of the watched keys were modified. Usually the operation is attempted again until successful:

```python
db = redis()

# Inverts the capitalization of foo (sets "DEFAULT value" if foo does not exist)
while True:
    db.watch("foo")
    foo = await db.get("foo") or b"default VALUE"
    db.multi()
    db.set("foo", foo.swapcase())
    if await db.exec():
        break
```

`False` is returned by `exec` if the transaction was discarded. Otherwise a list of responses or `True` is returned. In this example a boolean is always returned because the only command within the transaction was `set` which does not produce any output.

## Pub/Sub channels

### Sending messages

Messages are published via normal `publish` commands:

```python
await redis().publish("channel", "message")
```

### Receiving messages

Receiving connections can be created by calling `pubsub` on the connection pool:

```python
async for message in redis.pubsub("channel"):
    print(message)
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
    print(message, "from", channel)
```

Instead of `async for` you may equivalently `await pubsub` to receive a single message.

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

Keys such as field names and channel names are always decoded into `str` and the decoding modes only affect handling of values (content). Many Redis protocol commands also respond with typed integer, string or list responses which are not affected by this.

Three decoding modes are provided for raw byte values. By default, values are not decoded. The other modes are enabled by modifiers `.strdecode` and `.autodecode`, which affect **only** the next `await`. Pub/Sub mode does not reset its decoding settings, so they persist once initially set.

#### Default (no decoding)

```python
>>> await db.get("binary").get("number").get("jsonkey")
[
  b"\x80\x00\xFF",
  b"10",
  b'{"foo": 123, "bar": [1, 2, 3]}'
]
```

#### .strdecode

```python
>>> await db.get("binary").get("number").get("jsonkey").strdecode
[
  '\udc80\x00\udcff',
  '10',
  '{"foo": 123, "bar": [1, 2, 3]}',
]
```

All values are decoded into `str` with invalid UTF-8 sequences replaced by Unicode surrogate values.

#### .autodecode

```python
>>> await db.get("binary").get("number").get("jsonkey").autodecode
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
