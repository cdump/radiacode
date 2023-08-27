import struct

from bluepy.btle import BTLEDisconnectError, DefaultDelegate, Peripheral

from radiacode.bytes_buffer import BytesBuffer


class DeviceNotFound(Exception):
    pass


class Bluetooth(DefaultDelegate):
    def __init__(self, mac):
        self._resp_buffer = b''
        self._resp_size = 0
        self._response = None

        try:
            self.p = Peripheral(mac)
        except BTLEDisconnectError as ex:
            raise DeviceNotFound('Device not found or bluetooth adapter is not powered on') from ex

        self.p.withDelegate(self)

        service = self.p.getServiceByUUID('e63215e5-7003-49d8-96b0-b024798fb901')
        self.write_fd = service.getCharacteristics('e63215e6-7003-49d8-96b0-b024798fb901')[0].getHandle()
        notify_fd = service.getCharacteristics('e63215e7-7003-49d8-96b0-b024798fb901')[0].getHandle()
        self.p.writeCharacteristic(notify_fd + 1, b'\x01\x00')

    def handleNotification(self, chandle, data):
        if self._resp_size == 0:
            self._resp_size = 4 + struct.unpack('<i', data[:4])[0]
            self._resp_buffer = data[4:]
        else:
            self._resp_buffer += data
        self._resp_size -= len(data)
        assert self._resp_size >= 0
        if self._resp_size == 0:
            self._response = self._resp_buffer
            self._resp_buffer = b''

    def execute(self, req) -> BytesBuffer:
        for pos in range(0, len(req), 18):
            rp = req[pos : min(pos + 18, len(req))]
            self.p.writeCharacteristic(self.write_fd, rp)

        while self._response is None:
            self.p.waitForNotifications(2.0)

        br = BytesBuffer(self._response)
        self._response = None
        return br
