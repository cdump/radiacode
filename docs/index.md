# RadiaCode Python Library

`radiacode` is a Python interface for RadiaCode-10x radiation detectors and
spectrometers. It supports USB and Bluetooth connections, live measurements,
spectrum acquisition, energy calibration, and device configuration.

[Get started](getting-started.md){ .md-button .md-button--primary }
[API reference](reference/index.md){ .md-button }

## Installation

```shell
python -m pip install --upgrade radiacode
```

Python 3.9 or newer is required.

## Quick example

```python
from radiacode import RadiaCode, RealTimeData

with RadiaCode() as device:
    print(device.serial_number())

    for record in device.data_buf():
        if isinstance(record, RealTimeData):
            print(f"Count rate: {record.count_rate} cps")

    spectrum = device.spectrum()
    print(f"Live time: {spectrum.duration.total_seconds()} s")
    print(f"Total counts: {sum(spectrum.counts)}")
```

Pass `bluetooth_mac` to `RadiaCode` to use Bluetooth instead of USB. On macOS,
this value is the device's CoreBluetooth UUID rather than a conventional MAC
address.

## What is generated?

The [API reference](reference/index.md) is built directly from the library's
type annotations and docstrings. The task-focused guides are maintained as
Markdown so that behavior, units, and complete workflows can be explained in
context.
