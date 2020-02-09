class RedisError(Exception):
    pass

class ServerError(RedisError):
    pass

class ProtocolError(RedisError):
    pass
