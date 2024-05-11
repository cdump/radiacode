import argparse
import time

import prometheus_client

from radiacode import RealTimeData, RadiaCode
from radiacode.transports.usb import DeviceNotFound as DeviceNotFoundUSB
from radiacode.transports.bluetooth import DeviceNotFound as DeviceNotFoundBT

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bluetooth-mac', type=str, required=False, help='Radiacode Bluetooth MAC address (e.g. 00:11:22:33:44:55). MacOS does not support BT MACs, use Serial Number or UUID instead.')
    parser.add_argument('--bluetooth-serial', type=str, required=False, help='Connect via Bluetooth using Radiacode Serial (e.g. "RC-10x-xxxxxx").')
    parser.add_argument('--bluetooth-uuid', type=str, required=False, help='Connect via Bluetooth using Radiacode UUID (e.g. "11111111-2222-3333-4444-56789ABCDEF").')
    parser.add_argument('--serial', type=str, required=False, help='Connect via USB using Radiacode Serial (e.g. "RC-10x-xxxxxx").')
    parser.add_argument('--update-interval', type=int, default=3, required=False, help='update interval (seconds)')
    parser.add_argument('--port', type=int, default=5432, required=False, help='prometheus http port')

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

    serial = rc.serial_number()

    metric_count_rate = prometheus_client.Gauge('radiacode_count_rate', 'count rate, CPS', ['device']).labels(serial)
    metric_count_rate_error = prometheus_client.Gauge('radiacode_count_rate_error', 'count rate error, %', ['device']).labels(
        serial
    )
    metric_dose_rate = prometheus_client.Gauge('radiacode_dose_rate', 'dose rate, μSv/h', ['device']).labels(serial)
    metric_dose_rate_error = prometheus_client.Gauge('radiacode_dose_rate_error', 'dose rate error, %', ['device']).labels(serial)

    prometheus_client.start_http_server(args.port)

    while True:
        for v in rc.data_buf():
            if isinstance(v, RealTimeData):
                metric_count_rate.set(v.count_rate)
                metric_count_rate_error.set(v.count_rate_err)
                metric_dose_rate.set(10000 * v.dose_rate)  # convert to μSv/h
                metric_dose_rate_error.set(v.dose_rate_err)

        time.sleep(args.update_interval)


if __name__ == '__main__':
    main()
