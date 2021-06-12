import argparse
import asyncio
import time

import aiohttp

from radiacode import CountRate, DoseRate, RadiaCode


def sensors_data(rc_conn):
    databuf = rc_conn.data_buf()

    last_countrate, last_doserate = None, None
    for v in databuf:
        if isinstance(v, CountRate):
            if last_countrate is None or last_countrate.dt < v.dt:
                last_countrate = v
        elif isinstance(v, DoseRate):
            if last_doserate is None or last_doserate.dt < v.dt:
                last_doserate = v

    ret = []
    if last_countrate is not None:
        ret.append(
            {
                'id': 'S1',
                'name': 'CountRate',
                'value': last_countrate.count_rate,
                'unit': 'CPS',
                'time': int(last_countrate.dt.timestamp()),
            }
        )
    if last_doserate is not None:
        ret.append(
            {
                'id': 'S2',
                'name': 'R_DoseRate',
                'value': 1000000 * last_doserate.dose_rate,
                'unit': 'μR/h',
                'time': int(last_doserate.dt.timestamp()),
            }
        )
    return ret


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
