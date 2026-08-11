# Getting started

## Install the library

=== "pip"

    ```shell
    python -m pip install --upgrade radiacode
    ```

=== "uv"

    ```shell
    uv add radiacode
    ```

Install the optional example dependencies if you want to run the web server,
Prometheus exporter, or plotting examples:

```shell
python -m pip install --upgrade "radiacode[examples]"
```

## Connect to a device

Use a context manager so the USB handle or Bluetooth connection is always
released:

```python
from radiacode import RadiaCode

with RadiaCode() as device:
    print(device.serial_number())
    print(device.fw_version())
```

With no arguments, `RadiaCode` connects to the first available USB device. Use
`serial_number` when more than one USB device is connected:

```python
with RadiaCode(serial_number="RC-10x-xxxxxx") as device:
    print(device.serial_number())
```

For Bluetooth, pass the device identifier:

```python
with RadiaCode(bluetooth_mac="52:43:01:02:03:04") as device:
    print(device.serial_number())
```

See [Connections](guides/connections.md) for platform requirements and error
handling.

## Read measurements

`data_buf()` returns all records currently buffered by the device. A call can
contain several record types, so narrow them with `isinstance`:

```python
from radiacode import RadiaCode, RareData, RealTimeData

with RadiaCode() as device:
    for record in device.data_buf():
        if isinstance(record, RealTimeData):
            print(record.dt, record.count_rate, record.dose_rate)
        elif isinstance(record, RareData):
            print(record.dt, record.temperature, record.charge_level)
```

The records already contain timestamps calculated from the device data. See
[Measurements and units](guides/measurements.md) before converting dose values.

## Read a spectrum

```python
from radiacode import RadiaCode, spectrum_channel_to_energy

with RadiaCode() as device:
    spectrum = device.spectrum()

for channel, counts in enumerate(spectrum.counts):
    energy_kev = spectrum_channel_to_energy(
        channel, spectrum.a0, spectrum.a1, spectrum.a2
    )
    print(channel, energy_kev, counts)
```

The returned `Spectrum.duration` is a `datetime.timedelta`; call
`total_seconds()` when a numeric duration is needed.
