# Connections

`RadiaCode` opens its connection during construction. Prefer a `with` block, or
call `close()` explicitly when the object is no longer needed.

## USB

```python
from radiacode import RadiaCode

with RadiaCode() as device:
    print(device.serial_number())
```

When several supported devices are attached, select one by its device serial
number:

```python
with RadiaCode(serial_number="RC-10x-xxxxxx") as device:
    ...
```

Platform notes:

- **Linux:** install libusb. If access is denied, install the repository's
  [`radiacode.rules`](https://github.com/cdump/radiacode/blob/master/radiacode.rules)
  as an appropriate udev rule rather than running the application as root.
- **macOS:** install libusb, for example with `brew install libusb`.
- **Windows:** install a compatible USB driver for the device.

The USB-specific connection errors can be caught when an application needs to
distinguish them:

```python
from radiacode import RadiaCode
from radiacode.transports.usb import DeviceNotFound

try:
    device = RadiaCode()
except DeviceNotFound:
    print("No supported USB device was found")
else:
    device.close()
```

## Bluetooth

Pass a MAC address on Linux and Windows. Pass the CoreBluetooth UUID reported
by the operating system on macOS:

```python
from radiacode import RadiaCode

with RadiaCode(bluetooth_mac="52:43:01:02:03:04") as device:
    print(device.serial_number())
```

Bluetooth uses Bleak and starts a background event-loop thread for the lifetime
of the connection. `close()` disconnects the client and stops that thread.

```python
from radiacode import RadiaCode
from radiacode.transports.bluetooth import DeviceNotFound

try:
    device = RadiaCode(bluetooth_mac="52:43:01:02:03:04")
except DeviceNotFound as error:
    print(error)
else:
    device.close()
```

!!! note

    `serial_number` selects a USB device and is ignored when `bluetooth_mac` is
    supplied.

## Firmware compatibility

Initialization rejects firmware older than 4.8 by default. Upgrade the device
firmware when possible. `ignore_firmware_compatibility_check=True` bypasses
that guard for diagnostic use, but it does not make an incompatible protocol
safe or supported.
