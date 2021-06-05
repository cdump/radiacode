import struct

import usb.core

from radiacode.bytes_buffer import BytesBuffer


class DeviceNotFound(Exception):
    pass


class Usb:
    def __init__(self):
        self._device = usb.core.find(idVendor=0x483, idProduct=0xF123)
        if self._device is None:
            raise DeviceNotFound

    def execute(self, request: bytes) -> BytesBuffer:
        self._device.write(0x1, request)

        data = self._device.read(0x81, 256).tobytes()
        response_length = struct.unpack_from('<I', data)[0]
        data = data[4:]

        while len(data) < response_length:
            r = self._device.read(0x81, response_length - len(data)).tobytes()
            data += r

        return BytesBuffer(data)
