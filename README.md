# RedIO - Redis for Trio

A Python module for using Redis database in async programs based on the Trio
library.

```
pip install git+https://github.com/Tronic/redio.git
```

This module is not ready for production use and all APIs are still likely to
change. It works with my applications and performs roughly at the same speed
as other Redis modules for Python.

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
