import struct


class BytesBuffer:
    """A buffer for reading binary data with position tracking.

    This class provides functionality to read binary data sequentially from a bytes
    object, maintaining the current position in the buffer. It supports unpacking
    binary data according to struct format strings and reading ASCII strings with
    length prefixes.

    Args:
        data (bytes): The binary data to read from.
    """

    def __init__(self, data: bytes):
        """Initialize the BytesBuffer with binary data.

        Args:
            data (bytes): The binary data to read from.
        """
        self._data = data
        self._pos = 0

    def size(self) -> int:
        """Get the number of remaining bytes in the buffer.

        Returns:
            int: The number of unread bytes remaining in the buffer.
        """
        return len(self._data) - self._pos

    def data(self) -> bytes:
        """Get the remaining unread data in the buffer.

        Returns:
            bytes: The slice of data from the current position to the end.
        """
        return self._data[self._pos :]

    def unpack(self, fmt: str) -> tuple:
        """Unpack binary data according to the given format string.

        Uses the struct module's format syntax to unpack binary data from the
        current position in the buffer. Advances the position by the size of
        the unpacked data.

        Args:
            fmt (str): A struct format string (e.g., '<I' for little-endian unsigned int).

        Returns:
            tuple: The unpacked values according to the format string.

        Raises:
            Exception: If there isn't enough data remaining in the buffer for the requested format.
        """
        sz = struct.calcsize(fmt)
        if self._pos + sz > len(self._data):
            raise ValueError(f'BytesBuffer: {sz} bytes required for {fmt}, but have only {len(self._data) - self._pos}')
        self._pos += sz
        return struct.unpack_from(fmt, self._data, self._pos - sz)

    def unpack_string(self) -> str:
        """Unpack a length-prefixed ASCII string.

        Reads a string that is prefixed with a single byte length value.
        The string data follows the length byte and is decoded as ASCII.

        Returns:
            str: The decoded ASCII string.

        Raises:
            Exception: If there isn't enough data in the buffer.
            UnicodeDecodeError: If the string data cannot be decoded as ASCII.
        """
        slen = self.unpack('<B')[0]
        return self.unpack(f'<{slen}s')[0].decode('ascii')
