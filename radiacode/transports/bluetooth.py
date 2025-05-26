import struct
import platform
import time


class DeviceNotFound(Exception):
    pass


class ConnectionClosed(Exception):
    pass


if platform.system() == 'Darwin':

    class Bluetooth:
        def __init__(self):
            # Create an empty class if we are on MacOS
            pass

        def close(self):
            # No resources to release on MacOS
            pass

else:
    from bluepy.btle import BTLEDisconnectError, DefaultDelegate, Peripheral
    from radiacode.bytes_buffer import BytesBuffer

    class Bluetooth(DefaultDelegate):
        def __init__(self, mac, poll_interval: float = 0.01):
            """
            Initialize Bluetooth connection.
            
            Args:
                mac: Bluetooth MAC address
                poll_interval: How often to poll for notifications (default 0.01s = 10ms)
                              Shorter intervals provide better shutdown responsiveness.
            """
            self._resp_buffer = b''
            self._resp_size = 0
            self._response = None
            self._closing = False
            self._poll_interval = poll_interval

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
            if self._closing:
                raise ConnectionClosed('Connection is closing')
                
            # Send request
            for pos in range(0, len(req), 18):
                rp = req[pos : min(pos + 18, len(req))]
                self.p.writeCharacteristic(self.write_fd, rp)

            # Poll for response with short intervals for better shutdown responsiveness
            timeout_end = time.time() + 10.0  # 10 second total timeout
            while self._response is None and not self._closing:
                remaining_time = timeout_end - time.time()
                if remaining_time <= 0:
                    raise TimeoutError('Response timeout')
                
                # Use short poll interval, but not longer than remaining time
                poll_time = min(self._poll_interval, remaining_time)
                
                try:
                    self.p.waitForNotifications(poll_time)
                except BTLEDisconnectError:
                    raise ConnectionClosed('Bluetooth connection lost')

            if self._closing:
                raise ConnectionClosed('Connection closed while waiting for response')

            br = BytesBuffer(self._response)
            self._response = None
            return br

        def close(self):
            """Disconnect from the Bluetooth device and release resources."""
            self._closing = True
            
            # Give a brief moment for any pending operations
            time.sleep(0.1)
            
            if hasattr(self, 'p') and self.p is not None:
                try:
                    self.p.disconnect()
                except:
                    pass  # Ignore errors during disconnect
                self.p = None