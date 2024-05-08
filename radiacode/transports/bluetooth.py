import struct
import asyncio
from typing import Optional, List, Tuple

from radiacode.bytes_buffer import BytesBuffer
from radiacode.logger import Logger
from bleak import BleakScanner, BleakClient
from bleak.backends.scanner import AdvertisementData, BLEDevice

RADIACODE_SERVICE_UUID = 'e63215e5-7003-49d8-96b0-b024798fb901'  # Handle: 12
RADIACODE_WRITEFD_UUID = 'e63215e6-7003-49d8-96b0-b024798fb901'  # Handle: 13, (write-without-response, write), Max write w/o rsp size: 217
RADIACODE_NOTIFYFD_UUID = 'e63215e7-7003-49d8-96b0-b024798fb901' # Handle: 15, notify

class DeviceNotFound(Exception):
    pass

class Bluetooth():
    def __init__(self,
        bluetooth_mac: Optional[str] = None,
        bluetooth_serial: Optional[str] = None,
        bluetooth_uuid: Optional[str] = None
    ):
        self._resp_buffer = b''
        self._resp_size = 0
        self._response = None
        self.client = None
        self._response_event = asyncio.Event()

        self.bluetooth_mac = bluetooth_mac # Only for Windows and Linux
        self.bluetooth_serial = bluetooth_serial
        self.bluetooth_uuid = bluetooth_uuid

        # self.p.writeCharacteristic(notify_fd + 1, b'\x01\x00')

    async def connect(self) -> None:
        if self.bluetooth_mac:
            if len(self.bluetooth_mac) != 17:
                Logger.warning('The provided MAC address does not seem to be valid, but we will try anyway')

            self.client = BleakClient(self.bluetooth_mac)
        elif self.bluetooth_serial:
            if len(self.bluetooth_serial) < 6:
                Logger.warning('To improve reliability, try to provide at least 6 digits of your Radiacode serial number')

            bt_devices = await self._scan()

            if len(bt_devices) == 0:
                raise DeviceNotFound('No Radiacodes found. Check that bluetooth is enabled and that the Radiacode is not connected to another device.')
            
            ble, _ = (None, None)

            # Find the requested device in the list
            for b, a in bt_devices:
                if self.bluetooth_serial in str(a.local_name):
                    ble = b
                    break

            if ble is None:
                raise DeviceNotFound(f'No matching serial found while scanning. We were looking for: {self.bluetooth_serial}')

            self.client = BleakClient(ble)
        elif self.bluetooth_uuid:
            if len(self.bluetooth_uuid) != 36:
                Logger.warning('The provided UUID does not seem to be valid, but we will try anyway')

            self.client = BleakClient(self.bluetooth_uuid)
        else:
            raise DeviceNotFound('No connection parameters specified.')

        # Attempt connection
        await self.client.connect()
            
        if self.client.is_connected:
            Logger.notify(f'Connected to Radiacode via bluetooth to: {self.client.address}')
        else:
            raise DeviceNotFound('Cannot connect to the requested Radiacode')
        
        # Start notifications
        self.notiffd = self.client.services.get_characteristic(RADIACODE_NOTIFYFD_UUID)
        await self.client.start_notify(self.notiffd, self.handleNotification)

        self.writefd = self.client.services.get_characteristic(RADIACODE_WRITEFD_UUID)

        Logger.notify(f'Notifications started')
    
    async def _scan(self) -> List[Tuple[BLEDevice, AdvertisementData]]:
        """ Returns a list of Tuples of valid Radiacodes """
        radiacodes = []

        Logger.info(f'Scan started...')
        devices = await BleakScanner.discover(return_adv=True, cb=dict(use_bdaddr=False))

        for ble, adv in devices.values():
            if "RadiaCode" in str(adv.local_name):
                radiacodes.append((ble, adv))

        if len(radiacodes) == 0:
            return []
        
        bt_devices = []

        for r in radiacodes:
            ble, adv = r

            if RADIACODE_SERVICE_UUID not in adv.service_uuids:
                Logger.error(f'No valid service found for device ID: {adv.local_name} - UUID: {ble.address}')
                continue
            else:
                Logger.notify(f'Active service found for device ID: {adv.local_name} - UUID: {ble.address}')

            bt_devices.append(r)
            
        return bt_devices

    def handleNotification(self, characteristic, data) -> None:
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
        
        #self._response_event.set()

        #print(f'{tok} Notification: {characteristic.description}: {self._resp_buffer}')
        
    async def execute(self, req) -> BytesBuffer:
        if self.client is None or self.client.is_connected == False:
            await self.client.connect()

        if self.client.is_connected == False:
            raise DeviceNotFound('Connection to the device not active')

        # Request data
        self._response = []
        await self.client.write_gatt_char(self.writefd, req, response=False)
        await asyncio.sleep(1.5)
        #await self._response_event.wait()
        
        #await self.client.stop_notify(notif)

        br = BytesBuffer(self._response)
        self._response = None
        return br