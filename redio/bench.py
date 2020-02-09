
cmd = 100 * [b"command", b"arg", 100*b"arg"]

def main():
    a = bytearray()
    for _ in range(1000):
        a += b"".join(b"$%d\r\n%b\r\n" % (len(a), a) for a in cmd)


def main2():
    a = bytearray()
    for _ in range(1000):
        for a in cmd:
            a += b"$%d\r\n%b\r\n" % (len(a), a)
