"""
  Simple scanner to find a Radiacode over bluetooth.
  If a Radiacode is found, the library will print out both the device's serial number and the UUID.
  On Mac the UUID is specific to a computer-radiacode pair. A scan from a different computer will return a different UUID.
"""
from radiacode.transports.bluetooth import Bluetooth
from radiacode.logger import Logger

def main():
    Logger.info('Looking for Radiacodes over Bluetooth')
    radiacodes = Bluetooth()._scan()

    if len(radiacodes) == 0:
        Logger.error('No Radiacodes found, make sure Bluetooth is active on both your device and the Radiacode. Make sure the Radiacode is not connected to other devices.')
    else:
        Logger.notify(f'{len(radiacodes)} Radiacode(s) found')

if __name__ == '__main__':
    main()