import argparse
import time
import asyncio

from radiacode import RadiaCode
from radiacode.transports.usb import DeviceNotFound as DeviceNotFoundUSB
from radiacode.transports.bluetooth import DeviceNotFound as DeviceNotFoundBT


async def main(args: argparse.Namespace):
    try:
        if args.bluetooth_mac:
            print(f'Connecting to Radiacode via Bluetooth (MAC address: {args.bluetooth_mac})')
            rc = await RadiaCode.async_init(bluetooth_mac=args.bluetooth_mac)
        elif args.bluetooth_uuid:
            print(f'Connecting to Radiacode via Bluetooth (UUID: {args.bluetooth_uuid})')
            rc = await RadiaCode.async_init(bluetooth_uuid=args.bluetooth_uuid)
        elif args.bluetooth_serial:
            print(f'Connecting to Radiacode via Bluetooth (Serial: {args.bluetooth_serial})')
            rc = await RadiaCode.async_init(bluetooth_serial=args.bluetooth_serial)
        elif args.serial:
            print(f'Connecting to Radiacode via USB (Serial: {args.serial})')
            rc = await RadiaCode.async_init(serial_number=args.serial)
        else:
            print('Connecting to Radiacode via USB')
            rc = await RadiaCode.async_init()
    except DeviceNotFoundBT as e:
        print(e)
        return
    except DeviceNotFoundUSB:
        print('Radiacode not found, check your USB connection')
        return
    except ValueError as e:
        print(e)
        return
    except Exception as e:
        print(e)
        return

    serial = await rc.async_serial_number()
    print(f'### Serial number: {serial}')
    print('--------')

    fw_version = await rc.async_fw_version()
    print(f'### Firmware: {fw_version}')
    print('--------')

    spectrum = await rc.async_spectrum()
    print(f'### Spectrum: {spectrum}')
    print('--------')

    print('### DataBuf:')
    while True:
        for v in await rc.async_data_buf():
            print(v.dt.isoformat(), v)
        time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--bluetooth-mac',
        type=str,
        required=False,
        help='Radiacode Bluetooth MAC address (e.g. 00:11:22:33:44:55). MacOS does not support BT MACs, use Serial Number or UUID instead.',
    )
    parser.add_argument(
        '--bluetooth-serial',
        type=str,
        required=False,
        help='Connect via Bluetooth using Radiacode Serial (e.g. "RC-10x-xxxxxx").',
    )
    parser.add_argument(
        '--bluetooth-uuid',
        type=str,
        required=False,
        help='Connect via Bluetooth using Radiacode UUID (e.g. "11111111-2222-3333-4444-56789ABCDEF").',
    )
    parser.add_argument(
        '--serial', type=str, required=False, help='Connect via USB using Radiacode Serial (e.g. "RC-10x-xxxxxx").'
    )
    parser.add_argument('--usb', type=str, required=False, help='(default) Connect via USB to the first Radiacode available.')

    args = parser.parse_args()

    asyncio.run(main(args))
