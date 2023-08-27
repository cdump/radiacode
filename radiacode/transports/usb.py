import struct

import usb.core

from radiacode.bytes_buffer import BytesBuffer


class DeviceNotFound(Exception):
    pass


class MultipleUSBReadFailure(Exception):
    """Raised when max. number of USB read failues reached"""

    def __init__(self, message=None):
        self.message = 'Multiple USB Read Failures' if message is None else message
        super().__init__(self.message)


class Usb:
    def __init__(self, timeout_ms=3000):
        self._device = usb.core.find(idVendor=0x483, idProduct=0xF123)
        self._timeout_ms = timeout_ms
        if self._device is None:
            raise DeviceNotFound
        while True:
            try:
                self._device.read(0x81, 256, timeout=100)
            except usb.core.USBTimeoutError:
                break

    def execute(self, request: bytes) -> BytesBuffer:
        self._device.write(0x1, request)

        trials = 0
        max_trials = 3
        while trials < max_trials:  # repeat until non-zero lenght data received
            data = self._device.read(0x81, 256, timeout=self._timeout_ms).tobytes()
            if len(data) != 0:
                break
            else:
                trials += 1
        if trials >= max_trials:
            raise MultipleUSBReadFailure(str(trials) + ' USB Read Failures in sequence')

        response_length = struct.unpack_from('<I', data)[0]
        data = data[4:]

        while len(data) < response_length:
            r = self._device.read(0x81, response_length - len(data)).tobytes()
            data += r

        return BytesBuffer(data)
