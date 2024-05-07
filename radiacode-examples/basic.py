import argparse
import time, platform, asyncio

from radiacode import RadiaCode
from radiacode.transports.usb import DeviceNotFound as DeviceNotFoundUSB
from radiacode.transports.bluetooth import DeviceNotFound as DeviceNotFoundBT

async def main(args: argparse.Namespace):
    if hasattr(args, 'bluetooth_mac') and getattr(args, 'bluetooth_mac', None):
        print(f'Connecting to Radiacode via Bluetooth (MAC address: {args.bluetooth_mac})')

        try:
            rc = RadiaCode(bluetooth_mac=args.bluetooth_mac)
        except DeviceNotFoundBT as e:
            print(e)
            return
        except ValueError as e:
            print(e)
            return
    elif hasattr(args, 'bluetooth') and getattr(args, 'bluetooth', None):
        if args.bluetooth is None:
            print('Scanning for devices. We will try to connect to the first Radiacode available via Bluetooth')
        else:
            print(f'Scanning for devices. We will try to connect to: {args.bluetooth}')

        try:
            rc = await RadiaCode.BT(args.bluetooth)
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

    await rc.set_sound_on(False)

    serial = await rc.serial_number()
    print(f'### Serial number: {serial}')
    print('--------')

    fw_version = await rc.fw_version()
    print(f'### Firmware: {fw_version}')
    print('--------')

    spectrum = await rc.spectrum()
    print(f'### Spectrum: {spectrum}')
    print('--------')

    print('### DataBuf:')
    while True:
        for v in await rc.data_buf():
            print(v.dt.isoformat(), v)
        time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    if platform.system() != 'Darwin':
        parser.add_argument('--bluetooth-mac', type=str, required=False, help='bluetooth MAC address of radiascan device (e.g. 00:11:22:33:44:55)')
    else:
        parser.add_argument('--bluetooth', type=str, required=False, help='Radiacode Serial (e.g. "RC-10x-xxxxxx"). \
                            Since MacOS does not show Bluetooth MACs, the device has to be identified via its serial number.')

    parser.add_argument('--serial', type=str, required=False,
                        help='serial number of Radiacode device (e.g. "RC-10x-xxxxxx"). Useful in case of multiple devices.')

    args = parser.parse_args()

    asyncio.run(main(args))
