import argparse
import asyncio
import time

import aiohttp

from radiacode import RealTimeData, RadiaCode


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
    parser.add_argument('--bluetooth-mac', type=str, required=True, help='MAC address of radiascan device')
    parser.add_argument('--connection', choices=['usb', 'bluetooth'], default='bluetooth', help='device connection type')
    parser.add_argument('--interval', type=int, required=False, default=600, help='send interval, seconds')
    args = parser.parse_args()

    if args.connection == 'usb':
        print('will use USB connection')
        rc_conn = RadiaCode()
    else:
        print('will use Bluetooth connection')
        rc_conn = RadiaCode(bluetooth_mac=args.bluetooth_mac)

    device_data = {
        'mac': args.bluetooth_mac.replace(':', '-'),
        'name': 'RadiaCode-101',
    }

    while True:
        d = {
            'devices': [
                {
                    **device_data,
                    'sensors': sensors_data(rc_conn),
                },
            ],
        }
        print(f'Sending {d}')

        try:
            r = asyncio.run(send_data(d))
            print(f'NarodMon Response: {r}')
        except Exception as ex:
            print(f'NarodMon send error: {ex}')

        time.sleep(args.interval)


if __name__ == '__main__':
    main()
