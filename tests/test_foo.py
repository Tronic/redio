import redio

async def test_ping():
    redis = redio.Redis("redis://localhost/9")
    ret = await redis().ping()
    assert ret is None
