import argparse
import asyncio
import time
import aiohttp

from radiacode import RealTimeData, RadiaCode
from radiacode.transports.usb import DeviceNotFound as DeviceNotFoundUSB
from radiacode.transports.bluetooth import DeviceNotFound as DeviceNotFoundBT


def sensors_data(rc_conn):
    databuf = rc_conn.data_buf()

    last = None
    for v in databuf:
        if isinstance(v, RealTimeData):
            if last is None or last.dt < v.dt:
                last = v

    if last is None:
        return []

    ts = int(last.dt.timestamp())
    return [
        {
            'id': 'S1',
            'name': 'CountRate',
            'value': last.count_rate,
            'unit': 'CPS',
            'time': ts,
        },
        {
            'id': 'S2',
            'name': 'R_DoseRate',
            'value': 1000000 * last.dose_rate,
            'unit': 'μR/h',
            'time': ts,
        },
    ]


async def send_data(d):
    # use aiohttp because we already have it as dependency in webserver.py, don't want add 'requests' here
    async with aiohttp.ClientSession() as session:
        async with session.post('https://narodmon.ru/json', json=d) as resp:
            return await resp.text()


def main():
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
    parser.add_argument('--interval', type=int, required=False, default=600, help='Send interval, seconds')
    args = parser.parse_args()

    try:
        if args.bluetooth_mac:
            print(f'Connecting to Radiacode via Bluetooth (MAC address: {args.bluetooth_mac})')
            rc = RadiaCode(bluetooth_mac=args.bluetooth_mac)
        elif args.bluetooth_uuid:
            print(f'Connecting to Radiacode via Bluetooth (UUID: {args.bluetooth_uuid})')
            rc = RadiaCode(bluetooth_uuid=args.bluetooth_uuid)
        elif args.bluetooth_serial:
            print(f'Connecting to Radiacode via Bluetooth (Serial: {args.bluetooth_serial})')
            rc = RadiaCode(bluetooth_serial=args.bluetooth_serial)
        elif args.serial:
            print(f'Connecting to Radiacode via USB (Serial: {args.serial})')
            rc = RadiaCode(serial_number=args.serial)
        else:
            print('Connecting to Radiacode via USB')
            rc = RadiaCode()
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

    mac = args.bluetooth_mac.replace(':', '-') if args.bluetooth_mac else '00-00-00-00-00-00'

    device_data = {
        'mac': mac,
        'name': 'RadiaCode-101',
    }

    while True:
        d = {
            'devices': [
                {
                    **device_data,
                    'sensors': sensors_data(rc),
                },
            ],
        }

        try:
            r = asyncio.run(send_data(d))
            print(f'NarodMon Response: {r}')
        except Exception as ex:
            print(f'NarodMon send error: {ex}')

        time.sleep(args.interval)


if __name__ == '__main__':
    main()
