from abc import ABC, abstractmethod

from redio.conv import list_to_dict, list_of_keys


class CommandBase(ABC):
    """High level API command handlers"""

    def __init__(self):
        super().__init__()
        # Transaction state: None, "watch" or list of handlers (in multi)
        self._transaction_state = None

    @abstractmethod
    def _command(self, *cmd, handler=None):
        """Queue a command tuple."""

    ## Transactions

    def watch(self, key1, *keys):
        """Marks the given keys to be watched for conditional execution of a transaction."""
        if self._transaction_state not in (None, "watch"):
            raise ValueError("WATCH inside MULTI is not allowed")
        self._transaction_state = "watch"
        return self._command(b'WATCH', key1, *keys, handler="OK")

    def unwatch(self):
        """Forget about all watched keys"""
        if self._transaction_state not in (None, "watch"):
            raise ValueError("UNWATCH inside MULTI is not allowed")
        self._transaction_state = None
        return self._command(b'UNWATCH', handler="OK")

    def multi(self):
        """Marks the start of a transaction block. Subsequent commands will be queued for atomic execution using EXEC."""
        if self._transaction_state not in (None, "watch"):
            raise ValueError("MULTI calls can not be nested")
        ret = self._command(b'MULTI', handler="OK")
        self._transaction_state = []  # This is used in self._command
        return ret

    def discard(self):
        """Flushes all previously queued commands in a transaction and restores the connection state to normal.

        If WATCH was used, DISCARD unwatches all keys watched by the connection."""
        if self._transaction_state in (None, "watch"):
            raise ValueError("DISCARD without MULTI")
        self._transaction_state = None
        return self._command(b'DISCARD', handler="OK")

    def exec(self):
        """Executes all previously queued commands in a transaction and restores the connection state to normal.

        When using WATCH, EXEC will execute commands only if the watched keys were not modified, allowing for a check-and-set mechanism"""
        if self._transaction_state in (None, "watch"):
            raise ValueError("EXEC without MULTI")
        handler_list, self._transaction_state = self._transaction_state, None
        return self._command(b'EXEC', handler=handler_list)

    ## Manually crafted Redis command helpers

    def ping(self, *args):
        """PING server and check for PONG response."""
        return self._command(b'PING', *args, handler="PONG")

    def set(self, key, val, *keyvals):
        """SET a value for key."""
        return self._command(b'SET', key, val, *keyvals, handler="OK")

    def keys(self, pattern="*"):
        """Returns all keys matching pattern."""
        return self._command(b'KEYS', pattern, handler=list_of_keys)

    ## Hash keys

    def hset(self, key, dictionary=None, **keyval):
        """Sets field in the hash stored at key to value. If key does not exist, a new key holding a hash is created. If field already exists in the hash, it is overwritten. Multiple fields may be set in the same command.

        Python dict or keywords arguments define field names and values."""
        if dictionary:
            keyval = {**dictionary, **keyval}
        args = [a for kv in keyval.items() for a in kv]
        return self._command(b"HSET", key, *args)

    def hgetall(self, key):
        """Returns all fields and values of the hash stored at key.

        Python dict with str keys is returned."""
        return self._command(b'HGETALL', key, handler=list_to_dict)

    def hdel(self, key, field, *fields):
        """Removes the specified fields from the hash stored at key. Specified fields that do not exist within this hash are ignored. If key does not exist, it is treated as an empty hash and this command returns 0.

        Return value: the number of fields that were removed from the hash, not including specified but non existing fields."""
        return self._command(b'HDEL', key, field, *fields)

    def hexists(self, key, field):
        """Returns if field is an existing field in the hash stored at key."""
        return self._command(b'HEXISTS', key, field, handler=bool)

    def hget(self, key, field):
        """Returns the value associated with field in the hash stored at key, or None.

        If a list of field names is passed as field, a list of values is returned (HMGET)."""
        if isinstance(field, (tuple, list)):
            # FIXME: Empty list leads to Redis error
            return self._command(b'HMGET', key, *field)
        return self._command(b'HGET', key, field)

    def hincrby(self, key, field, num):
        """Increments the number stored at field in the hash stored at key by increment. If key does not exist, a new key holding a hash is created. If field does not exist the value is set to 0 before the operation is performed.

        The range of values supported by HINCRBY is limited to 64 bit signed integers.

        Return value: the value at field after the increment operation."""
        return self._command(b'HINCRBY', key, field, num)

    def hincrbyfloat(self, key, field, num):
        """Increment the specified field of a hash stored at key, and representing a floating point number, by the specified increment. If the increment value is negative, the result is to have the hash field value decremented instead of incremented. If the field does not exist, it is set to 0 before performing the operation. An error is returned if one of the following conditions occur:

        The field contains a value of the wrong type (not a string).
        The current field content or the specified increment are not parsable as a double precision floating point number.

        Return value: bytes: the value of field after the increment."""
        return self._command(b'HINCRBYFLOAT', key, field, num)

    def hkeys(self, key):
        """Returns all field names in the hash stored at key."""
        return self._command(b'HKEYS', key, handler=list_of_keys)

    def hlen(self, key):
        """Returns the number of fields contained in the hash stored at key."""
        return self._command(b'HLEN', key)

    def hsetnx(self, key, field, value, handler=bool):
        """Sets field in the hash stored at key to value, only if field does not yet exist. If key does not exist, a new key holding a hash is created. If field already exists, this operation has no effect.

        Return value: bool: whether the field was created and set."""
        return self._command(b'HSETNX', key, field, value)

    def hstrlen(self, key, field):
        """Returns the string length of the value associated with field in the hash stored at key. If the key or the field do not exist, 0 is returned."""
        return self._command(b'HSTRLEN', key, field)

    def hvals(self, key):
        """Returns all values in the hash stored at key."""
        return self._command(b'HVALS', key)

    ## Key expiration times

    def expire(self, key, seconds: float):
        """PEXPIRE/EXPIRE: set key expiration in seconds"""
        return self._command(b'PEXPIRE', key, f"{1000 * seconds:.0f}")

    def expireat(self, key, time: float):
        """PEXPIREAT/EXPIREAT: set key expiration deadline"""
        return self._command(b'PEXPIREAT', key, 1000 * time)

    def ttl(self, key):
        """Return TTL of a key in seconds, with millisecond precision (float)."""
        return self._command(b'PTTL', key, handler=lambda ms: .001 * ms)

    ## Scanning (not very pythonic)
    def scan(self, arg1, *args): return self._command(b'SCAN', arg1, *args)
    def hscan(self, key, arg2, *args): return self._command(b'HSCAN', key, arg2, *args)
    def zscan(self, key, arg2, *args): return self._command(b'ZSCAN', key, arg2, *args)
    def sscan(self, key, arg2, *args): return self._command(b'SSCAN', key, arg2, *args)

    ## The rest are auto-generated and not all of them might make sense.

    def append(self, key, arg2): return self._command(b'APPEND', key, arg2)
    def asking(self): return self._command(b'ASKING')
    def bgrewriteaof(self): return self._command(b'BGREWRITEAOF')
    def bgsave(self, *args): return self._command(b'BGSAVE', *args)
    def bitcount(self, key, *args): return self._command(b'BITCOUNT', key, *args)
    def bitfield(self, key, *args): return self._command(b'BITFIELD', key, *args)
    def bitop(self, arg1, key1, key2, *args): return self._command(b'BITOP', arg1, key1, key2, *args)
    def bitpos(self, key, arg2, *args): return self._command(b'BITPOS', key, arg2, *args)
    def blpop(self, arg1, arg2, *args): return self._command(b'BLPOP', arg1, arg2, *args)
    def brpop(self, arg1, arg2, *args): return self._command(b'BRPOP', arg1, arg2, *args)
    def brpoplpush(self, key1, key2, arg3): return self._command(b'BRPOPLPUSH', key1, key2, arg3)
    def bzpopmax(self, arg1, arg2, *args): return self._command(b'BZPOPMAX', arg1, arg2, *args)
    def bzpopmin(self, arg1, arg2, *args): return self._command(b'BZPOPMIN', arg1, arg2, *args)
    def client(self, arg1, *args): return self._command(b'CLIENT', arg1, *args)
    def cluster(self, arg1, *args): return self._command(b'CLUSTER', arg1, *args)
    def command(self): return self._command(b'COMMAND')
    def config(self, arg1, *args): return self._command(b'CONFIG', arg1, *args)
    def dbsize(self): return self._command(b'DBSIZE')
    def debug(self, arg1, *args): return self._command(b'DEBUG', arg1, *args)
    def decr(self, key): return self._command(b'DECR', key)
    def decrby(self, key, arg2): return self._command(b'DECRBY', key, arg2)
    def delete(self, key1, *args): return self._command(b'DEL', key1, *args)
    def dump(self, key): return self._command(b'DUMP', key)
    def echo(self, arg1): return self._command(b'ECHO', arg1)
    def eval(self, arg1, arg2, *args): return self._command(b'EVAL', arg1, arg2, *args)
    def evalsha(self, arg1, arg2, *args): return self._command(b'EVALSHA', arg1, arg2, *args)
    def exists(self, key1, *args): return self._command(b'EXISTS', key1, *args)
    def flushall(self, *args): return self._command(b'FLUSHALL', *args, handler="OK")
    def flushdb(self, *args): return self._command(b'FLUSHDB', *args, handler="OK")
    def geoadd(self, key, arg2, arg3, arg4, *args): return self._command(b'GEOADD', key, arg2, arg3, arg4, *args)
    def geodist(self, key, arg2, arg3, *args): return self._command(b'GEODIST', key, arg2, arg3, *args)
    def geohash(self, key, *args): return self._command(b'GEOHASH', key, *args)
    def geopos(self, key, *args): return self._command(b'GEOPOS', key, *args)
    def georadius(self, key, arg2, arg3, arg4, arg5, *args): return self._command(b'GEORADIUS', key, arg2, arg3, arg4, arg5, *args)
    def georadiusbymember(self, key, arg2, arg3, arg4, *args): return self._command(b'GEORADIUSBYMEMBER', key, arg2, arg3, arg4, *args)
    def get(self, key): return self._command(b'GET', key)
    def getbit(self, key, arg2): return self._command(b'GETBIT', key, arg2)
    def getrange(self, key, arg2, arg3): return self._command(b'GETRANGE', key, arg2, arg3)
    def getset(self, key, arg2): return self._command(b'GETSET', key, arg2)
    def incr(self, key): return self._command(b'INCR', key)
    def incrby(self, key, arg2): return self._command(b'INCRBY', key, arg2)
    def incrbyfloat(self, key, arg2): return self._command(b'INCRBYFLOAT', key, arg2)
    def info(self, *args): return self._command(b'INFO', *args)
    def lastsave(self): return self._command(b'LASTSAVE')
    def latency(self, arg1, *args): return self._command(b'LATENCY', arg1, *args)
    def lindex(self, key, arg2): return self._command(b'LINDEX', key, arg2)
    def linsert(self, key, arg2, arg3, arg4): return self._command(b'LINSERT', key, arg2, arg3, arg4)
    def llen(self, key): return self._command(b'LLEN', key)
    def lolwut(self, *args): return self._command(b'LOLWUT', *args)
    def lpop(self, key): return self._command(b'LPOP', key)
    def lpush(self, key, arg2, *args): return self._command(b'LPUSH', key, arg2, *args)
    def lpushx(self, key, arg2, *args): return self._command(b'LPUSHX', key, arg2, *args)
    def lrange(self, key, arg2, arg3): return self._command(b'LRANGE', key, arg2, arg3)
    def lrem(self, key, arg2, arg3): return self._command(b'LREM', key, arg2, arg3)
    def lset(self, key, arg2, arg3): return self._command(b'LSET', key, arg2, arg3)
    def ltrim(self, key, arg2, arg3): return self._command(b'LTRIM', key, arg2, arg3)
    def memory(self, arg1, *args): return self._command(b'MEMORY', arg1, *args)
    def mget(self, key1, *args): return self._command(b'MGET', key1, *args)
    def migrate(self, arg1, arg2, arg3, arg4, arg5, *args): return self._command(b'MIGRATE', arg1, arg2, arg3, arg4, arg5, *args)
    def module(self, arg1, *args): return self._command(b'MODULE', arg1, *args)
    def monitor(self): return self._command(b'MONITOR')
    def move(self, key, arg2): return self._command(b'MOVE', key, arg2)
    def mset(self, key1, arg2, *args): return self._command(b'MSET', key1, arg2, *args)
    def msetnx(self, key1, arg2, *args): return self._command(b'MSETNX', key1, arg2, *args)
    def object(self, arg1, *args): return self._command(b'OBJECT', arg1, *args)
    def persist(self, key): return self._command(b'PERSIST', key)
    def pexpire(self, key, arg2): return self._command(b'PEXPIRE', key, arg2)
    def pexpireat(self, key, arg2): return self._command(b'PEXPIREAT', key, arg2)
    def pfadd(self, key, *args): return self._command(b'PFADD', key, *args)
    def pfcount(self, key1, *args): return self._command(b'PFCOUNT', key1, *args)
    def pfdebug(self, arg1, arg2, *args): return self._command(b'PFDEBUG', arg1, arg2, *args)
    def pfmerge(self, key1, *args): return self._command(b'PFMERGE', key1, *args)
    def pfselftest(self): return self._command(b'PFSELFTEST')
    def post(self, *args): return self._command(b'POST', *args)
    def psetex(self, key, arg2, arg3): return self._command(b'PSETEX', key, arg2, arg3)
    def psync(self, arg1, arg2): return self._command(b'PSYNC', arg1, arg2)
    def publish(self, channel, message): return self._command(b'PUBLISH', channel, message)
    def randomkey(self): return self._command(b'RANDOMKEY')
    def readonly(self): return self._command(b'READONLY')
    def readwrite(self): return self._command(b'READWRITE')
    def rename(self, key1, key2): return self._command(b'RENAME', key1, key2)
    def renamenx(self, key1, key2): return self._command(b'RENAMENX', key1, key2)
    def replconf(self, *args): return self._command(b'REPLCONF', *args)
    def replicaof(self, arg1, arg2): return self._command(b'REPLICAOF', arg1, arg2)
    def restore(self, key, arg2, arg3, *args): return self._command(b'RESTORE', key, arg2, arg3, *args)
    def role(self): return self._command(b'ROLE')
    def rpop(self, key): return self._command(b'RPOP', key)
    def rpoplpush(self, key1, key2): return self._command(b'RPOPLPUSH', key1, key2)
    def rpush(self, key, arg2, *args): return self._command(b'RPUSH', key, arg2, *args)
    def rpushx(self, key, arg2, *args): return self._command(b'RPUSHX', key, arg2, *args)
    def sadd(self, key, arg2, *args): return self._command(b'SADD', key, arg2, *args)
    def save(self): return self._command(b'SAVE')
    def scard(self, key): return self._command(b'SCARD', key)
    def script(self, arg1, *args): return self._command(b'SCRIPT', arg1, *args)
    def sdiff(self, key1, *args): return self._command(b'SDIFF', key1, *args)
    def sdiffstore(self, key1, key2, *args): return self._command(b'SDIFFSTORE', key1, key2, *args)
    def setbit(self, key, arg2, arg3): return self._command(b'SETBIT', key, arg2, arg3)
    def setex(self, key, arg2, arg3): return self._command(b'SETEX', key, arg2, arg3)
    def setnx(self, key, arg2): return self._command(b'SETNX', key, arg2)
    def setrange(self, key, arg2, arg3): return self._command(b'SETRANGE', key, arg2, arg3)
    def shutdown(self, *args): return self._command(b'SHUTDOWN', *args)
    def sinter(self, key1, *args): return self._command(b'SINTER', key1, *args)
    def sinterstore(self, key1, key2, *args): return self._command(b'SINTERSTORE', key1, key2, *args)
    def sismember(self, key, arg2): return self._command(b'SISMEMBER', key, arg2)
    def slaveof(self, arg1, arg2): return self._command(b'SLAVEOF', arg1, arg2)
    def slowlog(self, arg1, *args): return self._command(b'SLOWLOG', arg1, *args)
    def smembers(self, key): return self._command(b'SMEMBERS', key)
    def smove(self, key1, key2, arg3): return self._command(b'SMOVE', key1, key2, arg3)
    def sort(self, key, *args): return self._command(b'SORT', key, *args)
    def spop(self, key, *args): return self._command(b'SPOP', key, *args)
    def srandmember(self, key, *args): return self._command(b'SRANDMEMBER', key, *args)
    def srem(self, key, arg2, *args): return self._command(b'SREM', key, arg2, *args)
    def strlen(self, key): return self._command(b'STRLEN', key)
    def substr(self, key, arg2, arg3): return self._command(b'SUBSTR', key, arg2, arg3)
    def sunion(self, key1, *args): return self._command(b'SUNION', key1, *args)
    def sunionstore(self, key1, key2, *args): return self._command(b'SUNIONSTORE', key1, key2, *args)
    def swapdb(self, arg1, arg2): return self._command(b'SWAPDB', arg1, arg2)
    def sync(self): return self._command(b'SYNC')
    def time(self): return self._command(b'TIME')
    def touch(self, key, *args): return self._command(b'TOUCH', key, *args)
    def type(self, key): return self._command(b'TYPE', key)
    def unlink(self, key1, *args): return self._command(b'UNLINK', key1, *args)
    def wait(self, arg1, arg2): return self._command(b'WAIT', arg1, arg2)
    def xack(self, key, arg2, arg3, *args): return self._command(b'XACK', key, arg2, arg3, *args)
    def xadd(self, key, arg2, arg3, arg4, *args): return self._command(b'XADD', key, arg2, arg3, arg4, *args)
    def xclaim(self, key, arg2, arg3, arg4, arg5, *args): return self._command(b'XCLAIM', key, arg2, arg3, arg4, arg5, *args)
    def xdel(self, key, arg2, *args): return self._command(b'XDEL', key, arg2, *args)
    def xgroup(self, arg1, *args): return self._command(b'XGROUP', arg1, *args)
    def xinfo(self, arg1, *args): return self._command(b'XINFO', arg1, *args)
    def xlen(self, key): return self._command(b'XLEN', key)
    def xpending(self, key, arg2, *args): return self._command(b'XPENDING', key, arg2, *args)
    def xrange(self, key, arg2, arg3, *args): return self._command(b'XRANGE', key, arg2, arg3, *args)
    def xread(self, key, arg2, arg3, *args): return self._command(b'XREAD', key, arg2, arg3, *args)
    def xreadgroup(self, key, arg2, arg3, arg4, arg5, arg6, *args): return self._command(b'XREADGROUP', key, arg2, arg3, arg4, arg5, arg6, *args)
    def xrevrange(self, key, arg2, arg3, *args): return self._command(b'XREVRANGE', key, arg2, arg3, *args)
    def xsetid(self, key, arg2): return self._command(b'XSETID', key, arg2)
    def xtrim(self, key, *args): return self._command(b'XTRIM', key, *args)
    def zadd(self, key, arg2, arg3, *args): return self._command(b'ZADD', key, arg2, arg3, *args)
    def zcard(self, key): return self._command(b'ZCARD', key)
    def zcount(self, key, arg2, arg3): return self._command(b'ZCOUNT', key, arg2, arg3)
    def zincrby(self, key, arg2, arg3): return self._command(b'ZINCRBY', key, arg2, arg3)
    def zinterstore(self, arg1, arg2, arg3, *args): return self._command(b'ZINTERSTORE', arg1, arg2, arg3, *args)
    def zlexcount(self, key, arg2, arg3): return self._command(b'ZLEXCOUNT', key, arg2, arg3)
    def zpopmax(self, key, *args): return self._command(b'ZPOPMAX', key, *args)
    def zpopmin(self, key, *args): return self._command(b'ZPOPMIN', key, *args)
    def zrange(self, key, arg2, arg3, *args): return self._command(b'ZRANGE', key, arg2, arg3, *args)
    def zrangebylex(self, key, arg2, arg3, *args): return self._command(b'ZRANGEBYLEX', key, arg2, arg3, *args)
    def zrangebyscore(self, key, arg2, arg3, *args): return self._command(b'ZRANGEBYSCORE', key, arg2, arg3, *args)
    def zrank(self, key, arg2): return self._command(b'ZRANK', key, arg2)
    def zrem(self, key, arg2, *args): return self._command(b'ZREM', key, arg2, *args)
    def zremrangebylex(self, key, arg2, arg3): return self._command(b'ZREMRANGEBYLEX', key, arg2, arg3)
    def zremrangebyrank(self, key, arg2, arg3): return self._command(b'ZREMRANGEBYRANK', key, arg2, arg3)
    def zremrangebyscore(self, key, arg2, arg3): return self._command(b'ZREMRANGEBYSCORE', key, arg2, arg3)
    def zrevrange(self, key, arg2, arg3, *args): return self._command(b'ZREVRANGE', key, arg2, arg3, *args)
    def zrevrangebylex(self, key, arg2, arg3, *args): return self._command(b'ZREVRANGEBYLEX', key, arg2, arg3, *args)
    def zrevrangebyscore(self, key, arg2, arg3, *args): return self._command(b'ZREVRANGEBYSCORE', key, arg2, arg3, *args)
    def zrevrank(self, key, arg2): return self._command(b'ZREVRANK', key, arg2)
    def zscore(self, key, arg2): return self._command(b'ZSCORE', key, arg2)
    def zunionstore(self, arg1, arg2, arg3, *args): return self._command(b'ZUNIONSTORE', arg1, arg2, arg3, *args)
