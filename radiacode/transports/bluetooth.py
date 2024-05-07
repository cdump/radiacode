import struct
import platform
import asyncio

RADIACODE_SERVICE_UUID = 'e63215e5-7003-49d8-96b0-b024798fb901'  # Handle: 12
RADIACODE_WRITEFD_UUID = 'e63215e6-7003-49d8-96b0-b024798fb901'  # Handle: 13, (write-without-response, write), Max write w/o rsp size: 217
RADIACODE_NOTIFYFD_UUID = 'e63215e7-7003-49d8-96b0-b024798fb901' # Handle: 15, notify

tok = '[\033[1;32m\N{check mark}\033[0m]'
tnok = '[\033[1;31m\N{aegean check mark}\033[0m]'
tinfo = '[\033[1;34m\N{information source}\033[0m]'

class DeviceNotFound(Exception):
    pass

if platform.system() == 'Darwin':
    from radiacode.bytes_buffer import BytesBuffer
    from bleak import BleakScanner, BleakClient

    class Bluetooth():
        def __init__(self):
            self._resp_buffer = b''
            self._resp_size = 0
            self._response = None
            self.client = None

            # self.p.writeCharacteristic(notify_fd + 1, b'\x01\x00')

        async def connect(self, serial=None):
            bt_devices = await self._scan()

            if len(bt_devices) == 0:
                raise DeviceNotFound(f'{tnok} No valid Radiacodes found. Check that bluetooth is enabled.')
            
            ble, adv = (None, None)

            if serial is not None:
                for b, a in bt_devices:
                    if serial in str(a.local_name):
                        ble, adv = b, a
                        break
            else: # Pick the first device if no serial is specified
                ble, adv = bt_devices[0]

            if ble is None:
                raise DeviceNotFound(f'{tnok} No valid Radiacodes found while scanning. Check that the Radiacode is not connected to other devices then try again.')

            self.client = BleakClient(ble)
            await self.client.connect()
                
            if self.client.is_connected:
                print(f'{tok} Connected via Bluetooth to {adv.local_name}')
            else:
                raise DeviceNotFound(f'{tnok} Cannot connect to {adv.local_name} - UUID: {ble[0]}')
            
            # Start notifications
            self.notiffd = self.client.services.get_characteristic(RADIACODE_NOTIFYFD_UUID)
            await self.client.start_notify(self.notiffd, self.handleNotification)

            self.writefd = self.client.services.get_characteristic(RADIACODE_WRITEFD_UUID)

            print(f'{tok} Notifications started')
        
        async def _scan(self):
            radiacodes = []

            print(f'{tinfo} Scan started...')
            devices = await BleakScanner.discover(return_adv=True, cb=dict(use_bdaddr=False))

            for ble, adv in devices.values():
                if "RadiaCode" in str(adv.local_name):
                    radiacodes.append((ble, adv))

            if len(radiacodes) == 0:
                raise DeviceNotFound(f'{tnok} No RadiaCode found. Make ensure that bluetooth is active and that the RadiaCode is not already connected to another device')
            
            bt_devices = []

            for r in radiacodes:
                ble, adv = r

                if RADIACODE_SERVICE_UUID not in adv.service_uuids:
                    print(f'{tnok} No valid service found for device {adv.local_name} - UUID: {ble.address}')
                    continue
                else:
                    print(f'{tok} Active service found for device {adv.local_name} - UUID: {ble.address}')

                bt_devices.append(r)
                
            return bt_devices

        def handleNotification(self, characteristic, data):
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

            #print(f'{tok} Notification: {characteristic.description}: {self._resp_buffer}')
            
        async def execute(self, req) -> BytesBuffer:
            # for pos in range(0, len(req), 18):
            #     rp = req[pos : min(pos + 18, len(req))]
            #     self.p.writeCharacteristic(self.write_fd, rp)
            if self.client is None or self.client.is_connected == False:
                await self.client.connect()

            if self.client.is_connected == False:
                raise DeviceNotFound(f'{tnok} Connection to the device not active')

            # Request data
            self._response = []
            await self.client.write_gatt_char(self.writefd, req, response=False)
            await asyncio.sleep(2.0)
            #await self.client.stop_notify(notif)

            br = BytesBuffer(self._response)
            self._response = None
            return br

else:
    from bluepy.btle import BTLEDisconnectError, DefaultDelegate, Peripheral
    from radiacode.bytes_buffer import BytesBuffer

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
