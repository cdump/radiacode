import argparse
import time
import platform

from radiacode import RadiaCode
from radiacode.transports.usb import DeviceNotFound as DeviceNotFoundUSB
from radiacode.transports.bluetooth import DeviceNotFound as DeviceNotFoundBT


def main():
    parser = argparse.ArgumentParser()

    # Bluetooth is only supported on Linux via bluepy
    if platform.system() == 'Linux':
        parser.add_argument(
            '--bluetooth-mac',
            type=str,
            required=False,
            help='(Linux only) Bluetooth MAC address of radiascan device (e.g. 00:11:22:33:44:55)',
        )

    parser.add_argument(
        '--serial',
        type=str,
        required=False,
        help='serial number of radiascan device (e.g. "RC-10x-xxxxxx"). Useful in case of multiple devices.',
    )

    args = parser.parse_args()

    if hasattr(args, 'bluetooth_mac') and args.bluetooth_mac:
        print(f'Connecting to Radiacode via Bluetooth (MAC address: {args.bluetooth_mac})')

        try:
            rc = RadiaCode(bluetooth_mac=args.bluetooth_mac)
        except DeviceNotFoundBT as e:
            print(e)
            return
        except ValueError as e:
            print(e)
            return
    else:
        print('Connecting to Radiacode via USB' + (f' (serial number: {args.serial})' if args.serial else ''))

        try:
            rc = RadiaCode(serial_number=args.serial)
        except DeviceNotFoundUSB:
            print('Device not found, check your USB connection')
            return

    serial = rc.serial_number()
    print(f'### Serial number: {serial}')
    print('--------')

    fw_version = rc.fw_version()
    print(f'### Firmware: {fw_version}')
    print('--------')

    spectrum = rc.spectrum()
    print(f'### Spectrum: {spectrum}')
    print('--------')

    print('### DataBuf:')
    while True:
        for v in rc.data_buf():
            print(v.dt.isoformat(), v)
        time.sleep(2)


if __name__ == '__main__':
    main()
