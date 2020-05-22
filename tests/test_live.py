from redio import Redis
import pytest

@pytest.fixture
def redis():
    yield Redis("redis://localhost/9")

async def test_ping(redis):
    assert await redis().ping() == []

async def test_key(redis):
    await redis().delete("testkey") == 1
    assert await redis().set("testkey", b"value").get("testkey") == b"value"
    assert await redis().delete("testkey") == 1

async def test_hashkey(redis):
    await redis().delete("testhkey") == 1
    assert await redis().hgetall("testhkey") == {}
    assert await redis().hset("testhkey", dict(foo=b"foovalue", bar=b"barvalue")) == 2
    assert await redis().hset("testhkey", dict(foo=b"foovalue", bar=b"barvalue")) == 0
    assert await redis().hget("testhkey", "foo") == b"foovalue"
    assert await redis().hset("testhkey", foo=b"newfoovalue") == 0
    assert await redis().hset("testhkey", baz=b"bazvalue") == 1
    assert await redis().hgetall("testhkey") == {
        "foo": b"newfoovalue",
        "bar": b"barvalue",
        "baz": b"bazvalue",
    }
    assert await redis().delete("testhkey") == 1

async def test_pubsub(redis):
    assert await redis().publish("testchannel", b"Msg1") == 0
    channel = await redis.pubsub("testchannel").connect()
    assert await redis().publish("testchannel", b"Msg2") == 1
    async for msg in channel:
        assert msg == b"Msg2"
        break
