import struct


class BytesBuffer:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def size(self):
        return len(self._data) - self._pos

    def data(self):
        return self._data[self._pos :]

    def unpack(self, fmt):
        sz = struct.calcsize(fmt)
        if self._pos + sz > len(self._data):
            raise Exception(f'BytesBuffer: {sz} bytes required for {fmt}, but have only {len(self._data) - self._pos}')
        self._pos += sz
        return struct.unpack_from(fmt, self._data, self._pos - sz)

    def unpack_string(self) -> str:
        slen = self.unpack('<B')[0]
        return self.unpack(f'<{slen}s')[0].decode('ascii')
