import json

def list_to_dict(l):
    return {bytedecode_str(k): v for k, v in zip(l[::2], l[1::2])}

def list_of_keys(l):
    return [bytedecode_str(k) for k in l]

def bytedecode_auto(s):
    try:
        s = s.decode()
    except UnicodeDecodeError:
        return s
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def bytedecode_str(s):
    return s.decode(errors="surrogateescape")


def decode(response, bytedecode):
    if isinstance(response, bytes):
        response = bytedecode(response)
    elif isinstance(response, list):
        for i in range(len(response)):
            response[i] = decode(response[i], bytedecode)
    elif isinstance(response, dict):
        for k in response:
            response[k] = bytedecode(response[k])
    return response

def encode(a):
    if hasattr(a, "encode"): return a.encode()
    elif isinstance(a, (int, float, dict)): return json.dumps(a).encode()
    return a

def command_human(cmd: bytes, *args: bytes):
    """Produce a human-readable representation of a Redis command."""
    ret = cmd.decode()
    for a in args[:10]:
        if len(a) == 0:
            ret += ' ""'
            continue
        if len(a) < 20:
            try:
                a = a.decode()
                ret += f" {a}" if a.isalnum() else f" {a!r}"
                continue
            except UnicodeDecodeError:
                pass
        ret += f" [{len(a)} bytes]"
    if len(args) > 10:
        ret += f" ⋯ of {len(args)} args"
    return ret


class ByteDecoder:
    """Helpers for switching decoding modes (used in high level API)"""
    def __init__(self):
        self._bytedecode = None

    def _decode(self, text):
        """Decode text using the selected decoder"""
        return decode(text, self._bytedecode) if self._bytedecode else text

    @property
    def autodecode(self):
        """Enable decoding of strings, numbers and json. Undecodable sequences
        remain as bytes."""
        return self.bytedecoder(bytedecode_auto)

    @property
    def strdecode(self):
        """Enable decoding of bytes into strs.

        Produces Unicode surrogates \\uDC80...\\uDCFF for invalid UTF-8 bytes,
        using the errors=\"surrogateescape\" encode/decode mode of Python."""
        return self.bytedecoder(bytedecode_str)

    def bytedecoder(self, bytedecode):
        """Set custom byte decoding function."""
        self._bytedecode = bytedecode
        return self
