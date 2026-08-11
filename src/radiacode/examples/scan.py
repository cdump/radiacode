import argparse
import asyncio

from bleak import BleakClient, BleakScanner


async def scan():
    devices = await BleakScanner.discover(return_adv=True)
    for device, advertisement in devices.values():
        name = advertisement.local_name or device.name
        if isinstance(name, str) and name.startswith('RadiaCode'):
            print(f'RadiaCode device: {device.address} ({name}), RSSI={advertisement.rssi} dB')


async def inspect_device(address):
    async with BleakClient(address) as client:
        for service in client.services:
            print(f'Service {service.uuid}')
            for characteristic in service.characteristics:
                print(f'  Characteristic {characteristic.uuid}: {", ".join(characteristic.properties)}')
                if 'read' in characteristic.properties:
                    print(f'    {bytes(await client.read_gatt_char(characteristic))!r}')


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan', action='store_true', help='scan for RadiaCode devices instead of connecting')
    parser.add_argument('--address', default='52:43:06:50:01:d7', help='Bluetooth device identifier to inspect')
    args = parser.parse_args()

    if args.scan:
        await scan()
    else:
        await inspect_device(args.address)


if __name__ == '__main__':
    asyncio.run(main())
